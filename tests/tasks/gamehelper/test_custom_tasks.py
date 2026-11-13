import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config_manual import ConfigManual
from module.config.config_menu import ConfigMenu
from module.config.config_model import ConfigModel
from module.exception import TaskEnd
from tasks.CustomTask.config import CustomTaskEntry, ENTRY_PREFIX
from tasks.CustomTask.script_task import EntryConfig, ScriptTask


@pytest.fixture
def model(monkeypatch):
    # 配置设置接口会自动保存；测试只使用内存模型。
    monkeypatch.setattr(ConfigModel, 'save', Mock())
    return ConfigModel()


def test_new_helpers_are_registered_and_disabled_for_existing_profiles(model):
    template = json.loads(Path('config/template.json').read_text(encoding='utf-8'))
    names = ConfigMenu().menu['gamehelper']
    assert names == ['AutoStory', 'ExplorationFight', 'CustomTask']
    for name in names:
        assert name in ConfigManual.SCHEDULER_PRIORITY
        key = {'AutoStory': 'auto_story', 'ExplorationFight': 'exploration_fight', 'CustomTask': 'custom_task'}[name]
        assert not getattr(model, key).scheduler.enable
        assert not template[key]['scheduler']['enable']
        assert 'scheduler' in model.script_task(name)


def test_repeated_entries_have_independent_settings_and_order_controls(model):
    assert model.script_set_arg('CustomTask', 'task_list', 'add_task', '探索')
    first = model.custom_task.selected_entry
    assert model.script_set_arg('CustomTask', 'exploration_config', 'minions_cnt', 3)
    assert model.script_set_arg('CustomTask', 'task_list', 'add_task', '探索')
    second = model.custom_task.selected_entry
    assert model.script_set_arg('CustomTask', 'exploration_config', 'minions_cnt', 7)
    assert first.settings['exploration_config']['minions_cnt'] == 3
    assert second.settings['exploration_config']['minions_cnt'] == 7
    assert model.exploration.exploration_config.minions_cnt == 30
    assert model.script_set_arg('CustomTask', 'task_list', 'entry_action', '上移')
    assert [entry.id for entry in model.custom_task.entries] == [second.id, first.id]
    assert 'scheduler' not in model.script_task(ENTRY_PREFIX + first.id)
    payload = model.script_task('CustomTask')
    assert next(row for row in payload['exploration_config'] if row['name'] == 'minions_cnt')['value'] == 7
    snapshot = model.custom_task.model_dump()
    assert not model.script_set_arg('CustomTask', 'exploration_config', 'minions_cnt', -1)
    assert model.custom_task.model_dump() == snapshot


def test_entry_configuration_captures_extra_scheduling_without_touching_parent(model):
    entry = CustomTaskEntry(type='Exploration', settings={'exploration_config': {'minions_cnt': 3}})
    parent = SimpleNamespace(model=model, task_delay=Mock(), save=Mock())
    snapshot = model.model_dump()
    config = EntryConfig(parent, entry, entry.task_model())
    config.exploration.exploration_config.minions_cnt = 9
    config.exploration.scheduler.enable = True
    config.task_delay('Exploration', success=True)
    config.task_delay('RealmRaid', success=False)
    config.task_call('MemoryScrolls')
    config.save()
    assert config.success is True
    assert model.model_dump() == snapshot
    parent.task_delay.assert_not_called()
    parent.save.assert_not_called()


def test_sequence_advances_after_child_taskend_and_uses_private_settings(model, monkeypatch):
    model.custom_task.add('Exploration')
    model.custom_task.add('Exploration')
    model.custom_task.entries[0].settings['exploration_config']['minions_cnt'] = 3
    model.custom_task.entries[1].settings['exploration_config']['minions_cnt'] = 7
    observed = []

    class Child:
        def __init__(self, config, device):
            self.config = config

        def run(self):
            observed.append(self.config.exploration.exploration_config.minions_cnt)
            self.config.task_delay('Exploration', success=False)
            raise TaskEnd

    monkeypatch.setattr('tasks.CustomTask.script_task.import_module', lambda path: SimpleNamespace(ScriptTask=Child))
    task = object.__new__(ScriptTask)
    task.config = SimpleNamespace(model=model)
    task.device = Mock()
    task.set_next_run = Mock()
    task.goto_page = Mock()
    with pytest.raises(TaskEnd):
        task.run()
    assert observed == [3, 7]
    task.set_next_run.assert_called_once_with('CustomTask', success=True, finish=True)


def test_account_entry_allows_empty_character_but_rejects_incomplete_account():
    entry = CustomTaskEntry(type='AccountSwitch', settings={'account': {'account': 'test', 'svr': 'test'}})
    assert entry.task_model().account.character == ''
    assert ScriptTask.entry_error(entry) is None
    assert ScriptTask.entry_error(CustomTaskEntry(type='AccountSwitch'))


def test_custom_task_api_preview_is_read_only_and_reorder_errors_preserve_entries(model, monkeypatch):
    from fastapi import HTTPException
    from module.server import script_router as router

    model.custom_task.add('Exploration')
    snapshot = model.model_dump()
    monkeypatch.setattr(router, 'mm', SimpleNamespace(config_cache=lambda name: SimpleNamespace(model=model)))
    preview = asyncio.run(router.change_task_list('test', 'CustomTask', router.TaskListChange(
        action='add', type='RealmRaid', preview=True,
        entries=[entry.model_dump(mode='json') for entry in model.custom_task.entries],
    )))
    assert [entry['type'] for entry in preview['entries']] == ['Exploration', 'RealmRaid']
    payload = asyncio.run(router.preview_custom_task_entry('test', {'type': 'RealmRaid'}))
    assert 'raid_config' in payload and 'scheduler' not in payload
    assert model.model_dump() == snapshot
    with pytest.raises(HTTPException) as failure:
        asyncio.run(router.change_task_list('test', 'CustomTask', router.TaskListChange(action='reorder', ids=['missing'])))
    assert failure.value.status_code == 400
    assert model.model_dump() == snapshot
    model.save.assert_not_called()
