from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from tasks.RealmRaid.config import RaidConfig
from tasks.RealmRaid.script_task import ScriptTask
from tasks.GlobalGame.assets import GlobalGameAssets
from module.exception import TaskEnd


def make_task() -> ScriptTask:
    task = object.__new__(ScriptTask)
    task.round_retreat_done = False
    task.first_attack_pending_after_retreat = False
    return task


def make_config(*, exit_four: bool = True):
    return SimpleNamespace(
        raid_config=SimpleNamespace(exit_four=exit_four),
        general_battle_config=SimpleNamespace(),
    )


def test_legacy_failure_options_are_removed():
    config = RaidConfig()

    assert not hasattr(config, "three_refresh")
    assert not hasattr(config, "when_attack_fail")


def test_ensure_retreat_four_skips_when_disabled():
    task = make_task()
    task.screenshot = Mock()
    task.is_first_position_finished = Mock()
    task.check_ticket = Mock()
    task.retreat_four_at_first = Mock()

    assert task.ensure_retreat_four(make_config(exit_four=False))
    task.screenshot.assert_not_called()
    task.retreat_four_at_first.assert_not_called()


def test_failed_first_position_does_not_count_as_completed_retreat_four():
    task = make_task()
    task.screenshot = Mock()
    task.is_first_position_finished = Mock(return_value=True)
    task.check_ticket = Mock(return_value=True)
    task.retreat_four_at_first = Mock(return_value=True)
    config = make_config()

    assert task.ensure_retreat_four(config)
    assert task.round_retreat_done
    task.retreat_four_at_first.assert_called_once_with(config)


def test_ensure_retreat_four_runs_only_once_per_round():
    task = make_task()
    task.screenshot = Mock()
    task.is_first_position_finished = Mock(return_value=False)
    task.check_ticket = Mock(return_value=True)
    task.retreat_four_at_first = Mock(return_value=True)
    config = make_config()

    assert task.ensure_retreat_four(config)
    assert task.ensure_retreat_four(config)
    assert task.round_retreat_done
    assert task.first_attack_pending_after_retreat
    task.retreat_four_at_first.assert_called_once_with(config)


def test_refresh_round_ensures_retreat_and_resets_state():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.check_refresh = Mock(return_value=True)
    task.round_retreat_done = True
    task.first_attack_pending_after_retreat = True
    config = make_config()

    assert task.refresh_round(config)
    task.ensure_retreat_four.assert_called_once_with(config)
    task.check_refresh.assert_called_once_with()
    assert not task.round_retreat_done
    assert not task.first_attack_pending_after_retreat


def test_refresh_round_keeps_state_when_refresh_is_unavailable():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.check_refresh = Mock(return_value=False)
    task.round_retreat_done = True

    assert not task.refresh_round(make_config())
    assert task.round_retreat_done


@pytest.fixture
def refresh_task(monkeypatch):
    # 保留真实 appear_then_click 和 Timer，验证一秒点击间隔，仅模拟画面与设备输入。
    clock = {'now': 100.0}
    monkeypatch.setattr('module.base.timer.time.time', lambda: clock['now'])

    def make(*, required_clicks=1, popup_open=False, available=True,
             ignore_refresh=False, miss_first_confirm=False, hide_popup_once=False):
        task = make_task()
        task.interval_timer = {}
        state = {'popup': popup_open, 'refreshed': False, 'hidden': False,
                 'hidden_once': False, 'confirm_times': [], 'ready_frames': 0}

        def screenshot():
            clock['now'] += 0.3
            state['hidden'] = (hide_popup_once and not state['hidden_once']
                               and len(state['confirm_times']) == 1 and state['popup'])
            state['hidden_once'] |= state['hidden']
            if state['refreshed']:
                state['ready_frames'] += 1

        def match(rule):
            if rule is task.I_FRESH:
                return available and not state['popup'] and not state['refreshed']
            if rule in (GlobalGameAssets.I_UI_CONFIRM, GlobalGameAssets.I_UI_CANCEL):
                return state['popup'] and not state['hidden']
            return rule is task.I_RR_PERSON

        for rule in (task.I_FRESH, task.I_RR_PERSON,
                     GlobalGameAssets.I_UI_CONFIRM, GlobalGameAssets.I_UI_CANCEL):
            monkeypatch.setattr(rule, 'match', lambda image, _rule=rule, **kwargs: match(_rule))

        def click(x, y, control_name):
            if control_name == task.I_FRESH.name and not ignore_refresh:
                state['popup'] = True
            if control_name == GlobalGameAssets.I_UI_CONFIRM.name:
                state['confirm_times'].append(clock['now'])
                if required_clicks is not None and len(state['confirm_times']) >= required_clicks:
                    state['popup'] = False
                    state['refreshed'] = True

        task.device = SimpleNamespace(image=object(), image_frame_id='refresh-test',
            get_image_batch_cache=Mock(return_value=None), click=Mock(side_effect=click))
        task.screenshot = Mock(side_effect=screenshot)
        task.goto_page = Mock()
        if miss_first_confirm:
            original_click = task.appear_then_click
            missed = {'done': False}

            def appear_then_click(rule, **kwargs):
                if rule is GlobalGameAssets.I_UI_CONFIRM and not missed['done']:
                    missed['done'] = True
                    return False
                return original_click(rule, **kwargs)

            task.appear_then_click = appear_then_click
        return task, state

    return make


def test_refresh_cooldown_does_not_click_anything(refresh_task):
    task, _ = refresh_task(available=False)
    assert not task.check_refresh()
    task.device.click.assert_not_called()


def test_refresh_stops_when_click_does_not_open_confirmation(refresh_task):
    task, state = refresh_task(ignore_refresh=True)
    assert not task.check_refresh()
    assert state['confirm_times'] == []


@pytest.mark.parametrize('required_clicks', [1, 2, 3, None])
def test_refresh_confirmation_retries_with_real_click_interval(refresh_task, required_clicks):
    task, state = refresh_task(required_clicks=required_clicks)
    assert task.check_refresh() is (required_clicks is not None)
    times = state['confirm_times']
    assert times
    assert all(later - earlier >= 1 for earlier, later in zip(times, times[1:]))
    if required_clicks is not None:
        assert len(times) == required_clicks
        assert state['ready_frames'] >= 2
    else:
        assert len(times) > 1
    controls = [call.kwargs['control_name'] for call in task.device.click.call_args_list]
    assert controls.count(task.I_FRESH.name) == 1
    assert GlobalGameAssets.I_UI_CANCEL.name not in controls
    task.goto_page.assert_not_called()


def test_refresh_handles_existing_confirmation_with_hidden_background_button(refresh_task):
    task, state = refresh_task(popup_open=True, available=False)
    assert task.check_refresh()
    assert state['refreshed']
    assert all(call.kwargs['control_name'] != task.I_FRESH.name
               for call in task.device.click.call_args_list)


def test_refresh_retries_when_first_confirmation_check_misses(refresh_task):
    task, state = refresh_task(miss_first_confirm=True)
    assert task.check_refresh()
    assert state['refreshed']


def test_refresh_does_not_treat_one_missing_popup_frame_as_success(refresh_task):
    task, state = refresh_task(required_clicks=2, hide_popup_once=True)
    assert task.check_refresh()
    assert state['refreshed']
    assert len(state['confirm_times']) == 2


def test_three_wins_attacks_first_and_continues_when_other_positions_have_no_failure():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[])
    task.is_first_position_finished = Mock(return_value=False)
    task.refresh_round = Mock()

    assert task.process_three_win_stage(make_config()) == "attack_first"
    task.ensure_retreat_four.assert_called_once()
    task.refresh_round.assert_not_called()


def test_three_wins_refreshes_after_formal_first_position_failure():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[1])
    task.is_first_position_finished = Mock(return_value=True)
    task.refresh_round = Mock(return_value=True)
    config = make_config()

    assert task.process_three_win_stage(config) == "refreshed"
    task.refresh_round.assert_called_once_with(config, failed_position=1)


def test_three_wins_attacks_first_when_retreat_failure_mark_is_present():
    task = make_task()
    task.round_retreat_done = True
    task.first_attack_pending_after_retreat = True
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[1])
    task.is_first_position_finished = Mock(return_value=True)
    task.refresh_round = Mock()

    assert task.process_three_win_stage(make_config()) == "attack_first"
    task.is_first_position_finished.assert_not_called()
    task.refresh_round.assert_not_called()


def test_three_wins_keeps_clearing_a_won_first_position_without_assuming_retreat_done():
    task = make_task()
    task.get_failed_positions = Mock(return_value=[])
    task.is_first_position_finished = Mock(return_value=True)
    task.ensure_retreat_four = Mock()

    assert task.process_three_win_stage(make_config()) == 'continue'
    assert not task.round_retreat_done
    task.ensure_retreat_four.assert_not_called()


def test_three_wins_refreshes_when_another_position_failed():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[1, 4])
    task.is_first_position_finished = Mock()
    task.refresh_round = Mock(return_value=True)
    config = make_config()

    assert task.process_three_win_stage(config) == "refreshed"
    task.refresh_round.assert_called_once_with(config, failed_position=1)
    task.is_first_position_finished.assert_not_called()


def test_three_wins_stops_when_another_position_failed_and_refresh_is_unavailable():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[7])
    task.is_first_position_finished = Mock()
    task.refresh_round = Mock(return_value=False)

    assert task.process_three_win_stage(make_config()) == "stop"
    task.is_first_position_finished.assert_not_called()


def test_three_win_stage_is_read_from_the_game_image():
    task = make_task()
    task.screenshot = Mock()
    task.appear = Mock(return_value=True)

    assert task.has_three_wins()
    task.screenshot.assert_called_once_with()
    task.appear.assert_called_once_with(task.I_RR_THREE, threshold=0.8)


def test_find_one_masks_failed_positions_without_modifying_device_image():
    task = make_task()
    image = np.full((4, 18, 3), 255, dtype=np.uint8)
    task.device = SimpleNamespace(image=image)
    task.__dict__["partition"] = [
        SimpleNamespace(roi_back=(index * 2, 0, 2, 4), roi_front=(index * 2, 0, 2, 4))
        for index in range(9)
    ]

    find_anyone = Mock(return_value=None)
    task.__dict__["order_medal"] = SimpleNamespace(find_anyone=find_anyone)

    assert task.find_one(False, exclude_positions={2}) == (None, None)
    searched_image = find_anyone.call_args.args[0]
    assert np.all(searched_image[:, 2:4, ...] == 0)
    assert np.all(image == 255)


@pytest.mark.parametrize('position', [1, 4])
def test_retreat_four_runs_four_quick_exits(position):
    task = make_task()
    task.fire = Mock(return_value=True)
    task.build_quick_exit_config = Mock(return_value="quick-exit")
    task.run_general_battle = Mock(return_value=False)
    task.ui_click_until_appear_or_timeout = Mock(return_value=True)
    config = make_config()

    assert task.retreat_four_at_first(config, position=position)
    assert task.fire.call_count == 4
    task.fire.assert_called_with(position)
    assert task.run_general_battle.call_count == 4
    task.run_general_battle.assert_called_with(config="quick-exit")
    assert task.ui_click_until_appear_or_timeout.call_count == 4


@pytest.mark.parametrize('position', [1, 2])
@pytest.mark.parametrize('exit_four', [True, False])
@pytest.mark.parametrize('preexisting_failure', [True, False])
def test_normal_battle_failure_retreats_if_needed_then_refreshes_instead_of_attacking_others(
        position, exit_four, preexisting_failure):
    task = make_task()
    config = make_config(exit_four=exit_four)
    config.raid_config.number_base = 0
    config.raid_config.number_attack = 1
    config.general_battle_config.lock_team_enable = False
    config.switch_soul_config = SimpleNamespace(enable=False, enable_switch_by_name=False)
    task.config = SimpleNamespace(realm_raid=config)
    task.goto_page = Mock()
    task.set_next_run = Mock()
    task.screenshot = Mock()
    task.appear = Mock(side_effect=lambda rule, **kwargs: rule is task.I_RR_PERSON)
    task.ensure_lock = Mock()
    task.is_frog = Mock(return_value=False)
    task.has_three_wins = Mock(return_value=False)
    task.is_first_position_finished = Mock(return_value=False)
    task.get_failed_positions = Mock(return_value=[position] if preexisting_failure else [])
    task.find_one = Mock(return_value=('medal', position))
    task.check_medal_is_frog = Mock(return_value=False)
    task.fire = Mock(return_value=True)
    task.reward_detect_click = Mock(return_value=False)
    events = []
    task.check_ticket = Mock(side_effect=lambda *args: 'refresh' not in events)
    task.retreat_four_at_first = Mock(side_effect=lambda *args, **kwargs: events.append('retreat') or True)
    task.run_general_battle = Mock(side_effect=lambda *args: events.append('lose') or False)
    task.check_refresh = Mock(side_effect=lambda: events.append('refresh') or True)

    with pytest.raises(TaskEnd):
        task.run()

    expected = ['refresh'] if preexisting_failure else ['lose', 'refresh']
    if exit_four:
        expected.insert(0 if preexisting_failure or position == 1 else 1, 'retreat')
    assert events == expected
    if preexisting_failure:
        task.fire.assert_not_called()
        task.find_one.assert_not_called()
    else:
        task.fire.assert_called_once_with(position)
        task.find_one.assert_called_once()


@pytest.mark.parametrize('first_finished', [[False, False], [False, True], [True]])
def test_automatic_new_board_resets_retreat_state_only_after_stable_detection(first_finished):
    task = make_task()
    task.round_retreat_done = True
    task.first_attack_pending_after_retreat = True
    task.screenshot = Mock()
    task.appear = Mock(return_value=True)
    task.is_first_position_finished = Mock(side_effect=first_finished)

    task.sync_round_state()

    new_board = first_finished == [False, False]
    assert task.round_retreat_done is not new_board
    assert task.first_attack_pending_after_retreat is not new_board


def test_failure_in_other_position_can_retreat_there_when_first_position_was_already_won():
    task = make_task()
    task.screenshot = Mock()
    task.appear = Mock(side_effect=lambda rule: rule is task.I_RAID_SUCCESS)
    task.check_ticket = Mock(return_value=True)
    task.retreat_four_at_first = Mock(return_value=True)
    task.check_refresh = Mock(return_value=True)
    config = make_config()

    assert task.refresh_round(config, failed_position=4)
    task.retreat_four_at_first.assert_called_once_with(config, position=4)
    task.check_refresh.assert_called_once()
    assert not task.round_retreat_done


def test_refresh_uses_an_available_target_when_first_position_was_already_won():
    task = make_task()
    task.screenshot = Mock()
    task.appear = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[])
    task.find_one = Mock(return_value=('medal', 5))
    task.check_ticket = Mock(return_value=True)
    task.retreat_four_at_first = Mock(return_value=True)
    task.check_refresh = Mock(return_value=True)
    config = make_config()

    assert task.refresh_round(config)
    task.find_one.assert_called_once_with(False, exclude_positions={1})
    task.retreat_four_at_first.assert_called_once_with(config, position=5)


def test_failed_retreat_does_not_proceed_to_refresh():
    task = make_task()
    task.screenshot = Mock()
    task.appear = Mock(return_value=False)
    task.check_ticket = Mock(return_value=True)
    task.retreat_four_at_first = Mock(return_value=False)
    task.check_refresh = Mock()

    assert not task.refresh_round(make_config(), failed_position=1)
    task.check_refresh.assert_not_called()
    assert not task.round_retreat_done
