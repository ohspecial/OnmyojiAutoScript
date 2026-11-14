from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config_model import ConfigModel
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType, MetaDemon, MetaDemonConfig


@pytest.mark.parametrize('sequence,expected', [
    ('1 2 3 4', [1, 2, 3, 4]),
    ('3 2', [3, 2]),
    ('6 5', [6, 5]),
    (' 6  3\t2\n', [6, 3, 2]),
    ('', []),
])
def test_configured_stars_keep_the_entered_order(sequence, expected):
    assert MetaDemonConfig(fire_sequence=sequence).fire_sequence_v == expected


@pytest.mark.parametrize('settings,expected', [
    ({'fire_sequence': '3 2'}, '3 2'),
    ({'fire_sequence': '6 5', 'dynamic_star_level': True}, '6 5'),
    ({'dynamic_star_level': True}, '1 2 3 4'),
    ({'dynamic_star_level': False}, '1 2 3 4'),
])
def test_profiles_preserve_custom_order_and_discard_dynamic_mode(settings, expected):
    legacy = {'meta_demon': {'meta_demon_config': settings.copy()}}
    model = ConfigModel(**legacy)

    assert legacy['meta_demon']['meta_demon_config'] == settings
    restored = MetaDemon.model_validate_json(model.meta_demon.model_dump_json())
    assert restored.meta_demon_config.fire_sequence == expected
    assert 'dynamic_star_level' not in restored.meta_demon_config.model_dump()
    fields = {row['name']: row for row in model.script_task('MetaDemon')['meta_demon_config']}
    assert fields['fire_sequence']['value'] == expected
    assert 'dynamic_star_level' not in fields


@pytest.fixture
def summon_task(monkeypatch):
    ticks = iter(index * 0.1 for index in range(1000))
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.time.monotonic', lambda: next(ticks))

    def make(fatigue, available, *, sequence='1 2 3 4'):
        task = object.__new__(BossBattle)
        task.conf = MetaDemon(meta_demon_config={'fire_sequence': sequence})
        task.State = SimpleNamespace(done=False)
        task.cur_boss_type = None
        task.current_count = 0
        task.device = SimpleNamespace(image=object())
        task.O_MD_FATIGUE = SimpleNamespace(
            ocr_digit_counter=Mock(return_value=(fatigue, 100 - fatigue, 100)),
        )
        task.I_MD_CHECK_SELECTED = SimpleNamespace(roi_front=(0, 0, 0, 0))
        tickets = {BossType(star): getattr(task, 'I_MD_' + name) for star, name in enumerate(
            ('ONE_STAR', 'TWO_STARS', 'THREE_STARS', 'FOUR_STARS', 'FIVE_STARS', 'SIX_STARS'), 1)}
        state = {'selected': False, 'summoned': False}
        task.screenshot = Mock()
        task.ticket_matches_star = Mock(side_effect=lambda rule, star: star in available)
        task.appear = lambda rule: (
            (rule is task.I_MD_FIRE and state['summoned'])
            or rule is task.I_MD_GET_BOSS
            or (rule is task.I_MD_CHECK_SELECTED and state['selected'])
        )

        def select(rule, **kwargs):
            assert any(rule is ticket for ticket in tickets.values())
            x, y, width, _ = rule.roi_front
            task.I_MD_CHECK_SELECTED.roi_front = (x + width / 2, y, 0, 0)
            state['selected'] = True

        def confirm(rule, **kwargs):
            if rule is task.I_MD_CLOSE_POPUP:
                return True
            assert rule is task.I_MD_GET_BOSS
            state['summoned'] = True
            return True

        task.click = Mock(side_effect=select)
        task.appear_then_click = Mock(side_effect=confirm)
        return task

    return make


@pytest.mark.parametrize('fatigue,available,sequence,expected', [
    (49, {1, 2, 3, 4, 5, 6}, '3 2', 3),
    (50, {1, 2, 3, 4, 5, 6}, '3 2', 3),
    (100, {1, 2, 3, 4, 5, 6}, '3 2', 3),
    (70, {1, 2, 5, 6}, '3 2', 2),
    (70, {1, 2, 5, 6}, '1 2 3 4', 1),
    (10, {1, 5, 6}, '6 5', 6),
    (70, {1, 5}, '6 5', 5),
])
def test_actual_summon_uses_custom_order_at_any_fatigue(summon_task, fatigue, available, sequence, expected):
    task = summon_task(fatigue, available, sequence=sequence)

    assert task.check_fatigue()
    assert task.check_and_switch_ticket()
    assert task.cur_boss_type == BossType(expected)
    assert not task.State.done


@pytest.mark.parametrize('sequence,available', [
    ('3 2', {1, 5, 6}),
    ('1 2 3 4', {5, 6}),
    ('', {1, 2, 3, 4, 5, 6}),
])
def test_unselected_stars_are_not_summoned_when_requested_tickets_run_out(summon_task, sequence, available):
    task = summon_task(70, available, sequence=sequence)

    assert not task.check_and_switch_ticket()
    assert task.State.done
    task.click.assert_not_called()
    task.appear_then_click.assert_called_once_with(task.I_MD_CLOSE_POPUP, interval=0.8)


def test_existing_boss_is_finished_without_selecting_another_ticket(summon_task):
    task = summon_task(70, {1, 2}, sequence='3 2')
    task.cur_boss_type = BossType.SIX_STARS
    task.appear = lambda rule: rule is task.I_MD_FIRE

    assert task.check_and_switch_ticket()
    assert task.cur_boss_type == BossType.SIX_STARS
    task.ticket_matches_star.assert_not_called()
    task.click.assert_not_called()


def test_explicit_six_star_offering_overrides_battle_order(summon_task):
    task = summon_task(10, {1, 5, 6})

    assert task.check_fatigue()
    assert task.check_and_switch_ticket(sequence=(BossType.SIX_STARS,))
    assert task.cur_boss_type == BossType.SIX_STARS


def test_failed_fatigue_ocr_does_not_prepare_or_summon(summon_task):
    task = summon_task(70, {1, 5, 6})
    assert task.check_fatigue()
    task.O_MD_FATIGUE.ocr_digit_counter.return_value = (0, 0, 0)

    task.synthesis_boss_ticket = Mock()
    task.check_and_switch_ticket = Mock()
    assert not task.check_and_prepare_battle()
    task.synthesis_boss_ticket.assert_not_called()
    task.check_and_switch_ticket.assert_not_called()
    task.click.assert_not_called()
    task.appear_then_click.assert_not_called()
    assert not task.State.done
