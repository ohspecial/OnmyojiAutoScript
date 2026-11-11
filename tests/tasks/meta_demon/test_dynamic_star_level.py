from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config_model import ConfigModel
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType, MetaDemon, MetaDemonConfig


@pytest.mark.parametrize('fatigue,expected', [
    (0, [1, 2, 3, 4, 5, 6]),
    (49, [1, 2, 3, 4, 5, 6]),
    (50, [5, 6, 1, 2, 3, 4]),
    (51, [5, 6, 1, 2, 3, 4]),
    (100, [5, 6, 1, 2, 3, 4]),
])
def test_priority_changes_at_fifty_fatigue(fatigue, expected):
    assert MetaDemonConfig().attack_sequence(fatigue) == expected


@pytest.mark.parametrize('fatigue', [0, 49, 50, 100])
def test_disabled_dynamic_mode_always_uses_ascending_stars(fatigue):
    config = MetaDemonConfig(dynamic_star_level=False)
    assert config.attack_sequence(fatigue) == [1, 2, 3, 4, 5, 6]


def test_existing_profiles_enable_dynamic_mode_without_retaining_old_order():
    legacy = {'meta_demon': {'meta_demon_config': {'fire_sequence': '2 3 4'}}}
    model = ConfigModel(**legacy)

    assert legacy['meta_demon']['meta_demon_config'] == {'fire_sequence': '2 3 4'}
    config = model.meta_demon.meta_demon_config
    assert config.dynamic_star_level
    assert config.attack_sequence(50)[:2] == [BossType.FIVE_STARS, BossType.SIX_STARS]
    assert 'fire_sequence' not in config.model_dump()
    schema = config.model_json_schema()['properties']
    assert 'fire_sequence' not in schema
    assert schema['dynamic_star_level']['title'] == '动态调节鬼王星级'


@pytest.fixture
def summon_task(monkeypatch):
    ticks = iter(index * 0.1 for index in range(1000))
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.time.monotonic', lambda: next(ticks))

    def make(fatigue, available, *, dynamic=True):
        task = object.__new__(BossBattle)
        task.conf = MetaDemon(meta_demon_config={'dynamic_star_level': dynamic})
        task.State = SimpleNamespace(done=False)
        task.cur_boss_type = None
        task.current_count = 0
        task._current_fatigue = None
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
            assert rule is task.I_MD_GET_BOSS
            state['summoned'] = True
            return True

        task.click = Mock(side_effect=select)
        task.appear_then_click = Mock(side_effect=confirm)
        return task

    return make


@pytest.mark.parametrize('fatigue,available,dynamic,expected', [
    (49, {1, 2, 3, 4, 5, 6}, True, 1),
    (50, {1, 2, 3, 4, 5, 6}, True, 5),
    (70, {1, 3, 6}, True, 6),
    (70, {2, 4}, True, 2),
    (70, {1, 5, 6}, False, 1),
])
def test_actual_summon_uses_fatigue_and_available_tickets(summon_task, fatigue, available, dynamic, expected):
    task = summon_task(fatigue, available, dynamic=dynamic)

    assert task.check_fatigue()
    assert task.check_and_switch_ticket()
    assert task.cur_boss_type == BossType(expected)
    assert not task.State.done


def test_explicit_six_star_offering_overrides_dynamic_low_star_preference(summon_task):
    task = summon_task(10, {1, 5, 6})

    assert task.check_fatigue()
    assert task.check_and_switch_ticket(sequence=(BossType.SIX_STARS,))
    assert task.cur_boss_type == BossType.SIX_STARS


def test_failed_fatigue_ocr_discards_previous_reading_and_does_not_summon(summon_task):
    task = summon_task(70, {1, 5, 6})
    assert task.check_fatigue()
    task.O_MD_FATIGUE.ocr_digit_counter.return_value = (0, 0, 0)

    assert not task.check_fatigue()
    assert task._current_fatigue is None
    assert not task.check_and_switch_ticket()
    task.click.assert_not_called()
    task.appear_then_click.assert_not_called()
    assert not task.State.done
