from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config_model import ConfigModel
from tasks.CustomTask.config import ENTRY_PREFIX
from tasks.MetaDemon.config import MetaDemonMode
from tasks.MetaDemon.script_task import ScriptTask


def mode_field(model, task):
    return next(row for row in model.script_task(task)['meta_demon_config'] if row['name'] == 'mode')


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setattr(ConfigModel, 'save', Mock())
    return ConfigModel()


@pytest.mark.parametrize('mode', list(MetaDemonMode))
def test_mode_dropdown_saves_and_dispatches_the_selected_mode(model, monkeypatch, mode):
    field = mode_field(model, 'MetaDemon')
    assert field['type'] == 'enum'
    assert field['value'] == MetaDemonMode.BOSS_BATTLE.value
    assert field['default'] == MetaDemonMode.BOSS_BATTLE.value
    assert field['enumEnum'] == [item.value for item in MetaDemonMode]
    assert 'ui_exclusive_groups' not in field

    assert model.script_set_arg('MetaDemon', 'meta_demon_config', 'mode', mode.value)
    assert mode_field(model, 'MetaDemon')['value'] == mode.value
    assert model.meta_demon.meta_demon_config.model_dump(mode='json')['mode'] == [mode.value]
    restored = ConfigModel.model_validate_json(model.model_dump_json())
    assert mode_field(restored, 'MetaDemon')['value'] == mode.value

    battle, assistance = Mock(return_value='battle'), Mock(return_value='assistance')
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.BossBattle.run', battle)
    monkeypatch.setattr('tasks.MetaDemon.assistance.run_assistance', assistance)
    task = object.__new__(ScriptTask)
    task.config = SimpleNamespace(meta_demon=restored.meta_demon)
    assert task.run() == ('assistance' if mode == MetaDemonMode.BOSS_ASSIST else 'battle')
    assert battle.call_count == int(mode == MetaDemonMode.BOSS_BATTLE)
    assert assistance.call_count == int(mode == MetaDemonMode.BOSS_ASSIST)


@pytest.mark.parametrize('task_name', ['CustomTask', 'entry'])
def test_custom_task_mode_dropdown_updates_only_its_own_entry(model, task_name):
    model.custom_task.add('MetaDemon')
    entry = model.custom_task.selected_entry
    task_name = ENTRY_PREFIX + entry.id if task_name == 'entry' else task_name
    assert mode_field(model, task_name)['type'] == 'enum'

    assert model.script_set_arg(task_name, 'meta_demon_config', 'mode', '鬼王协助')
    assert mode_field(model, task_name)['value'] == '鬼王协助'
    assert entry.settings['meta_demon_config']['mode'] == ['鬼王协助']
    assert model.meta_demon.meta_demon_config.mode == [MetaDemonMode.BOSS_BATTLE]


def test_invalid_mode_is_rejected_without_changing_saved_selection(model):
    before = model.meta_demon.model_dump()
    assert not model.script_set_arg('MetaDemon', 'meta_demon_config', 'mode', '不存在的模式')
    assert not model.script_set_arg('MetaDemon', 'meta_demon_config', 'mode', '["鬼王战斗", "鬼王协助"]')
    assert model.meta_demon.model_dump() == before


def test_empty_legacy_mode_is_not_implicitly_enabled(model):
    model.meta_demon.meta_demon_config.mode = []
    assert mode_field(model, 'MetaDemon')['value'] == ''
    assert model.meta_demon.meta_demon_config.mode == []
