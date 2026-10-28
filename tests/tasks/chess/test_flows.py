"""使用模拟画面推进关键流程，不连接模拟器或发送实际输入。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
import pytest

from module.exception import TaskEnd
from tasks.Chess.assets import ChessAssets
from tasks.Chess.config import Chess, ChessConfig
from tasks.Chess.runtime.events import ChessEventMonitor
from tasks.Chess.runtime.round_state import ChessRoundStateMixin
from tasks.Chess.runtime.state import ChessGameState
from tasks.Chess.script_task import ScriptTask
from tasks.GlobalGame.assets import GlobalGameAssets


class OfflineClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_task(monkeypatch):
    clock = OfflineClock()
    monkeypatch.setattr('time.monotonic', clock.monotonic)
    monkeypatch.setattr('time.sleep', clock.sleep)
    task = object.__new__(ScriptTask)
    task.chess_state = ChessGameState()
    task.chess_events = ChessEventMonitor()
    task.interval_timer = {}
    task.device = SimpleNamespace(
        stuck_record_clear=Mock(), click_record_remove=Mock(),
        image=np.zeros((2, 2, 3), dtype=np.uint8), image_frame_id='initial',
    )
    task.click = Mock(return_value=True)
    task.set_next_run = Mock()
    return task


def set_frames(task, frames):
    sequence = iter(enumerate(frames))

    def screenshot():
        number, task.offline_frame = next(sequence)
        task.device.image_frame_id = f'offline-{number}'

    task.screenshot = Mock(side_effect=screenshot)


def prepare_round(task, monkeypatch, frames):
    set_frames(task, frames)
    monkeypatch.setattr(ChessRoundStateMixin, '_read_round_number', lambda self: self.offline_frame[0])
    monkeypatch.setattr(ChessRoundStateMixin, '_read_chess_mode', lambda self: self.offline_frame[1])
    task.appear = Mock(return_value=False)
    task._finish_chess_game_after_markers_missing = Mock(return_value=False)
    task.purchase_lineup_cards_once = Mock()
    task._run_preparation_economy_until_time_limit = Mock()
    task._handle_preparation_stage = Mock(return_value=True)
    task._handle_battle_sell_stage = Mock(return_value=True)
    task._run_battle_economy_until_budget_limit = Mock()
    task._handle_passive_stage = Mock(return_value=True)


def test_round_switch_freezes_old_actions_and_runs_stages_once(monkeypatch):
    task = make_task(monkeypatch)
    prepare_round(task, monkeypatch, [
        (1, '备'), (1, '战'), (1, '战'), (1, '鬼'), (1, '待'), (2, '备'), (2, '备'),
    ])

    assert task.run_one_round(1) == 2

    task.purchase_lineup_cards_once.assert_called_once_with()
    task._run_preparation_economy_until_time_limit.assert_called_once_with()
    task._handle_preparation_stage.assert_called_once_with(1)
    task._handle_battle_sell_stage.assert_called_once_with()
    task._run_battle_economy_until_budget_limit.assert_called_once_with()
    assert task._handle_passive_stage.call_args_list == [call('战'), call('战'), call('鬼'), call('待')]
    assert task.chess_state.round.hyakki_round_seen


def test_grigri_is_resolved_before_preparation_purchase(monkeypatch):
    task = make_task(monkeypatch)
    prepare_round(task, monkeypatch, [(1, '符咒'), (1, '备'), (2, '备'), (2, '备')])
    task.appear = lambda marker: marker is ChessAssets.I_SELECT_GRIGRI and task.offline_frame[1] == '符咒'

    def select_grigri():
        task.purchase_lineup_cards_once.assert_not_called()
        return True

    task._select_grigri_and_check_lineup = Mock(side_effect=select_grigri)

    assert task.run_one_round(1) == 2

    task._select_grigri_and_check_lineup.assert_called_once_with()
    task.purchase_lineup_cards_once.assert_called_once_with()


def test_hyakki_followup_reconciles_before_next_preparation_purchase(monkeypatch):
    task = make_task(monkeypatch)
    task._is_boss_challenge_round = Mock(return_value=False)
    task._board_set_has_shikigami_visual = Mock(return_value=False)
    task._board_lineup_names = {'kaoru'}
    task._board_actual_positions = {'kaoru': 1}
    task._player_deployed_positions = {1}
    task._reconcile_lineup_after_hyakki_round = Mock(wraps=task._reconcile_lineup_after_hyakki_round)
    prepare_round(task, monkeypatch, [(6, '鬼'), (7, '备'), (7, '备')])

    assert task.run_one_round(6) == 7
    assert task.chess_state.hyakki_lineup_check_pending
    task._reconcile_lineup_after_hyakki_round.assert_not_called()

    prepare_round(task, monkeypatch, [(7, '备'), (8, '备'), (8, '备')])

    def purchase():
        task._reconcile_lineup_after_hyakki_round.assert_called_once_with(next_round_no=7)
        assert task._current_round_no == 7
        assert not task._board_lineup_names
        assert not task._board_actual_positions
        assert not task._player_deployed_positions

    task.purchase_lineup_cards_once.side_effect = purchase
    assert task.run_one_round(7) == 8
    assert not task.chess_state.hyakki_lineup_check_pending


def test_hyakki_check_stays_pending_when_next_preparation_was_missed(monkeypatch):
    task = make_task(monkeypatch)
    task._reconcile_lineup_after_hyakki_round = Mock()
    prepare_round(task, monkeypatch, [(6, '鬼'), (7, '战'), (7, '战')])
    assert task.run_one_round(6) == 7
    prepare_round(task, monkeypatch, [(7, '战'), (8, '备'), (8, '备')])
    assert task.run_one_round(7) == 8
    assert task.chess_state.hyakki_lineup_check_pending
    task._reconcile_lineup_after_hyakki_round.assert_not_called()


def test_hyakki_check_waits_until_a_non_boss_preparation(monkeypatch):
    task = make_task(monkeypatch)
    task.chess_state.hyakki_lineup_check_pending = True
    task._is_preparation_mode = Mock(return_value=True)
    task._is_boss_challenge_round = Mock(return_value=True)
    task._reconcile_lineup_after_hyakki_round = Mock()
    assert task._check_pending_hyakki_lineup(9) is False
    assert task.chess_state.hyakki_lineup_check_pending
    task._reconcile_lineup_after_hyakki_round.assert_not_called()
    task._is_boss_challenge_round.return_value = False
    assert task._check_pending_hyakki_lineup(10) is True
    assert not task.chess_state.hyakki_lineup_check_pending
    task._reconcile_lineup_after_hyakki_round.assert_called_once_with(next_round_no=10)
    assert task._check_pending_hyakki_lineup(10) is False


def test_hyakki_pending_check_does_not_leak_to_next_game():
    state = ChessGameState(hyakki_lineup_check_pending=True)
    state.begin_game()
    assert state.hyakki_lineup_check_pending is False


def test_consuming_previous_hyakki_check_does_not_skip_a_new_one(monkeypatch):
    task = make_task(monkeypatch)
    task._is_boss_challenge_round = Mock(return_value=False)
    task._reconcile_lineup_after_hyakki_round = Mock()
    task.chess_state.hyakki_lineup_check_pending = True
    prepare_round(task, monkeypatch, [(7, '备'), (7, '鬼'), (8, '备'), (8, '备')])
    assert task.run_one_round(7) == 8
    task._reconcile_lineup_after_hyakki_round.assert_called_once_with(next_round_no=7)
    assert task.chess_state.hyakki_lineup_check_pending
    prepare_round(task, monkeypatch, [(8, '备'), (9, '备'), (9, '备')])
    assert task.run_one_round(8) == 9
    assert task._reconcile_lineup_after_hyakki_round.call_args_list == [
        call(next_round_no=7), call(next_round_no=8),
    ]
    assert not task.chess_state.hyakki_lineup_check_pending


@pytest.mark.parametrize('rank_protection', [False, True])
def test_round_stops_for_game_end_or_protection_exit(monkeypatch, rank_protection):
    task = make_task(monkeypatch)
    prepare_round(task, monkeypatch, [(1, '备')])
    task._rank_protection_exit_requested = rank_protection
    task._finish_chess_game_after_markers_missing.return_value = not rank_protection
    task.Chess_Exit = Mock(return_value=True)

    assert task.run_one_round(1) is None

    task.purchase_lineup_cards_once.assert_not_called()
    if rank_protection:
        task.Chess_Exit.assert_called_once_with(return_to_lobby=False)
        assert task._rank_protection_exit_succeeded
    else:
        task.Chess_Exit.assert_not_called()


@pytest.mark.parametrize('first_stage', ['exit', 'reward', 'share'])
def test_result_flow_reaches_lobby_through_share_and_rank(monkeypatch, first_stage):
    task = make_task(monkeypatch)
    frames = [first_stage]
    if first_stage != 'share':
        frames.append('share')
    frames.extend(['transition', 'rank', 'lobby'])
    set_frames(task, frames)
    markers = {
        'exit': (task.I_CHESS_EXIT_TO_LOBBY,),
        'reward': (GlobalGameAssets.I_UI_REWARD,),
        'share': (ChessAssets.I_SHARE,),
        'transition': (),
        'rank': (task.I_CHECK_CHESS_RANK, task.I_CHESS_RANK_GOTO_LOBBY),
        'lobby': (task.I_CHECK_CHESS,),
    }
    task.appear = lambda marker: any(marker is value for value in markers[task.offline_frame])
    task.appear_then_click = Mock(side_effect=lambda marker, **kwargs: task.appear(marker))

    assert task.return_to_chess_lobby() is True

    assert call(task.I_CHESS_RANK_GOTO_LOBBY, interval=1.5) in task.appear_then_click.call_args_list
    assert task._chess_share_advancing is False


@pytest.mark.parametrize('return_to_lobby', [False, True])
def test_chess_exit_confirms_then_completes_requested_result_flow(monkeypatch, return_to_lobby):
    task = make_task(monkeypatch)
    set_frames(task, ['battle', 'confirm', 'result', 'result'])
    task.select_chess_sixrealms_if_visible = Mock(return_value=False)
    task.chess_result_page_visible = Mock(side_effect=lambda: task.offline_frame == 'result')
    task.appear = lambda marker: marker is task.I_CHESS_EXIT_CONFIRM and task.offline_frame == 'confirm'
    task.appear_then_click = Mock(side_effect=lambda marker, **kwargs: (
        task.appear(marker) or (marker is task.I_CHESS_EXIT and task.offline_frame == 'battle')
    ))
    task.return_to_chess_lobby = Mock(return_value=True)

    assert task.Chess_Exit(return_to_lobby=return_to_lobby) is True

    assert call(task.I_CHESS_EXIT_CONFIRM, interval=.8) in task.appear_then_click.call_args_list
    if return_to_lobby:
        task.return_to_chess_lobby.assert_called_once_with()
    else:
        task.return_to_chess_lobby.assert_not_called()


def test_restart_from_rank_page_waits_for_button_to_disappear(monkeypatch):
    task = make_task(monkeypatch)
    set_frames(task, ['share', 'restart', 'waiting'])
    task.appear = lambda marker: (
        marker is ChessAssets.I_SHARE and task.offline_frame == 'share'
        or marker is ChessAssets.I_RESTART_AGAIN and task.offline_frame == 'restart'
    )

    assert task._restart_chess_game_from_result() is True

    assert task.click.call_args_list[-1] == call(ChessAssets.I_RESTART_AGAIN)


def prepare_matchmaking(task, frames):
    set_frames(task, frames)
    task._matchmaking_timeout_seconds = 10
    task._consecutive_matchmaking_timeouts = 0
    task.SLOW_POLL_INTERVAL = 11
    task.select_chess_sixrealms_if_visible = Mock(return_value=False)
    task._is_in_chess_game = Mock(side_effect=lambda: task.offline_frame == 'game')
    task.chess_result_page_visible = Mock(return_value=False)
    task.appear = lambda marker: (
        marker is task.I_CANCEL_WAITING and task.offline_frame == 'waiting'
        or marker is task.I_CHESS_START and task.offline_frame == 'lobby'
    )
    task.appear_then_click = Mock(return_value=True)


@pytest.mark.parametrize('frames', [
    ['waiting', 'loading', 'game'],
    ['waiting', 'waiting', 'game', 'game'],
])
def test_match_completion_avoids_cancel_click(monkeypatch, frames):
    task = make_task(monkeypatch)
    prepare_matchmaking(task, frames)

    task._wait_until_in_chess_game(timeout=120, retry_start=True)

    task.appear_then_click.assert_not_called()
    assert task._consecutive_matchmaking_timeouts == 0


def test_three_confirmed_queue_timeouts_end_task(monkeypatch):
    task = make_task(monkeypatch)
    prepare_matchmaking(task, ['waiting', 'waiting', 'waiting', 'lobby'] * 3)

    with pytest.raises(TaskEnd):
        task._wait_until_in_chess_game(timeout=120, retry_start=True)

    assert task._consecutive_matchmaking_timeouts == 3
    assert task.appear_then_click.call_args_list == [call(task.I_CANCEL_WAITING, interval=0)] * 3
    task.set_next_run.assert_called_once_with(task='Chess', success=False, finish=True)


def prepare_task_run(task, config):
    task.config = SimpleNamespace(chess=Chess(chess_config=config))
    task.start_time = datetime.now()
    task.screenshot = Mock()
    task.goto_page = Mock()
    task._recover_interrupted_chess_game = Mock()
    task.return_to_chess_lobby = Mock(return_value=True)


def test_top_four_rank_completes_two_protection_exits(monkeypatch):
    task = make_task(monkeypatch)
    prepare_task_run(task, ChessConfig(run_count=1, rank_protection=True))
    requested_exits = []

    def run_game():
        requested_exits.append(task._rank_protection_exit_requested)
        task._rank_protection_exit_succeeded = task._rank_protection_exit_requested
        return None if task._rank_protection_exit_requested else 1

    task.run_one_game = Mock(side_effect=run_game)
    task._restart_chess_game_from_result = Mock(return_value=True)

    with pytest.raises(TaskEnd):
        task.run()

    assert requested_exits == [False, True, True]
    assert task._restart_chess_game_from_result.call_count == 2
    task.return_to_chess_lobby.assert_called_once_with()
    task.set_next_run.assert_called_once_with(task='Chess', success=True, finish=True)


def test_full_weekly_coins_schedule_next_monday_after_game(monkeypatch):
    task = make_task(monkeypatch)
    prepare_task_run(task, ChessConfig(run_count=-1, coin_full_exit=True))
    task._coin_is_full = Mock(side_effect=[False, True])
    task.run_one_game = Mock(return_value=5)

    with pytest.raises(TaskEnd):
        task.run()

    task.run_one_game.assert_called_once_with()
    scheduling = task.set_next_run.call_args.kwargs
    assert scheduling['task'] == 'Chess'
    assert scheduling['server'] is False
    assert scheduling['target'].weekday() == 0
    assert timedelta(0) < scheduling['target'] - task.start_time <= timedelta(days=7)
