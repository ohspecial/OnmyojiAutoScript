from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config import Config
from module.exception import TaskEnd
from tasks.GameUi.page import page_main
from tasks.MemoryScrolls.config import MemoryScrolls
from tasks.MemoryScrolls.script_task import ScriptTask


def make_task(success_minutes, *, entry_available=True):
    memory_scrolls = MemoryScrolls(
        scheduler={
            'enable': True,
            'success_interval': f'00 00:{success_minutes:02d}:00',
            'failure_interval': '01 00:00:00',
        },
        memory_scrolls_finish={'auto_finish_exploration': True},
    )
    # 使用真实调度计算，但隔离配置读写，避免测试生成或改写账号文件。
    config = object.__new__(Config)
    config.model = SimpleNamespace(memory_scrolls=memory_scrolls)
    config.reload = Mock()
    config.save = Mock()

    task = object.__new__(ScriptTask)
    task.config = config
    task.start_time = datetime(2026, 11, 13, 9, 11, 8)
    task.wait_until_appear = Mock(return_value=entry_available)
    task.screenshot = Mock()
    task.appear = Mock(side_effect=lambda rule: rule is task.I_MS_FRAGMENT_S)
    task.ui_click = Mock()
    task.ui_click_until_disappear = Mock()
    task.goto_page = Mock()
    task.goto_scroll = Mock()
    task.custom_next_run = Mock()
    return task


@pytest.mark.parametrize('success_minutes', [5, 11])
def test_below_daily_quota_rechecks_after_configured_success_interval(success_minutes):
    task = make_task(success_minutes)

    with pytest.raises(TaskEnd):
        task.run()

    scheduler = task.config.memory_scrolls.scheduler
    assert scheduler.next_run == task.start_time + timedelta(minutes=success_minutes)
    assert scheduler.enable
    task.goto_page.assert_called_with(page_main)
    task.goto_scroll.assert_not_called()
    task.custom_next_run.assert_not_called()
    task.config.save.assert_called_once()


def test_missing_memory_scrolls_entry_keeps_failure_interval():
    task = make_task(5, entry_available=False)

    with pytest.raises(TaskEnd):
        task.run()

    assert task.config.memory_scrolls.scheduler.next_run == task.start_time + timedelta(days=1)
    task.goto_scroll.assert_not_called()
    task.custom_next_run.assert_not_called()
    task.config.save.assert_called_once()
