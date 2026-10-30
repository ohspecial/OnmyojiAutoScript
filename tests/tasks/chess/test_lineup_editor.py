"""阵容存储、编辑器接口和对局快照的离线回归检查。"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from module.config.config_model import ConfigModel
from module.server import chesslineup_router as router
from tasks.Chess.config import ChessConfig
from tasks.Chess.runtime.activity_watchdog import ChessActivityWatchdog
from tasks.Chess.script_task import ScriptTask
from tasks.Chess.strategy import custom_lineups as storage
from tasks.Chess.strategy.lineup import LineupBond, oasx_lineup_choices
from tasks.Chess.strategy.lineup_loader import LINEUPS_FILE, load_lineup_registry


@pytest.fixture
def document():
    slots = [{} for _ in range(12)]
    slots[0] = {'shikigami': 'kaoru', 'equipment': [{'kind': 'soul', 'key': 'wangliangzhixia'}]}
    return {'key': 'test_lineup', 'display_name': '测试阵容', 'slots': slots}


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / 'custom_lineups.json'
    monkeypatch.setattr(storage, 'STORE', path)
    return path


@pytest.mark.parametrize('invalid', ['duplicate', 'unknown', 'empty_equipment', 'own_emblem'])
def test_invalid_lineup_is_rejected(document, invalid):
    if invalid == 'duplicate':
        document['slots'][1] = document['slots'][0]
    elif invalid == 'unknown':
        document['slots'][0]['shikigami'] = 'unknown'
    elif invalid == 'empty_equipment':
        document['slots'][1] = {'equipment': [{'kind': 'soul', 'key': 'wangliangzhixia'}]}
    else:
        document['slots'][0]['equipment'] = [{'kind': 'emblem', 'key': 'qijiaoshan'}]
    with pytest.raises(ValidationError):
        storage.CustomLineup.model_validate(document)


def test_custom_storage_round_trip_and_duplicate_protection(document, store):
    lineup = storage.CustomLineup.model_validate(document)
    storage.save_lineup(lineup)
    assert storage.load_strategy(lineup.key)['shikigami']['kaoru']['preferred_souls'] == ('wangliangzhixia',)
    with pytest.raises(FileExistsError):
        storage.save_lineup(lineup, overwrite=False)
    assert not store.with_suffix('.tmp').exists()
    storage.delete_lineup(lineup.key)
    assert storage.read_lineups() == {}


def test_version_one_migration_keeps_backup(store):
    original = json.dumps({'version': 1, 'lineups': [{
        'key': 'old_lineup', 'display_name': '旧阵容',
        'shikigami_positions': {'薰': [1, 1, []]},
    }]}, ensure_ascii=False).encode('utf-8')
    store.write_bytes(original)
    assert storage.read_lineups()['old_lineup']['slots'][0]['shikigami'] == 'kaoru'
    assert store.with_suffix('.v1.bak.json').read_bytes() == original
    assert json.loads(store.read_text(encoding='utf-8'))['version'] == 2


def test_haiguo_keeps_legacy_selection_and_physical_positions():
    registry = load_lineup_registry()
    assert ChessConfig(lineup_bond='海国').lineup_bond == LineupBond.HAIGUO
    strategy = registry['haiguo']['strategy']
    assert strategy['display_name'] == '海国'
    assert strategy['shikigami']['umi_no_Chou']['position'] == 1
    assert strategy['shikigami']['kanihime']['position'] == 7


def test_dynamic_oasx_choices_save_stable_identity(document, store, monkeypatch):
    storage.save_lineup(storage.CustomLineup.model_validate(document))
    model = ConfigModel()
    monkeypatch.setattr(ConfigModel, 'save', Mock())
    label = next(label for label, key in oasx_lineup_choices().items() if key == 'custom:test_lineup')
    assert model.script_set_arg('Chess', 'chess_config', 'lineup_bond', label)
    assert model.chess.chess_config.custom_lineup == 'custom:test_lineup'
    groups = model.script_task('Chess')['chess_config']
    choice = next(item for item in groups if item['name'] == 'lineup_bond')
    assert choice['value'] == label
    assert not any(item['name'] == 'custom_lineup' for item in groups)
    assert not model.chess.select_oasx_lineup('custom:missing')


def test_running_game_keeps_snapshot_until_next_selection(document, store):
    storage.save_lineup(storage.CustomLineup.model_validate(document))
    task = object.__new__(ScriptTask)
    task.select_lineup_strategy('custom:test_lineup')
    document['display_name'] = '已修改'
    storage.save_lineup(storage.CustomLineup.model_validate(document))
    assert task.get_lineup_strategy()['display_name'] == '测试阵容'
    assert task.select_lineup_strategy('custom:test_lineup')['display_name'] == '已修改'


def test_catalog_images_exist_and_builtin_documents_validate():
    catalog = asyncio.run(router.catalog())
    static = router.WEB / 'static'
    for kind in ('shikigami', 'soul', 'emblem'):
        for item in catalog[kind]:
            assert (static / Path(item['image']).relative_to('/tool/chesslineup/static')).is_file(), item['image']
    assert (static / 'cards/special_hakuzosu_protect.webp').is_file()
    assert len(load_lineup_registry()) == 4


def test_editor_refuses_to_delete_referenced_lineup(document, store, tmp_path, monkeypatch):
    storage.save_lineup(storage.CustomLineup.model_validate(document))
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    (config_dir / 'example.json').write_text(json.dumps({
        'chess': {'chess_config': {'lineup_bond': '自定义阵容', 'custom_lineup': 'custom:test_lineup'}},
    }), encoding='utf-8')
    monkeypatch.setattr(router, 'ROOT', tmp_path)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.remove('custom', 'test_lineup'))
    assert error.value.status_code == 409
    assert storage.read_lineups()['test_lineup']


def test_apply_rejects_path_traversal_before_loading_config(document, store):
    storage.save_lineup(storage.CustomLineup.model_validate(document))
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.apply(router.ApplyBody(key='test_lineup', script='../example')))
    assert error.value.status_code == 400


def test_boss_and_normal_positions_use_anchored_click_ranges():
    task = object.__new__(ScriptTask)
    task.appear = Mock(return_value=True)
    for boss, expected in [(False, (377, 398)), (True, (347, 392))]:
        task._is_boss_challenge_round = Mock(return_value=boss)
        assert task._set_position(1) == expected
        assert task._soul_target_position(1) == (expected[0], expected[1] - 5)
    task.appear.return_value = False
    from module.exception import GameStuckError
    with pytest.raises(GameStuckError):
        task._set_position(1)


def test_missing_board_anchor_never_confirms_recall():
    task = object.__new__(ScriptTask)
    task._board_frame_scan = Mock(return_value=[])
    assert not task._board_set_has_shikigami(1)
    assert not task._board_set_is_empty(1)


@pytest.mark.parametrize('boss', [False, True])
def test_board_scan_tracks_shifted_anchor_stars_and_frame_cache(boss):
    task = object.__new__(ScriptTask)
    task._is_boss_challenge_round = Mock(return_value=boss)
    frame = task.F_BOSS_BOARD_OCCUPANCY if boss else task.F_BOARD_OCCUPANCY
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    dx, dy = 11, -7
    x, y, width, height = frame.badge_references[0]
    image[y+dy:y+dy+height, x+dx:x+dx+width] = frame.image
    rules = [SimpleNamespace(image=rng.integers(0, 256, (6, 6, 3), dtype=np.uint8)) for _ in range(3)]
    task.board_occupancy_rules = rules
    x, y, _, _ = frame.roi_ranges[0]
    image[y+dy:y+dy+6, x+dx:x+dx+6] = rules[1].image
    task.device = SimpleNamespace(image=image, image_frame_id='scan-1')
    task.appear = Mock(side_effect=lambda target, **_: target.match(image))
    task.click = Mock()
    slots = task._board_frame_scan()
    assert len(slots) == 12
    assert slots[0]['occupied'] and slots[0]['star'] == 2
    assert not any(slot['occupied'] for slot in slots[1:])
    assert task._board_frame_scan() is slots
    assert task.appear.call_count == 1
    x, y, width, height = frame.roi_ranges[12]
    assert task._set_position(1) == (x + dx + width // 2, y + dy + height // 2)
    task.device.image_frame_id = 'scan-2'
    assert task._board_frame_scan() is not slots
    task.click.assert_not_called()


def test_watchdog_restores_existing_profile_on_exit():
    import sys
    before = sys.getprofile()
    with ChessActivityWatchdog(timeout=300) as watchdog:
        assert watchdog.thread.is_alive()
    assert sys.getprofile() is before
    assert not watchdog.thread.is_alive()
