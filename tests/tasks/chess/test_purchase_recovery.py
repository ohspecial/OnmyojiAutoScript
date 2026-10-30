"""验证失败购买的跨阶段预算、腾位确认及诊断记录。"""

from collections import deque
import json
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from module.device.device import Device
from tasks.Chess.assets import ChessAssets
from tasks.Chess.runtime.state import ChessGameState, ChessPurchaseAttempt
from tasks.Chess.script_task import ScriptTask


@pytest.fixture
def task(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr('time.monotonic', lambda: clock.now)
    monkeypatch.setattr('time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    result = object.__new__(ScriptTask)
    result.chess_state = ChessGameState()
    result.interval_timer = {}
    result.device = SimpleNamespace(
        image=np.zeros((20, 30, 3), dtype=np.uint8), image_frame_id='frame',
        click_record=deque(maxlen=15), stuck_record_clear=Mock(),
    )
    for name in ('click_record_add', 'click_record_check', 'click_record_clear', 'click_record_remove'):
        setattr(result.device, name, MethodType(getattr(Device, name), result.device))

    def click(rule, **kwargs):
        result.device.click_record_add(rule)
        result.device.click_record_check()
        return True

    result.click = Mock(side_effect=click)
    result.screenshot = Mock()
    result.appear = Mock(return_value=False)
    result._read_chess_mode = Mock(return_value='备')
    result._read_remaining_time = Mock(return_value=30)
    result._read_shop_gold = Mock(return_value=38)
    result._can_afford_shop_shikigami = Mock(return_value=True)
    result._recognize_shop_slot = Mock(return_value={'name': 'hotarugusa', 'source': 'frame', 'score': .99})
    result._hand_card_detections = Mock(return_value=[{}] * 10)
    result._hand_capacity_count = Mock(return_value=9)
    result._free_one_hand_slot_for_purchase = Mock(return_value=None)
    result._save_shop_purchase_failure = Mock()
    return result


def test_blocked_card_does_not_retry_when_preparation_changes_to_battle(task):
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    task._read_chess_mode.return_value = '战'
    for _ in range(12):
        assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    assert task.click.call_count == 1
    task._free_one_hand_slot_for_purchase.assert_called_once_with()
    task._save_shop_purchase_failure.assert_called_once()
    assert len(task.device.click_record) == 1


def test_same_stock_has_three_total_clicks_even_after_verified_recovery(task):
    task._free_one_hand_slot_for_purchase.return_value = {'hand_count_before': 10, 'hand_count_after': 9}
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    task._read_chess_mode.return_value = '战'
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    assert task.click.call_count == 3
    assert task.chess_state.shop_purchases[(4, 'hotarugusa')].attempts == 3
    task._free_one_hand_slot_for_purchase.assert_called_once_with()


def test_verified_recovery_can_retry_and_complete_purchase(task):
    original_click = task.click.side_effect
    bought = False

    def click(rule, **kwargs):
        nonlocal bought
        result = original_click(rule, **kwargs)
        bought = task.click.call_count == 2
        return result

    card = task._recognize_shop_slot.return_value
    task.click.side_effect = click
    task._recognize_shop_slot.side_effect = lambda *args, **kwargs: None if bought else card
    task._free_one_hand_slot_for_purchase.return_value = {'hand_count_before': 10, 'hand_count_after': 9}
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is True
    assert task.click.call_count == 2
    assert not task.chess_state.shop_purchases
    assert not task.device.click_record
    task._save_shop_purchase_failure.assert_not_called()


def test_full_hand_cleans_up_before_any_purchase_click(task):
    task._hand_capacity_count.return_value = 10
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    task.click.assert_not_called()
    task._free_one_hand_slot_for_purchase.assert_called_once_with()
    assert task.chess_state.shop_purchases[(4, 'hotarugusa')].blocked_reason


def test_full_hand_recovery_preserves_shared_purchase_budget(task):
    task._hand_capacity_count.side_effect = [10, 9, 9, 9]
    task._free_one_hand_slot_for_purchase.return_value = {'hand_count_before': 10, 'hand_count_after': 9}
    assert task._buy_shop_slot(4, ChessAssets.C_SHIKIGAMI_4, 'hotarugusa') is False
    assert task.click.call_count == 3
    task._free_one_hand_slot_for_purchase.assert_called_once_with()


def blocked_record(task):
    task.chess_state.shop_purchases[(4, 'hotarugusa')] = ChessPurchaseAttempt(3, True, 'no space')
    task.chess_state.shop_slot_names.update({slot: 'hotarugusa' for slot in range(1, 6)})
    task.device.click_record.extend([str(ChessAssets.C_SHIKIGAMI_4)] * 3)


def test_blocked_slot_does_not_prevent_purchasing_other_targets(task):
    blocked_record(task)
    task._ensure_shop_open = Mock(return_value=True)
    task._recognize_shop_slot.side_effect = lambda slot, rule: (
        {'name': 'kaoru', 'source': 'frame', 'score': .99} if slot == 3
        else {'name': 'hotarugusa', 'source': 'frame', 'score': .99} if slot == 4 else None
    )
    task._buy_shop_slot = Mock(return_value=True)
    assert task.purchase_lineup_cards_once() == ['kaoru']
    task._buy_shop_slot.assert_called_once_with(slot_index=3, click_rule=ChessAssets.C_SHIKIGAMI_3, matched_name='kaoru')


@pytest.mark.parametrize('changed', [False, True])
def test_only_confirmed_refresh_releases_same_name_block(task, changed):
    blocked_record(task)
    before = {slot: {'name': 'hotarugusa', 'image': None} for slot in range(1, 6)}
    after = {slot: {'name': 'kaoru' if changed and slot <= 3 else 'hotarugusa', 'image': None}
             for slot in range(1, 6)}
    task._shop_slot_refresh_snapshot = Mock(side_effect=[before, after, after] if not changed else [before, after])
    result = task._click_shop_refresh_and_confirm_slots(allow_hidden=True)
    assert result == ('success' if changed else 'no_progress')
    assert bool(task.chess_state.shop_purchases) is not changed
    if changed:
        assert str(ChessAssets.C_SHIKIGAMI_4) not in task.device.click_record


def test_partial_or_unchanged_recognition_does_not_release_block(task):
    blocked_record(task)
    task._observe_shop_purchase_layout({})
    task._observe_shop_purchase_layout({4: 'hotarugusa'})
    assert task.chess_state.shop_purchases[(4, 'hotarugusa')].blocked_reason
    task._observe_shop_purchase_layout({1: 'kaoru', 2: 'kaoru', 3: 'kaoru', 4: 'hotarugusa'})
    assert not task.chess_state.shop_purchases


def test_new_game_resets_purchase_history(task):
    blocked_record(task)
    task.chess_state.begin_game()
    task._reset_economy_state()
    assert not task.chess_state.shop_purchases
    assert not task.chess_state.shop_slot_names
    assert not task.device.click_record


@pytest.mark.parametrize('remaining', [None, 4, 14])
def test_late_preparation_skips_purchases_and_economy(task, remaining):
    task._read_remaining_time.return_value = remaining
    task._ensure_shop_open = Mock()
    task._run_economy_atomic_batch = Mock()
    assert task.purchase_lineup_cards_once() == []
    task._run_preparation_economy_until_time_limit()
    task._ensure_shop_open.assert_not_called()
    task._run_economy_atomic_batch.assert_not_called()
    task.click.assert_not_called()


def test_late_preparation_still_runs_deployment(task):
    task._read_remaining_time.return_value = 4
    task._is_shop_open = Mock(return_value=False)
    task.deploy_shikigami_from_hand = Mock()
    task.equip_souls_from_hand = Mock()
    assert task.purchase_lineup_cards_once() == []
    assert task._handle_preparation() is True
    task.deploy_shikigami_from_hand.assert_called_once_with()


def test_shop_open_wait_yields_to_deployment_when_clock_runs_low(task):
    task._is_shop_open = Mock(return_value=False)
    task._read_remaining_time.side_effect = [30, 30, 14]
    assert task._ensure_shop_open() is False
    task.click.assert_called_once_with(task.I_MARKET)


@pytest.mark.parametrize('counts, success', [
    ([10, 10, 10, 9, 9, 9], True),
    ([10, 10, 10, 10], False),
    ([10, 10, 10, 9, 10], False),
    ([10, 10, 10, 9, 9, 10], False),
])
def test_recovery_requires_total_hand_reduction_through_reopening(task, counts, success):
    del task._free_one_hand_slot_for_purchase
    task._ensure_shop_closed = Mock(return_value=True)
    task._ensure_shop_open = Mock(return_value=True)
    task.deploy_shikigami_from_hand = Mock()
    task.emergency_cleanup_hand = Mock(return_value={'sold_non_lineup': [(200, 600)]})
    task.sell_one_lineup_hand_card = Mock()
    task._hand_card_detections.side_effect = [[{}] * count for count in counts]
    result = task._free_one_hand_slot_for_purchase()
    assert (result is not None) is success
    task.sell_one_lineup_hand_card.assert_not_called()
    assert task._purchase_recovery_active is False


def test_successful_deployment_frees_space_without_cleanup_or_selling(task):
    del task._free_one_hand_slot_for_purchase
    task._ensure_shop_closed = Mock(return_value=True)
    task._ensure_shop_open = Mock(return_value=True)
    task.deploy_shikigami_from_hand = Mock()
    task.emergency_cleanup_hand = Mock()
    task._hand_card_detections.side_effect = [[{}] * count for count in [10, 10, 9, 9, 9, 9]]
    assert task._free_one_hand_slot_for_purchase()['hand_count_after'] == 9
    task.emergency_cleanup_hand.assert_not_called()


def test_recovery_yields_when_remaining_time_becomes_short(task):
    del task._free_one_hand_slot_for_purchase
    task._ensure_shop_closed = Mock(return_value=True)
    task._ensure_shop_open = Mock()
    task.deploy_shikigami_from_hand = Mock(side_effect=lambda: setattr(task._read_remaining_time, 'return_value', 14))
    task.emergency_cleanup_hand = Mock()
    assert task._free_one_hand_slot_for_purchase() is None
    task.emergency_cleanup_hand.assert_not_called()
    task._ensure_shop_open.assert_not_called()
    assert task._purchase_recovery_active is False


def test_failure_saves_before_after_images_and_counts(task, tmp_path, monkeypatch):
    del task._save_shop_purchase_failure
    monkeypatch.chdir(tmp_path)
    task.chess_state.shop_purchases[(4, 'hotarugusa')] = ChessPurchaseAttempt(3)
    before = {'hand_count': 10, 'gold': 33, 'image': task.device.image}
    after = {'hand_count': 10, 'gold': 38, 'image': task.device.image}
    task._save_shop_purchase_failure(4, 'hotarugusa', 'no space', before, after)
    folder, = (tmp_path / 'log/chess_purchase').iterdir()
    assert (folder / 'before.png').is_file()
    assert (folder / 'after.png').is_file()
    details = json.loads((folder / 'details.json').read_text(encoding='utf-8'))
    assert details['before'] == {'hand_count': 10, 'gold': 33}
    assert details['after'] == {'hand_count': 10, 'gold': 38}
