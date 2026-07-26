from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from tasks.RealmRaid.config import RaidConfig
from tasks.RealmRaid.script_task import ScriptTask


def make_task() -> ScriptTask:
    task = object.__new__(ScriptTask)
    task.round_retreat_done = False
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


def test_ensure_retreat_four_accepts_finished_first_position():
    task = make_task()
    task.screenshot = Mock()
    task.is_first_position_finished = Mock(return_value=True)
    task.check_ticket = Mock()
    task.retreat_four_at_first = Mock()

    assert task.ensure_retreat_four(make_config())
    assert task.round_retreat_done
    task.retreat_four_at_first.assert_not_called()


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
    task.retreat_four_at_first.assert_called_once_with(config)


def test_refresh_round_ensures_retreat_and_resets_state():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.check_refresh = Mock(return_value=True)
    task.round_retreat_done = True
    config = make_config()

    assert task.refresh_round(config)
    task.ensure_retreat_four.assert_called_once_with(config)
    task.check_refresh.assert_called_once_with()
    assert not task.round_retreat_done


def test_refresh_round_keeps_state_when_refresh_is_unavailable():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.check_refresh = Mock(return_value=False)
    task.round_retreat_done = True

    assert not task.refresh_round(make_config())
    assert task.round_retreat_done


def test_three_wins_attacks_first_and_continues_when_other_positions_have_no_failure():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[])
    task.is_first_position_finished = Mock(return_value=False)
    task.refresh_round = Mock()

    assert task.process_three_win_stage(make_config()) == "attack_first"
    task.ensure_retreat_four.assert_called_once()
    task.refresh_round.assert_not_called()


def test_three_wins_continues_clearing_when_only_first_position_failed():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[1])
    task.is_first_position_finished = Mock(return_value=True)
    task.refresh_round = Mock()

    assert task.process_three_win_stage(make_config()) == "continue"
    task.refresh_round.assert_not_called()


def test_three_wins_refreshes_when_another_position_failed():
    task = make_task()
    task.ensure_retreat_four = Mock(return_value=True)
    task.get_failed_positions = Mock(return_value=[1, 4])
    task.is_first_position_finished = Mock()
    task.refresh_round = Mock(return_value=True)
    config = make_config()

    assert task.process_three_win_stage(config) == "refreshed"
    task.refresh_round.assert_called_once_with(config)
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


def test_retreat_four_runs_four_quick_exits():
    task = make_task()
    task.fire = Mock(return_value=True)
    task.build_quick_exit_config = Mock(return_value="quick-exit")
    task.run_general_battle = Mock(return_value=False)
    task.ui_click_until_appear_or_timeout = Mock(return_value=True)
    config = make_config()

    assert task.retreat_four_at_first(config)
    assert task.fire.call_count == 4
    task.fire.assert_called_with(1)
    assert task.run_general_battle.call_count == 4
    task.run_general_battle.assert_called_with(config="quick-exit")
    assert task.ui_click_until_appear_or_timeout.call_count == 4
