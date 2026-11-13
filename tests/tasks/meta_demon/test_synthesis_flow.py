from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType


def make_task(monkeypatch, frames, *, title='合成二星裂变之眼'):
    task = object.__new__(BossBattle)
    clock = SimpleNamespace(now=0.)
    current = SimpleNamespace(stage='ready')
    sequence = iter(frames)
    task.device = SimpleNamespace(image=current, image_frame_id=0)
    task.submissions = 0
    reads = 0

    def screenshot():
        nonlocal reads
        reads += 1
        assert reads < 150, '合成流程未在限定时间内退出'
        clock.now += .1
        current.stage = next(sequence, current.stage)
        task.device.image_frame_id += 1

    def appear(rule, **kwargs):
        return (
            (rule is task.I_UI_REWARD and current.stage == 'reward')
            or (rule is task.I_MD_SYNTHESIS_NEED_MONEY and current.stage == 'purchase')
            or (rule is task.I_MD_SYNTHESIS_EMPTY and current.stage in ('anim_empty', 'not_enough'))
            or (rule is task.I_MD_START_SYNTHESIS and current.stage in ('ready', 'selected', 'not_enough'))
        )

    def submit(rule, **kwargs):
        assert rule is task.I_MD_START_SYNTHESIS
        assert current.stage == 'selected'
        task.submissions += 1
        return True

    task.screenshot = Mock(side_effect=screenshot)
    task.appear = Mock(side_effect=appear)
    task.click = Mock(return_value=True)
    task.appear_then_click = Mock(side_effect=submit)
    task.ui_click = Mock()
    task.ticket_matches_star = Mock(side_effect=lambda *args, **kwargs: current.stage in ('ready', 'selected', 'not_enough'))
    monkeypatch.setattr(task.O_SYNTHESIS_LEVEL, 'ocr', Mock(return_value=title))
    monkeypatch.setattr(task.I_MD_SYNTHESIS_EMPTY, 'match_all_any', Mock(return_value=[(1, 0, 0, 1, 1)]))
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.time.monotonic', lambda: clock.now)
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    return task, clock


@pytest.mark.parametrize('animation_stage', ['anim_empty', 'anim_bad_star'])
def test_synthesis_waits_out_animation_and_reward_before_next_batch(monkeypatch, animation_stage):
    batch = ['ready', 'selected', animation_stage, animation_stage, 'reward', 'closing', 'ready', 'ready']
    task, _ = make_task(monkeypatch, batch + batch + ['not_enough'])

    task.do_synthesis(task.I_MD_SYNTHESIS_ONE_STAR, 3, BossType.ONE_STAR)

    assert task.submissions == 2
    assert task.O_SYNTHESIS_LEVEL.ocr.call_count == 2
    assert all(call.kwargs.get('synthesis') for call in task.ticket_matches_star.call_args_list)


def test_synthesis_stops_without_resubmitting_when_result_never_arrives(monkeypatch):
    task, clock = make_task(monkeypatch, ['ready', 'selected', 'anim_empty'])

    task.do_synthesis(task.I_MD_SYNTHESIS_ONE_STAR, 3, BossType.ONE_STAR)

    assert task.submissions == 1
    assert clock.now >= 10


def test_paid_ticket_popup_is_closed_without_another_submission(monkeypatch):
    task, _ = make_task(monkeypatch, ['ready', 'selected', 'purchase'])

    task.do_synthesis(task.I_MD_SYNTHESIS_ONE_STAR, 3, BossType.ONE_STAR)

    assert task.submissions == 1
    task.ui_click.assert_called_once_with(task.I_MD_CLOSE_POPUP, task.I_MD_START_SYNTHESIS, interval=.6)


def test_wrong_material_star_never_starts_synthesis(monkeypatch):
    task, _ = make_task(monkeypatch, ['ready', 'selected'], title='合成三星裂变之眼')

    task.do_synthesis(task.I_MD_SYNTHESIS_ONE_STAR, 3, BossType.ONE_STAR)

    assert task.submissions == 0
    task.appear_then_click.assert_not_called()
    assert task.O_SYNTHESIS_LEVEL.ocr.call_count == 3
