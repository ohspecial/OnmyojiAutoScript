"""Regression cases for the October 31–November 2 Chess backport."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from module.atom.frame import Ocr, RuleFrame
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from tasks.Chess.assets import ChessAssets
from tasks.Chess.config import ChessConfig
from tasks.Chess.runtime.cache import economy_scope, same_frame
from tasks.Chess.runtime.state import ChessGameState
from tasks.Chess.script_task import ScriptTask
from tasks.Chess.strategy.lineup_loader import load_lineup_registry
from tasks.Chess.strategy.shikigami_catalog import SHIKIGAMI_BONDS_BY_ROMAJI


@pytest.fixture
def task(monkeypatch):
    clock = SimpleNamespace(now=0.)
    monkeypatch.setattr('time.monotonic', lambda: clock.now)
    monkeypatch.setattr('time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    result = object.__new__(ScriptTask)
    result.chess_state = ChessGameState()
    result.interval_timer = {}
    result.device = SimpleNamespace(image=np.zeros((720, 1280, 3), np.uint8),
                                    image_frame_id=1, click_record_remove=Mock(),
                                    stuck_record_clear=Mock())

    def screenshot():
        clock.now += .35
        result.device.image_frame_id += 1
        result.device.image = result.device.image.copy()

    result.screenshot = Mock(side_effect=screenshot)
    result._read_round_number = Mock(return_value=7)
    result._read_chess_mode = Mock(return_value='备')
    result._read_remaining_time = Mock(return_value=30)
    result._read_level = Mock(return_value=7)
    result._read_shop_gold = Mock(return_value=70)
    result.appear = Mock(return_value=False)
    result.click = Mock(return_value=True)
    return result


def test_arakawa_catalog_and_both_lineups_are_usable():
    assert '回响' in SHIKIGAMI_BONDS_BY_ROMAJI['arakawa_no_nushi']
    assert '分裂' not in SHIKIGAMI_BONDS_BY_ROMAJI['arakawa_no_nushi']
    registry = load_lineup_registry()
    assert ChessConfig(lineup_bond='荒川').lineup_bond.value == '荒川'
    assert ChessConfig(lineup_bond='海国').lineup_bond.value == '海国'
    assert registry['huangchuan']['strategy']['arakawa_goldfish_position'] == 7
    assert registry['haiguo']['strategy']['display_name'] == '海国'


@pytest.mark.parametrize('health,reserve,operation', [
    (None, 50, 'experience'), (100, 50, 'experience'), (60, 50, 'experience'),
    (59, 40, 'experience'), (20, 40, 'experience'), (19, 0, 'refresh'),
])
def test_health_controls_gold_reserve_and_emergency_operation(task, health, reserve, operation):
    task.chess_state.current_health = health
    assert task._economy_reserve_for_level(5) == reserve
    assert task._economy_sequence_for_level(5)[0] == operation
    if health == 19:
        assert not task._can_execute_economy_operation(5, 100, 'experience')
        assert task._can_execute_economy_operation(5, 2, 'refresh')


def test_refresh_quotas_follow_round_and_level(task):
    task.chess_state.economy_refresh_counts[7] = 1
    assert not task._economy_refresh_quota_available(6)
    assert task._economy_refresh_quota_available(7)
    task.chess_state.economy_refresh_counts[7] = 2
    assert task._economy_sequence_for_level(7) == ('experience',)
    task._read_round_number.return_value = 8
    assert task._economy_refresh_quota_available(6)
    task.chess_state.current_health = 19
    assert task._economy_refresh_quota_available(5)


@pytest.mark.parametrize('seconds,allowed', [(6, True), (5, False), (1, False)])
def test_final_battle_seconds_guard_every_refresh_entry(task, seconds, allowed):
    task._read_chess_mode.return_value = '战'
    task._read_remaining_time.return_value = seconds
    assert task._battle_refresh_time_allowed() is allowed
    if not allowed:
        assert task._click_shop_refresh_and_confirm_slots(allow_hidden=True) == 'no_progress'
        task.click.assert_not_called()


def test_elapsed_cached_countdown_stops_nested_economy_actions(task):
    task._read_remaining_time.return_value = 16
    task._detail_frame_cache = (task.device.image, None, -2.)

    @economy_scope
    def nested(instance):
        assert not instance._purchase_time_available()
        assert instance.purchase_lineup_cards_once() == []

    nested(task)
    task.click.assert_not_called()
    assert task._economy_guard_round is None


def test_economy_scope_stops_at_round_boundary(task):
    @economy_scope
    def outer(instance):
        instance._read_round_number.return_value = 8
        assert not instance._economy_action_allowed()
        assert instance.purchase_lineup_cards_once() == []
        assert instance._economy_guard_round == 7

    outer(task)
    assert task._economy_guard_round is None
    task.click.assert_not_called()


def test_same_frame_cache_invalidates_for_frame_id_and_image_replacement():
    call = Mock(side_effect=[2, 3, 4])

    class Reader:
        device = SimpleNamespace(image=np.zeros((1, 1, 3), np.uint8), image_frame_id=1)

        @same_frame
        def read(self):
            return call()

    reader = Reader()
    assert reader.read() == reader.read() == 2
    reader.device.image_frame_id = 2
    assert reader.read() == 3
    reader.device.image = reader.device.image.copy()
    assert reader.read() == 4
    assert call.call_count == 3


def test_detail_frame_shares_one_read_across_round_mode_and_countdown(task):
    del task._read_round_number, task._read_chess_mode, task._read_remaining_time
    frame = SimpleNamespace(execute=Mock(return_value=[7, '备', '1G']))
    task.F_CHESS_DETAIL_NORMAL = frame
    assert task._read_round_number() == 7
    assert task._read_chess_mode() == '备'
    assert task._read_remaining_time() == 16
    frame.execute.assert_called_once_with(task)


def test_frame_digit_mode_runs_ocr_and_compares_integers(task, monkeypatch):
    rule = RuleFrame(name='digit_check', roi_badge=(0, 0, 2, 2),
                     roi_range=[(3, 0, 5, 5)], roi_back=(0, 0, 20, 20),
                     badgefile=[ChessAssets.F_HAND_CARD.files[0]], range=[Ocr(mode='Digit')])
    rule.defer_ocr = True
    task.appear = Mock(return_value=True)
    monkeypatch.setattr(RuleOcr, 'ocr', Mock(return_value=7))
    assert rule.run(task, 7)
    assert not rule.run(task, 8)
    with pytest.raises(ValueError):
        rule.run(task, '7')


def test_health_identifies_player_then_reads_only_once_per_round(task, monkeypatch):
    state = task.chess_state
    state.player_name = '自己'
    state.first_hyakki_round = 6
    names = Mock(return_value=[SimpleNamespace(ocr_text='自己',
                 box=np.array([[10, 10], [60, 10], [60, 30], [10, 30]]))])
    task.O_NAME_RANGE = SimpleNamespace(roi=(1060, 41, 166, 623), detect_and_ocr=names)
    task._shop_refresh_marker_visible = Mock(return_value=False)
    health = Mock(return_value=19)
    monkeypatch.setattr(RuleOcr, 'ocr', health)
    assert task._read_current_health() == 19
    assert task._read_current_health() == 19
    assert names.call_count == health.call_count == 1
    task._clear_player_identity()
    assert state.player_name is None and state.current_health is None
    assert state.observation.current_health is None


def test_health_ignores_ambiguous_names(task, monkeypatch):
    state = task.chess_state
    state.player_name = '同名'
    state.first_hyakki_round = 6
    person = SimpleNamespace(ocr_text='同名', box=np.array([[0, 0], [20, 20]]))
    task.O_NAME_RANGE = SimpleNamespace(roi=(1060, 41, 166, 623),
                                       detect_and_ocr=Mock(return_value=[person, person]))
    task._shop_refresh_marker_visible = Mock(return_value=False)
    health = Mock()
    monkeypatch.setattr(RuleOcr, 'ocr', health)
    assert task._read_current_health() is None
    health.assert_not_called()


def test_failed_sale_is_bounded_and_resets_in_next_round(task):
    task._hand_card_identity_count = Mock(return_value=1)
    task.close_shikigami_specifics_if_open = Mock(return_value=False)
    task._drag_chess = Mock()
    card = {'type': 'shikigami', 'name': 'kappa', 'position': (300, 600)}
    for _ in range(3):
        assert task._sell_hand_card_confirmed(card) == 'blocked'
    assert task._drag_chess.call_count == 2
    task._read_round_number.return_value = 8
    assert task._sell_hand_card_confirmed(card) == 'blocked'
    assert task._drag_chess.call_count == 3


def test_missing_board_anchor_keeps_registered_lineup(task):
    task._board_lineup_names = {'kaoru'}
    task._board_actual_positions = {'kaoru': 1}
    task._player_deployed_positions = {1}
    task._board_frame_scan = Mock(return_value=[])
    assert task._reconcile_lineup_after_hyakki_round() == []
    assert task._board_lineup_names == {'kaoru'}


def test_partial_refresh_after_spending_never_clicks_again(task):
    task._read_chess_mode.return_value = '战'
    task._read_level.return_value = 9
    before = {i: {'name': 'kappa', 'image': None} for i in range(1, 6)}
    after = {i: {'name': 'kaoru' if i == 1 else 'kappa', 'image': None} for i in range(1, 6)}
    snapshots = iter([before])
    task._shop_slot_refresh_snapshot = Mock(side_effect=lambda: next(snapshots, after))
    task._read_shop_gold.side_effect = [70, 68]
    assert task._click_shop_refresh_and_confirm_slots(allow_hidden=True) == 'no_progress'
    task.click.assert_called_once_with(task.I_REFRESH)
    assert task.chess_state.economy_refresh_counts[7] == 1


def test_new_game_resets_health_sales_refresh_and_drag_state():
    state = ChessGameState(player_name='自己', current_health=10)
    state.sale_failures[('a',)] = 2
    state.economy_refresh_counts[7] = 3
    state.drag_pending.add('failed_drag')
    state.begin_game()
    assert state.current_health is None and state.player_name is None
    assert not state.sale_failures and not state.economy_refresh_counts and not state.drag_pending


@pytest.mark.parametrize('gold_visible,shop_open,success', [
    (True, True, True), (False, True, False), (True, False, False),
])
def test_purchase_confirms_gold_badge_with_local_budget(task, gold_visible, shop_open, success):
    target = ChessAssets.C_SHIKIGAMI_3
    dynamic = RuleClick(roi_front=(720, 55, 175, 237), roi_back=(720, 55, 175, 237),
                        name='CHESS_STORE_SLOT_3_RANGE_6')
    card = {'name': 'kaoru', 'click_rule': dynamic}
    badge = object()
    task._recognize_shop_slot = Mock(return_value=card)
    task._shop_purchase_badge = Mock(return_value=badge)
    task._shop_purchase_snapshot = Mock(return_value={'hand_count': 0, 'gold': 70})
    task._save_shop_purchase_failure = Mock()
    task._is_shop_open = Mock(return_value=shop_open)
    task._can_afford_shop_shikigami = Mock(return_value=True)
    task._hand_capacity_count = Mock(return_value=0)
    task.appear = lambda marker: marker is badge and gold_visible and not task.click.call_count
    assert task._buy_shop_slot(3, target, 'kaoru') is success
    if success:
        # Identity still matches in the mock; the disappearing gold badge confirms it.
        clicked = task.click.call_args.args[0]
        assert clicked.roi_back == dynamic.roi_back
        assert clicked.name == target.name
        assert not task.chess_state.shop_purchases
        task._save_shop_purchase_failure.assert_not_called()
    elif not gold_visible:
        task.click.assert_not_called()
    else:
        assert task.chess_state.shop_purchases[(3, 'kaoru')].attempts == 1
        task._save_shop_purchase_failure.assert_called_once()


def test_round_loop_restores_screenshot_interval_and_identity_on_error(task):
    state = task.chess_state
    state.player_name = '自己'
    state.current_health = 19
    task.device.screenshot_interval_set = Mock()
    task._run_game_by_rounds_without_device_stuck_timeout = Mock(side_effect=RuntimeError('interrupted'))
    with pytest.raises(RuntimeError, match='interrupted'):
        task._run_round_loop()
    assert task.device.screenshot_interval_set.call_args_list[0].args == ('combat',)
    assert task.device.screenshot_interval_set.call_args_list[-1].args == ()
    assert state.player_name is None and state.current_health is None


def test_disabled_sixrealms_waits_without_clicking(task):
    task.config = SimpleNamespace(chess=SimpleNamespace(chess_config=ChessConfig(sixrealms_selection_enabled=False)))
    task.appear = Mock(side_effect=[True, True, False])
    assert task.select_chess_sixrealms_if_visible() is True
    task.click.assert_not_called()
    task.screenshot.assert_called_once()


def test_lineup_reconciliation_waits_for_valid_occupied_board(task):
    task._shop_refresh_marker_visible = Mock(return_value=False)
    task._board_lineup_names = {'kaoru', 'hotarugusa'}
    task._board_actual_positions = {'kaoru': 1, 'hotarugusa': 7}
    task._player_deployed_positions = {1, 7}
    task._board_frame_scan = Mock(return_value=[])
    task._check_preparation_lineup_once(7)
    assert not task.chess_state.preparation_lineup_checked_rounds
    slots = [{'occupied': i == 1, 'star': 1 if i == 1 else None} for i in range(1, 13)]
    task._board_frame_scan.return_value = slots
    task._check_preparation_lineup_once(7)
    assert task._board_lineup_names == {'kaoru'}
    assert task._player_deployed_positions == {1}
    assert task.chess_state.preparation_lineup_checked_rounds == {7}
