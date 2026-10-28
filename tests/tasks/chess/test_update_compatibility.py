"""棋局上游更新与本地识别、配置和导航接口的离线兼容检查。"""

import ast
import importlib
import inspect
from datetime import datetime, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

import tasks.base_task as base_task
from module.atom.click import RuleClick
from module.atom.frame import Click, Image, RuleFrame
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.device.device import Device
from tasks.Chess.assets import ChessAssets
from tasks.Chess.config import ChessConfig
from tasks.Chess.runtime.press_and_drag import Press_and_Drag
from tasks.Chess.runtime.state import ChessGameState
from tasks.Chess.script_task import ScriptTask
from tasks.Chess.strategy.lineup import LineupBond
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import page_chess_battle, page_chess_result
from tasks.GlobalGame.assets import GlobalGameAssets


@pytest.mark.parametrize('old_lineup', [
    '荒川', '流火', '冥府', '大江山', '狐妖',
    'arakawa', 'liuhuo', 'mingfu', 'dajiangshan', 'huyao',
])
def test_old_lineups_migrate_without_resetting_task_options(old_lineup):
    config = ChessConfig(lineup_bond=old_lineup, run_count=5, coin_full_exit=True)
    assert config.lineup_bond == LineupBond.QIJIAOSHAN
    assert config.run_count == 5
    assert config.coin_full_exit is True
    assert config.hyakki_draft_enabled is True


@pytest.mark.parametrize('lineup', list(LineupBond))
def test_current_lineups_keep_their_selection(lineup):
    assert ChessConfig(lineup_bond=lineup.value).lineup_bond == lineup


@pytest.mark.parametrize('grayscale', [False, True])
def test_frame_rebases_ranges_and_clicks_only_when_requested(tmp_path, monkeypatch, grayscale):
    rng = np.random.default_rng(42)
    badge = rng.integers(0, 256, (6, 8, 3), dtype=np.uint8)
    wrong = rng.integers(0, 256, (6, 8, 3), dtype=np.uint8)
    image = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
    image[12:18, 21:29] = badge
    files = []
    for name, pixels in [('wrong', wrong), ('badge', badge)]:
        path = tmp_path / (name + '.png')
        path.write_bytes(cv2.imencode('.png', cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR))[1].tobytes())
        files.append(str(path))
    frame = RuleFrame(
        name='test_frame', roi_badge=(2, 3, 8, 6),
        roi_range=[(2, 3, 8, 6), (10, 3, 5, 5)], roi_back=(0, 0, 50, 40),
        badgefile=files, threshold=.99, badge_grayscale=grayscale,
        range=[Click(), Image()],
    )
    task = object.__new__(base_task.BaseTask)
    task.device = SimpleNamespace(image=image, image_frame_id='test-frame')
    task.interval_timer = {}
    task.click = Mock()
    # Frame 的多徽标和灰度匹配不能误用旧图像服务或其批量缓存。
    monkeypatch.setattr(base_task, 'get_image_client', Mock(side_effect=AssertionError('unexpected RPC')))
    task.prepare_appear_cache([frame])
    result = task.runframe(frame)
    assert result
    assert frame.badge_index == 1
    assert result[0] == (21, 12, 8, 6)
    np.testing.assert_array_equal(result[1], image[12:17, 29:34])
    task.click.assert_not_called()
    assert task.runframe(frame, True)
    task.click.assert_called_once()


@pytest.mark.parametrize('finished_at, server_update, expected', [
    (datetime(2026, 10, 24, 21, 30), time(9), datetime(2026, 10, 26, 21, 30)),
    (datetime(2026, 10, 24, 21, 30), time(6), datetime(2026, 10, 26, 6)),
    (datetime(2026, 10, 26, 8), time(6), datetime(2026, 11, 2, 6)),
])
def test_weekly_coin_limit_schedules_next_monday(monkeypatch, finished_at, server_update, expected):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls):
            return finished_at

    monkeypatch.setattr(base_task, 'datetime', FrozenDateTime)
    task = object.__new__(base_task.BaseTask)
    task.set_next_run = Mock()
    task.set_next_run_next_monday('Chess', SimpleNamespace(server_update=server_update))
    task.set_next_run.assert_called_once_with(task='Chess', server=False, target=expected)


def test_chess_navigation_recognizes_selection_and_specific_results():
    task = SimpleNamespace(appear=lambda target: target is ChessAssets.I_SELECT_SIXREALMS)
    assert page_chess_battle.recognizer.evaluate(task)
    for marker in (ChessAssets.I_SHARE, GameUiAssets.I_CHECK_CHESS_RANK):
        task.appear = lambda target: target is marker
        assert page_chess_result.recognizer.evaluate(task)
    task.appear = lambda target: target is GlobalGameAssets.I_UI_REWARD
    assert not page_chess_result.recognizer.evaluate(task)


def test_reference_libraries_and_dynamic_templates_load():
    task = object.__new__(ScriptTask)
    assert task.frame_card_library['cards']['card']
    assert task.frame_portraits['card']
    assert task.frame_portraits['store']
    assert task.frame_emblem_library['entries']
    assert task.frame_emblem_portraits
    assert all(task.frame_badges.values())
    rules = [value for value in vars(ChessAssets).values() if isinstance(value, RuleImage)]
    rules.extend(value for name, value in vars(GameUiAssets).items()
                 if isinstance(value, RuleImage) and ('CHESS' in name or name == 'I_CLOSE_RED'))
    rules.extend(task.board_occupancy_rules)
    rules.append(task.hakuzosu_protect_rule)
    rules.extend(rule for _, rule in task.soul_hand_rules)
    for rule in rules:
        assert Path(rule.file).is_file(), rule.file
        assert rule.image.size, rule.file


def test_imported_mixins_have_their_runtime_helpers():
    missing = set()
    incompatible = []
    instance = object.__new__(ScriptTask)
    paths = [*Path('tasks/Chess').rglob('*.py'), Path('tasks/GameUi/chess_battle.py')]
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith(('Mixin', 'ScriptTask')):
                continue
            for call in ast.walk(node):
                if (isinstance(call, ast.Attribute) and isinstance(call.value, ast.Name)
                        and call.value.id == 'self' and call.attr.isupper()
                        and not hasattr(ScriptTask, call.attr)):
                    missing.add(call.attr)
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name) and call.func.value.id == 'self'
                        and not hasattr(ScriptTask, call.func.attr)):
                    missing.add(call.func.attr)
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name) and call.func.value.id == 'self'
                        and not any(isinstance(arg, ast.Starred) for arg in call.args)
                        and all(keyword.arg is not None for keyword in call.keywords)):
                    method = getattr(instance, call.func.attr, None)
                    if callable(method):
                        try:
                            inspect.signature(method).bind(
                                *[None for _ in call.args],
                                **{keyword.arg: None for keyword in call.keywords},
                            )
                        except TypeError as error:
                            incompatible.append(f'{path}:{call.lineno}: {error}')
    assert not missing
    assert not incompatible


def test_imported_class_constants_exist_in_local_framework():
    missing = []
    paths = [*Path('tasks/Chess').rglob('*.py'), Path('tasks/GameUi/chess_battle.py'), Path('module/atom/frame.py')]
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        symbols = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                module = importlib.import_module(node.module)
                for name in node.names:
                    if name.name != '*':
                        symbols[name.asname or name.name] = getattr(module, name.name)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in symbols and inspect.isclass(symbols[node.value.id])
                    and not hasattr(symbols[node.value.id], node.attr)):
                missing.append(f'{path}:{node.lineno}: {node.value.id}.{node.attr}')
    assert not missing


def test_constructor_and_device_call_signatures_match_local_framework():
    symbols = {cls.__name__: cls for cls in (RuleImage, RuleFrame, RuleClick, RuleOcr)}
    symbols['Press_and_Drag'] = Press_and_Drag
    incompatible = []
    paths = [*Path('tasks/Chess').rglob('*.py'), Path('tasks/GameUi/chess_battle.py'), Path('module/atom/frame.py')]
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if (not isinstance(node, ast.Call) or any(isinstance(arg, ast.Starred) for arg in node.args)
                    or any(keyword.arg is None for keyword in node.keywords)):
                continue
            method = None
            unbound = False
            if isinstance(node.func, ast.Name):
                method = symbols.get(node.func.id)
            elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == 'self' and node.func.value.attr == 'device'):
                method = getattr(Device, node.func.attr, None)
                unbound = method is not None and not isinstance(
                    inspect.getattr_static(Device, node.func.attr), (staticmethod, classmethod),
                )
            elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'device'):
                method = getattr(Device, node.func.attr, None)
                unbound = method is not None and not isinstance(
                    inspect.getattr_static(Device, node.func.attr), (staticmethod, classmethod),
                )
            if callable(method):
                try:
                    inspect.signature(method).bind(
                        *[None] * (len(node.args) + int(unbound)),
                        **{keyword.arg: None for keyword in node.keywords},
                    )
                except TypeError as error:
                    incompatible.append(f'{path}:{node.lineno}: {error}')
    assert not incompatible


def test_shop_purchase_confirms_card_disappears_after_click():
    task = object.__new__(ScriptTask)
    task.chess_state = ChessGameState()
    target = ChessAssets.C_SHIKIGAMI_3
    card = {'name': 'kaoru', 'source': 'frame', 'score': .9856}
    task._recognize_shop_slot = Mock(side_effect=[card, card, None, None])
    task._is_purchase_allowed = Mock(return_value=True)
    task._can_afford_shop_shikigami = Mock(return_value=True)
    task._purchase_time_available = Mock(return_value=True)
    task._shop_purchase_snapshot = Mock(return_value={})
    task.screenshot = Mock()
    task.appear = Mock(return_value=False)
    task.click = Mock(return_value=True)
    task.device = SimpleNamespace(click_record_remove=Mock())

    assert task._buy_shop_slot(3, target, 'kaoru') is True

    task.click.assert_called_once_with(target, interval=.3)
    assert task.screenshot.call_count == 3
    task.device.click_record_remove.assert_called_once_with(target)


def test_click_until_disappear_keeps_legacy_behavior():
    task = object.__new__(base_task.BaseTask)
    target = ChessAssets.I_CHESS_START
    task.screenshot = Mock()
    task.appear = Mock(side_effect=[True, False])
    task.appear_then_click = Mock(return_value=True)

    assert task.ui_click_until_disappear(target, interval=.8) is True

    task.appear_then_click.assert_called_once_with(target, interval=.8)


def test_click_until_disappear_requires_consecutive_missing_frames():
    task = object.__new__(base_task.BaseTask)
    target = ChessAssets.C_SHIKIGAMI_3
    task.screenshot = Mock()
    task.click = Mock(return_value=True)
    visible = Mock(side_effect=[True, False, True, False, False])

    assert task.ui_click_until_disappear(
        target, click_target=target, visible=visible, interval=.3,
        timeout=2, confirm_frames=2, max_clicks=3,
    ) is True

    assert task.click.call_count == 2
    assert task.screenshot.call_count == 5


@pytest.mark.parametrize('guard, timeout, max_clicks', [
    (lambda: False, 2, 3),
    (None, 0, 3),
    (None, 2, 0),
])
def test_click_until_disappear_stops_before_disallowed_click(guard, timeout, max_clicks):
    task = object.__new__(base_task.BaseTask)
    target = ChessAssets.C_SHIKIGAMI_3
    task.screenshot = Mock()
    task.click = Mock(return_value=True)

    assert task.ui_click_until_disappear(
        target, click_target=target, visible=lambda: True, guard=guard,
        timeout=timeout, max_clicks=max_clicks,
    ) is False

    task.click.assert_not_called()
