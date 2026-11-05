import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from module.config.config import Config
from module.config.config_menu import ConfigMenu
from module.config.config_model import ConfigModel
from module.cooperation import Cooperation
from module.draft_duel_schedule import CHINA_TIME
from module.exception import GamePageUnknownError, TaskEnd
from script import Script
from tasks.DraftDuel.assets import DraftDuelAssets
from tasks.DraftDuel.config import DraftDuel
from tasks.DraftDuel.script_task import ScriptTask
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import page_town


def test_existing_profiles_get_the_task_disabled_and_template_matches():
    model = ConfigModel(config_name='offline-test', running_task='')
    assert not model.draft_duel.scheduler.enable
    assert 'DraftDuel' in ConfigMenu().menu['Weekly Task']
    assert set(model.script_task('DraftDuel')) == {'scheduler', 'draft_duel_config', 'invite_config'}
    template = json.loads(Path('config/template.json').read_text(encoding='utf-8'))
    assert template['draft_duel'] == model.draft_duel.model_dump(mode='json')


def test_script_skips_closed_hours_before_accessing_the_device(monkeypatch):
    now = datetime(2026, 11, 6, 23, tzinfo=CHINA_TIME)  # 周五结束，下次是周六八点。
    monkeypatch.setattr('module.draft_duel_schedule.draft_duel_now', lambda: now)
    runner = Script('offline-test')
    runner.config = SimpleNamespace(model=SimpleNamespace(draft_duel=DraftDuel()), task_delay=Mock())
    runner.device = Mock()
    assert runner.run('DraftDuel')
    assert runner.device.mock_calls == []
    assert runner.last_task_runtime_outcome['status'] == 'time_window_skipped'
    opening = datetime(2026, 11, 7, 8, tzinfo=CHINA_TIME).astimezone().replace(tzinfo=None)
    runner.config.task_delay.assert_called_once_with(task='DraftDuel', target=opening, server=False)


@pytest.mark.parametrize('exit_state', ['arrived', 'courtyard', 'leave_timeout', 'invite_timeout_navigation_failed'])
def test_finished_task_persists_next_run_even_when_leaving_fails(tmp_path, monkeypatch, exit_state):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'config').mkdir()
    file = tmp_path / 'config' / 'offline-test.json'
    started = datetime.now().replace(microsecond=0) - timedelta(minutes=10)
    item = DraftDuel(scheduler={'enable': True, 'next_run': started})
    file.write_text(json.dumps({'draft_duel': item.model_dump(mode='json')}), encoding='utf-8')
    task = object.__new__(ScriptTask)
    task.config = Config('offline-test')
    task.config.notifier = Mock()
    task.device = Mock()
    task.screenshot = Mock()
    task._publish_draft_abort = Mock()
    task._finalize_round_stats = Mock()
    task._clear_draft_checkpoint = Mock()
    visible = {'arrived': GameUiAssets.I_CHECK_TOWN, 'courtyard': GameUiAssets.I_CHECK_MAIN}.get(exit_state)
    task.appear = Mock(side_effect=lambda rule: rule is visible)
    task.goto_page = Mock(return_value=True)
    exit_click = Mock()
    monkeypatch.setattr('tasks.DraftDuel.runtime.cleanup.handle_draft_duel_exit', exit_click)
    clock = SimpleNamespace(monotonic=Mock(side_effect=[0, 31 if exit_state == 'leave_timeout' else 1]))
    monkeypatch.setattr('tasks.DraftDuel.runtime.cleanup.time', clock)

    class FinishClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return started + timedelta(minutes=10)

    monkeypatch.setattr('tasks.base_task.datetime', FinishClock)
    if exit_state == 'invite_timeout_navigation_failed':
        task.goto_page.side_effect = GamePageUnknownError('町中未确认')
        with pytest.raises(GamePageUnknownError, match='町中未确认'):
            task._finish_wait_timeout('等待邀请过久', '测试')
    else:
        message = '离队返回町中未确认' if exit_state == 'leave_timeout' else '已离队返回町中'
        with pytest.raises(TaskEnd, match=message):
            task._leave_draft_team('已完成1大轮协斗')
    if exit_state == 'courtyard':
        task.goto_page.assert_called_once_with(page_town, timeout=10)
        exit_click.assert_not_called()

    saved = Config('offline-test')
    expected = FinishClock.now() + timedelta(days=1)
    assert saved.draft_duel.scheduler.next_run == expected
    saved.update_scheduler()
    assert [entry.next_run for entry in saved.waiting_task if entry.command == 'DraftDuel'] == [expected]
    # 队员不会因旧时间已到期而马上重跑并唤醒队长。
    assert all(entry.command != 'DraftDuel' for entry in saved.pending_task)


def test_missing_roster_uses_failure_interval(monkeypatch):
    monkeypatch.setattr('tasks.DraftDuel.script_task.require_draft_duel_hours', Mock())
    task = object.__new__(ScriptTask)
    task.config = Mock()
    task._initialize_duel_state = Mock()
    task._save_draft_checkpoint = Mock()
    task._enter_matchmaking = Mock(return_value=True)
    task._select_shikigami = Mock(return_value=True)
    task._match_battle = Mock(return_value=True)
    task._deploy_shikigami = Mock(return_value=True)
    task._battle_and_settlement = Mock(return_value='rank')
    task.draft_selected = []
    task.start_time = datetime.now().replace(microsecond=0)
    with pytest.raises(TaskEnd, match='缺少本轮五名式神记录'):
        task.run()
    task.config.task_delay.assert_called_once_with(
        'DraftDuel', start_time=task.start_time, success=False, server=True, target=None)


def test_partner_wake_is_taken_at_the_scheduler_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr('module.draft_duel_schedule.draft_duel_now',
                        lambda: datetime(2026, 11, 6, 12, tzinfo=CHINA_TIME))
    (tmp_path / 'config').mkdir()
    items = {
        name: DraftDuel(scheduler={'enable': True}, draft_duel_config={'match_mode': mode},
                        invite_config={'cooperation_script': peer})
        for name, mode, peer in (('A', '队长', 'B'), ('B', '队员', 'A'))
    }
    for name, item in items.items():
        (tmp_path / 'config' / f'{name}.json').write_text(
            json.dumps({'draft_duel': item.model_dump(mode='json')}), encoding='utf-8')
    captain, member = Cooperation('A', tmp_path), Cooperation('B', tmp_path)
    captain.publish('DraftDuel')
    member.publish('')
    captain_config = SimpleNamespace(model=SimpleNamespace(draft_duel=items['A']))
    captain.prepare(captain_config, 'DraftDuel', 'B')

    runner = Script('B')
    runner._cooperation = member
    earlier = datetime.now() - timedelta(seconds=1)
    draft = SimpleNamespace(command='DraftDuel', next_run=earlier)
    other = SimpleNamespace(command='Duel', next_run=earlier)
    runner.config = SimpleNamespace(
        model=SimpleNamespace(draft_duel=items['B']),
        script=SimpleNamespace(anti_ban=None, optimization=SimpleNamespace(task_hoarding_duration=0)),
        reload=Mock(), task_call=Mock(return_value=True), get_next=Mock(return_value=other),
        pending_task=[other, draft],
    )
    runner.anti_ban_guard = Mock()
    runner.anti_ban_guard.wake_time.return_value = None
    assert runner.get_next_task() == 'DraftDuel'
    runner.config.task_call.assert_called_once_with('DraftDuel', force_call=False)
    assert member.requested() == []


def test_real_cross_rule_ignores_card_art_and_rejects_a_blank_frame():
    rule = deepcopy(DraftDuelAssets.I_HAND_SELECTED_CROSS)
    template, mask = rule.image, rule._template_mask > 0
    assert not rule.match(np.zeros((720, 1280, 3), dtype=np.uint8))
    frame = np.random.default_rng(42).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    x, y = 522, 510
    height, width = template.shape[:2]
    frame[y:y + height, x:x + width][mask] = template[mask]
    assert rule.match(frame)
    assert rule.roi_front == [x, y, width, height]
