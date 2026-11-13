"""Settlement, tutorial and coin-notice regressions without device or network."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from requests import Response

from module.exception import GameStuckError, GameTooManyClickError, TaskEnd
from module.notify.notify import Notifier
from tasks.Chess.assets import ChessAssets as A
from tasks.Chess.config import Chess, ChessConfig
from tasks.Chess.script_task import ScriptTask
from tasks.GameUi.assets import GameUiAssets as G
from tasks.GameUi.chess_battle import ChessBattleNavigationMixin
from tasks.GameUi.navigator import GameUi
from tasks.GameUi.page import page_chess, page_chess_result


LOBBY = (G.I_CHECK_CHESS, A.I_CHESS_START)
PANEL = (A.I_SHARE, G.I_CHESS_SHARE_PANEL_BAR, G.I_CHESS_SHARE_PANEL_CLOSE)
RANK = (G.I_CHECK_CHESS_RANK, G.I_CHESS_RANK_GOTO_LOBBY)
MODAL = LOBBY + (A.I_TUTORIAL_PROMPT, A.I_TUTORIAL_SKIP)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    clock = SimpleNamespace(now=0.)
    monkeypatch.setattr('time.monotonic', lambda: clock.now)
    monkeypatch.setattr('time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    # A forgotten mock must fail the test instead of issuing a real push.
    monkeypatch.setattr('requests.request', Mock(side_effect=AssertionError('Unexpected HTTP')))


class FrameTask(ScriptTask):
    def __init__(self, frames):
        self.frames = iter(frames)
        self.visible = ()
        self.clicked = []
        self.device = SimpleNamespace(
            image=np.zeros((720, 1280, 3), np.uint8),
            stuck_record_clear=Mock(), click_record_remove=Mock(), click_record_clear=Mock(),
        )

    def screenshot(self):
        self.visible = next(self.frames)
        self.device.image = self.device.image.copy()

    def appear(self, marker, **kwargs):
        return any(marker is item for item in self.visible)

    def click(self, marker, **kwargs):
        self.clicked.append(marker)
        return True

    def appear_then_click(self, marker, **kwargs):
        return self.click(marker, **kwargs) if self.appear(marker) else False

    def _is_in_chess_game(self):
        return self.appear(A.I_OPEN_LINEUP)


@pytest.mark.parametrize('overlay', [PANEL, (A.I_SHARE,), RANK,
                                       (A.I_REWARD_CHESS,), (A.I_RESTART_AGAIN,),
                                       (A.I_RANK_TRACK_LEFT, A.I_RANK_TRACK_RIGHT)])
def test_result_overrides_lobby_background(overlay):
    task = FrameTask([LOBBY + overlay])
    task.screenshot()
    assert not task.chess_lobby_visible()
    assert task.chess_result_page_visible()
    assert not task.clicked


def test_share_panel_closes_then_advances_only_on_left():
    task = FrameTask([LOBBY + PANEL, LOBBY + (A.I_SHARE,), RANK, LOBBY, LOBBY])
    assert task.return_to_chess_lobby()
    assert task.clicked == [G.I_CHESS_SHARE_PANEL_CLOSE, task.CHESS_RESULT_CONTINUE,
                            G.I_CHESS_RANK_GOTO_LOBBY]
    x, y, w, h = task.CHESS_RESULT_CONTINUE.roi_front
    assert x + w < 100 and y + h < 568
    task.device.click_record_clear.assert_not_called()
    task.device.click_record_remove.assert_not_called()


@pytest.mark.parametrize('partial', [PANEL[:1], PANEL[1:], PANEL[:2], PANEL[::2]])
def test_partial_share_panel_does_not_click_close(partial):
    task = FrameTask([partial])
    task.screenshot()
    task._advance_chess_result_stage()
    assert not any(target is G.I_CHESS_SHARE_PANEL_CLOSE for target in task.clicked)


def test_reward_does_not_suppress_return_button_or_rank_restart():
    task = FrameTask([(A.I_REWARD_CHESS,), (A.I_SHARE, G.I_CHESS_EXIT_TO_LOBBY),
                      (A.I_SHARE,), (A.I_SHARE, A.I_RESTART_AGAIN), (A.I_OPEN_LINEUP,)])
    assert task._restart_chess_game_from_result()
    assert task.clicked == [task.CHESS_RESULT_CONTINUE, G.I_CHESS_EXIT_TO_LOBBY,
                            task.CHESS_RESULT_CONTINUE, A.I_RESTART_AGAIN]


def test_transient_lobby_does_not_skip_rank_restart():
    task = FrameTask([LOBBY, (A.I_RESTART_AGAIN,), (A.I_OPEN_LINEUP,)])
    assert task._restart_chess_game_from_result()
    assert task.clicked == [A.I_RESTART_AGAIN]


def test_stable_lobby_stops_result_clicks():
    task = FrameTask([LOBBY, LOBBY])
    assert task._restart_chess_game_from_result() is False
    assert not task.clicked


def test_startup_recovers_share_panel_before_lobby():
    task = FrameTask([LOBBY + PANEL])
    task.return_to_chess_lobby = Mock(return_value=True)
    assert task._recover_interrupted_chess_game()
    task.return_to_chess_lobby.assert_called_once_with()


def test_courtyard_stops_result_clicks_and_uses_navigation():
    task = FrameTask([(G.I_CHECK_MAIN,)] * 3 + [LOBBY, LOBBY])

    def navigate(destination):
        assert destination is page_chess
        assert not task.clicked
        task.visible = LOBBY

    task.goto_page = Mock(side_effect=navigate)
    assert task.return_to_chess_lobby()
    task.goto_page.assert_called_once_with(page_chess)
    assert not task.clicked


@pytest.mark.parametrize('progress', [(A.I_RANK_PROGRESS,),
                                     (A.I_RANK_TRACK_LEFT, A.I_RANK_TRACK_RIGHT)])
def test_rank_animation_overrides_false_courtyard(progress):
    task = FrameTask([(G.I_CHECK_MAIN,) + progress, LOBBY, LOBBY])
    task.goto_page = Mock()
    assert task.return_to_chess_lobby()
    assert task.clicked == [task.CHESS_RESULT_CONTINUE]
    task.goto_page.assert_not_called()


def test_navigation_hands_rediscovered_result_back_without_courtyard_action(monkeypatch):
    task = FrameTask([(G.I_CHECK_MAIN,)] * 3 + [(A.I_RANK_PROGRESS,), LOBBY, LOBBY])

    def cached_navigation(self, destination, skip_first_screenshot):
        self.screenshot()
        return None

    monkeypatch.setattr(GameUi, '_refresh_current_page', cached_navigation)
    task.goto_page = Mock(side_effect=lambda dest: task._refresh_current_page(dest, True))
    assert task.return_to_chess_lobby()
    task.goto_page.assert_called_once_with(page_chess)
    assert task.clicked == []  # The rediscovered frame is re-read before acting.


def test_global_navigation_also_advances_rank_track():
    task = FrameTask([(A.I_RANK_TRACK_LEFT, A.I_RANK_TRACK_RIGHT)])
    task.screenshot()
    assert page_chess_result.recognizer.evaluate(task)
    assert ChessBattleNavigationMixin._advance_chess_result_stage(task)
    assert task.clicked == [task.CHESS_RESULT_CONTINUE]


def test_repeated_click_guard_is_preserved():
    task = FrameTask([PANEL])
    task.click = Mock(side_effect=GameTooManyClickError('offline'))
    with pytest.raises(GameTooManyClickError):
        task.return_to_chess_lobby()
    task.device.click_record_clear.assert_not_called()
    task.device.click_record_remove.assert_not_called()


@pytest.mark.parametrize('frames,expected', [
    ([LOBBY, LOBBY, MODAL, (A.I_OPEN_LINEUP,)], [A.I_CHESS_START, A.I_TUTORIAL_SKIP]),
    ([MODAL, (A.I_OPEN_LINEUP,)], [A.I_TUTORIAL_SKIP]),
    ([LOBBY, LOBBY, (A.I_OPEN_LINEUP,)], [A.I_CHESS_START]),
])
def test_entry_skips_tutorial_instead_of_clicking_through(frames, expected):
    task = FrameTask(frames)
    task._wait_until_in_chess_game(timeout=30, retry_start=True)
    assert task.clicked == expected


def test_tutorial_retry_limit():
    task = FrameTask([MODAL] * 4)
    with pytest.raises(GameStuckError, match='after 3 attempts'):
        task._wait_until_in_chess_game(timeout=30, retry_start=True)
    assert task.clicked == [A.I_TUTORIAL_SKIP] * 3


def test_tutorial_without_recognized_skip_does_not_click_start():
    task = FrameTask([LOBBY + (A.I_TUTORIAL_PROMPT,)])
    with pytest.raises(GameStuckError, match='skip button not recognized'):
        task._wait_until_in_chess_game(timeout=30, retry_start=True)
    assert not task.clicked


def notice_task(*, enabled=True, coin_full_exit=True):
    task = object.__new__(ScriptTask)
    notifier = Notifier('provider: bark\nkey: https://example.invalid/offline', enabled)
    notifier.config_name = 'offline'
    task.config = SimpleNamespace(config_name='offline', notifier=notifier,
                                  chess=Chess(chess_config=ChessConfig(coin_full_exit=coin_full_exit)))
    return task


def receipt(code=200):
    response = Response()
    response.status_code = code
    response._content = b'{"code": 200}'
    return response


def test_full_coin_notice_requires_confirmation_and_deduplicates(monkeypatch):
    http = Mock(return_value=receipt())
    monkeypatch.setattr('requests.request', http)
    task = notice_task()
    original_config = dict(task.config.notifier.config)
    original_request = task.config.notifier.notifier.request
    assert not task._notify_weekly_coin_full()
    http.assert_not_called()
    assert task._notify_weekly_coin_full(confirmed=True)
    assert not task._notify_weekly_coin_full(confirmed=True)
    http.assert_called_once()
    assert http.call_args.kwargs['timeout'] == (3, 5)
    assert '600/600' in http.call_args.kwargs['data']['body']
    assert task.config.notifier.config == original_config
    assert task.config.notifier.notifier.request == original_request


def test_notice_does_not_depend_on_stop_option(monkeypatch):
    http = Mock(return_value=receipt())
    monkeypatch.setattr('requests.request', http)
    assert notice_task(coin_full_exit=False)._notify_weekly_coin_full(confirmed=True)
    http.assert_called_once()


def test_notice_failure_has_three_attempts_total(monkeypatch):
    http = Mock(return_value=receipt(500))
    monkeypatch.setattr('requests.request', http)
    task = notice_task()
    assert not task._notify_weekly_coin_full(confirmed=True)
    assert not task._notify_weekly_coin_full(confirmed=True)
    assert http.call_count == 3


def test_disabled_notice_does_not_send(monkeypatch):
    http = Mock()
    monkeypatch.setattr('requests.request', http)
    assert not notice_task(enabled=False)._notify_weekly_coin_full(confirmed=True)
    http.assert_not_called()


def test_failed_notice_keeps_next_monday_schedule_and_resets_on_new_run(monkeypatch):
    http = Mock(return_value=receipt(500))
    monkeypatch.setattr('requests.request', http)
    task = notice_task()
    task.start_time = datetime.now()
    task.goto_page = Mock()
    task.screenshot = Mock()
    task._recover_interrupted_chess_game = Mock()
    task._coin_is_full = Mock(return_value=True)
    task.set_next_run = Mock()
    task.run_one_game = Mock()
    for run in range(2):
        with pytest.raises(TaskEnd):
            task._run_chess_task()
        assert http.call_count == 3 * (run + 1)
        target = task.set_next_run.call_args.kwargs['target']
        assert target.weekday() == 0 and target > task.start_time
    task.run_one_game.assert_not_called()


def test_notice_enabled_without_stop_keeps_playing_and_notifies_once(monkeypatch):
    http = Mock(return_value=receipt())
    monkeypatch.setattr('requests.request', http)
    task = notice_task(coin_full_exit=False)
    task.start_time = datetime.now()
    task.goto_page = Mock()
    task.screenshot = Mock()
    task._recover_interrupted_chess_game = Mock()
    task._coin_is_full = Mock(return_value=True)
    task.set_next_run = Mock()
    task.return_to_chess_lobby = Mock()
    task.run_one_game = Mock(return_value=5)
    with pytest.raises(TaskEnd):
        task._run_chess_task()
    task.run_one_game.assert_called_once_with()
    http.assert_called_once()
    task.set_next_run.assert_called_once_with(task='Chess', success=True, finish=True)


def test_coin_notice_after_two_protection_exits_keeps_monday_schedule(monkeypatch):
    monkeypatch.setattr('requests.request', Mock(return_value=receipt()))
    task = notice_task()
    task.config.chess.chess_config.rank_protection = True
    task.start_time = datetime.now()
    task.goto_page = Mock()
    task.screenshot = Mock()
    task._recover_interrupted_chess_game = Mock()
    task._coin_is_full = Mock(side_effect=[False, True])
    task.set_next_run = Mock()
    task.return_to_chess_lobby = Mock()
    task._restart_chess_game_from_result = Mock(return_value=True)

    def run_game():
        task._rank_protection_exit_succeeded = task._rank_protection_exit_requested
        return None if task._rank_protection_exit_requested else 1

    task.run_one_game = Mock(side_effect=run_game)
    with pytest.raises(TaskEnd):
        task._run_chess_task()
    assert task.run_one_game.call_count == 3
    assert task._coin_notice_sent
    assert task.set_next_run.call_args.kwargs['target'].weekday() == 0
