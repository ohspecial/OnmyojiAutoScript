"""回放日志中的倒计时字形误识别和拖卡后阶数短暂丢失。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.Chess.runtime.round_state import ChessRoundStateMixin
from tasks.Chess.runtime.state import ChessGameState
from tasks.Chess.script_task import ScriptTask


@pytest.fixture
def task(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    result = object.__new__(ScriptTask)
    result.chess_state = ChessGameState()
    result.device = SimpleNamespace(image=None)
    result.screenshot = Mock()
    result.appear = Mock(return_value=False)
    result._is_preparation_mode = Mock(return_value=True)
    return result


@pytest.mark.parametrize('raw, expected', [
    ('16', 16), ('1G', 16), ('1S', 15), ('O9', 9), ('1G秒', 16),
    ('14', 14), ('0', 0), ('备', None), ('8abc5', None), ('1:06', None), ('', None),
])
def test_countdown_text_does_not_silently_truncate_bad_glyphs(raw, expected):
    assert ChessRoundStateMixin._parse_remaining_time_text(raw) == expected


@pytest.mark.parametrize('alternate', [False, True])
def test_countdown_uses_repaired_text_in_both_layouts(task, alternate):
    task._read_primary_round_layout = Mock(return_value=('1G', alternate))
    task.O_NOW_TIME = SimpleNamespace(ocr=Mock(return_value=['1G']))
    assert task._read_remaining_time() == 16
    task._read_chess_mode = Mock(return_value='备')
    assert task._purchase_time_available() is True


def test_list_result_from_ocr_is_treated_as_text():
    assert ChessRoundStateMixin._normalize_ocr_text(['备']) == '备'
    assert ChessRoundStateMixin._normalize_ocr_text(['1G']) == '1G'


def test_transient_level_failure_retries_with_new_screenshot(task):
    task._read_level = Mock(side_effect=[None, 5])
    result = task._read_lineup_capacity_status()
    assert result['capacity'] == 5
    task.screenshot.assert_called_once_with()
    assert task._read_level.call_count == 2


def test_persistently_unknown_level_stays_safe_and_bounded(task):
    task._read_level = Mock(return_value=None)
    assert task._read_lineup_capacity_status() is None
    assert task._read_level.call_count == 3
    assert task.screenshot.call_count == 2


def test_level_retry_stops_when_preparation_ends(task):
    task._read_level = Mock(return_value=None)
    task._is_preparation_mode.return_value = False
    assert task._read_lineup_capacity_status() is None
    task.screenshot.assert_not_called()


def test_unknown_capacity_does_not_mark_preparation_complete(task):
    task._ensure_shop_closed = Mock(return_value=True)
    task._is_shop_open = Mock(return_value=False)
    task._read_lineup_capacity_status = Mock(return_value=None)
    task._find_best_shikigami_hand_card = Mock(return_value=None)
    task.equip_souls_from_hand = Mock()

    assert task._handle_preparation() is False
    assert task._deployment_capacity_pending is True
    task.equip_souls_from_hand.assert_not_called()

    # 下一帧阶数恢复后继续准备，而不是带着“已完成”的标记空等到开战。
    task._read_lineup_capacity_status.return_value = {'capacity': 5, 'full': False}
    assert task._handle_preparation() is True
    assert task._deployment_capacity_pending is False
    task.equip_souls_from_hand.assert_called_once_with(set())
