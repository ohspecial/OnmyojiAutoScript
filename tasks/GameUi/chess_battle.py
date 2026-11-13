from __future__ import annotations

"""百鬼棋局局内页面的全局恢复与退出流程。"""

import time
import random

from module.atom.click import RuleClick
from module.exception import GameStuckError
from module.logger import logger
from tasks.Chess.assets import ChessAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GlobalGame.assets import GlobalGameAssets


class ChessBattleNavigationMixin:
    """让所有继承 GameUi 的任务都能退出遗留的百鬼棋局。"""

    CHESS_EXIT_TIMEOUT = 60.0
    CHESS_EXIT_SCREENSHOT_INTERVAL = 0.35
    CHESS_EXIT_MAX_ATTEMPTS = 3
    CHESS_LOBBY_CONFIRM_FRAMES = 2
    I_CHESS_SHARE_PANEL_BAR = GameUiAssets.I_CHESS_SHARE_PANEL_BAR
    I_CHESS_SHARE_PANEL_CLOSE = GameUiAssets.I_CHESS_SHARE_PANEL_CLOSE
    I_CHESS_RESULT_CONTINUE_HINT = ChessAssets.I_RESULT_CONTINUE_HINT
    # Keep result clicks clear of the overlapping share/start buttons.
    CHESS_RESULT_CONTINUE = RuleClick(
        roi_front=(24, 150, 40, 280), roi_back=(24, 150, 40, 280),
        name='CHESS_RESULT_CONTINUE',
    )

    def select_chess_sixrealms_if_visible(self) -> bool:
        """完成开局必选场地；选定同一项后最多点击两次，等待页面消失。"""
        if not self.appear(ChessAssets.I_SELECT_SIXREALMS):
            return False
        target = random.choice((ChessAssets.C_SIXREALMS_1,
                                ChessAssets.C_SIXREALMS_2,
                                ChessAssets.C_SIXREALMS_3))
        click_limit = random.randint(1, 2)
        logger.info(f'Chess six-realms selection: target={target.name}, clicks={click_limit}')
        deadline = time.monotonic() + self.CHESS_EXIT_TIMEOUT
        clicks = 0
        while time.monotonic() < deadline:
            if not self.appear(ChessAssets.I_SELECT_SIXREALMS):
                logger.info('Chess six-realms selection completed')
                return True
            if clicks < click_limit:
                self.device.click_record_remove(target)
                self.click(target)
                clicks += 1
            self.device.stuck_record_clear()
            time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
            self.screenshot()
        raise GameStuckError('Chess: six-realms selection did not disappear after choosing a field')

    def _close_unknown_chess_result_page(self) -> bool:
        """结算未知页面出现红色返回时，关闭后重新识别页面。"""
        if self.chess_result_flow_visible() or self.appear(ChessAssets.I_RESTART_AGAIN):
            return False
        if not self.appear(ChessAssets.I_BACK_RED):
            return False
        logger.warning('Chess result flow: close unknown page with red back button')
        self._chess_share_advancing = False
        self.click(ChessAssets.I_BACK_RED, interval=0.8)
        return True

    def chess_share_panel_visible(self) -> bool:
        """棋局分享标志、平台栏和右上关闭按钮同时出现才关闭面板。"""
        return (
            self.appear(ChessAssets.I_SHARE)
            and self.appear(self.I_CHESS_SHARE_PANEL_BAR)
            and self.appear(self.I_CHESS_SHARE_PANEL_CLOSE)
        )

    def chess_lobby_visible(self) -> bool:
        """开战按钮匹配前先排除结算；两个旧标志都来自同一按钮。"""
        return (
            not self.chess_result_page_visible()
            and self.appear(self.I_CHECK_CHESS)
            and self.appear(ChessAssets.I_CHESS_START)
        )

    def _click_chess_result_continue(self) -> None:
        self.click(self.CHESS_RESULT_CONTINUE, interval=1.5)

    def chess_result_continue_visible(self) -> bool:
        """The result-specific hint and share icon jointly identify the rank screen."""
        return (self.appear(self.I_CHESS_RESULT_CONTINUE_HINT)
                and self.appear(ChessAssets.I_SHARE))

    def _chess_reward_visible(self) -> bool:
        return (self.appear(ChessAssets.I_REWARD_CHESS)
                or self.appear(GlobalGameAssets.I_UI_REWARD))

    def _chess_rank_progress_visible(self) -> bool:
        return (self.appear(ChessAssets.I_RANK_PROGRESS)
                or (self.appear(ChessAssets.I_RANK_TRACK_LEFT)
                    and self.appear(ChessAssets.I_RANK_TRACK_RIGHT)))

    def _advance_chess_result_stage(self) -> bool:
        """优先处理奖励和分享阶段，避免背景被识别成大厅。"""
        if self._chess_rank_progress_visible():
            self._click_chess_result_continue()
            return True
        if self.chess_share_panel_visible():
            self._chess_share_advancing = True
            logger.info('Chess share panel detected; close the panel without sharing')
            self.click(self.I_CHESS_SHARE_PANEL_CLOSE, interval=1.5)
            return True
        if self.chess_result_continue_visible():
            self._chess_share_advancing = True
            self._click_chess_result_continue()
            return True
        if self._chess_reward_visible():
            self._chess_share_advancing = False
            self._click_chess_result_continue()
            return True
        # 过渡帧可能仍保留“分享”图标；明确的排名/返回按钮比该图标
        # 更能确定下一步，交回调用方处理，保留“再来一局”原流程。
        if any(self.appear(marker) for marker in (
            ChessAssets.I_RESTART_AGAIN,
            self.I_CHECK_CHESS_RANK,
            self.I_CHESS_RANK_GOTO_LOBBY,
            self.I_CHESS_EXIT_TO_LOBBY,
            self.I_CHESS_EXIT_TO_LOBBY_2,
        )):
            self._chess_share_advancing = False
            return False
        if self.appear(ChessAssets.I_SHARE):
            self._chess_share_advancing = True
        elif getattr(self, '_chess_share_advancing', False):
            if self.chess_lobby_visible():
                self._chess_share_advancing = False
        if getattr(self, '_chess_share_advancing', False):
            # 分享标志消失后仍推进未知过渡画面。保持规则名称和点击
            # 记录不变，让设备层的过多点击检查正常生效。
            if self._close_unknown_chess_result_page():
                return True
            self._click_chess_result_continue()
            return True
        return False

    def chess_result_page_visible(self) -> bool:
        """检测百鬼棋局任一结算、分享或排名页面。"""
        return (
            self._chess_rank_progress_visible()
            or self.chess_share_panel_visible()
            or self.appear(self.I_CHESS_EXIT_TO_LOBBY)
            or self.appear(self.I_CHESS_EXIT_TO_LOBBY_2)
            or self._chess_reward_visible()
            or self.appear(ChessAssets.I_SHARE)
            or self.appear(self.I_CHECK_CHESS_RANK)
            or self.appear(self.I_CHESS_RANK_GOTO_LOBBY)
            or self.appear(ChessAssets.I_RESTART_AGAIN)
        )

    def chess_result_flow_visible(self) -> bool:
        """检测百鬼棋局大厅或任一结算页面。"""
        return (
            self.chess_lobby_visible()
            or self.chess_result_page_visible()
        )

    def return_to_chess_lobby(self) -> bool:
        """完成返回按钮、分享页与排名页流程，最终回到棋局大厅。"""
        logger.debug('Global Chess result flow: return to lobby')
        self._chess_share_advancing = False
        deadline = time.monotonic() + self.CHESS_EXIT_TIMEOUT
        share_seen = False
        exit_clicked = False
        safe_clicks = 0
        lobby_frames = 0
        next_rank_safe_click_at = 0.0
        fallback_exit_at = time.monotonic() + 1.5

        while time.monotonic() < deadline:
            self.device.stuck_record_clear()
            self.screenshot()

            if self._advance_chess_result_stage():
                lobby_frames = 0
                exit_clicked = True
                share_seen = True
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            if self.chess_lobby_visible():
                lobby_frames += 1
                if lobby_frames >= self.CHESS_LOBBY_CONFIRM_FRAMES:
                    logger.debug('Global Chess result flow: stable lobby reached')
                    return True
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue
            lobby_frames = 0

            rank_page = self.appear(self.I_CHECK_CHESS_RANK)
            rank_button = self.appear(self.I_CHESS_RANK_GOTO_LOBBY)
            if rank_page or rank_button:
                if rank_button:
                    self.appear_then_click(
                        self.I_CHESS_RANK_GOTO_LOBBY,
                        interval=1.5,
                    )
                elif time.monotonic() >= next_rank_safe_click_at:
                    # 部分结算只显示“点击空白处继续”，没有返回大厅按钮。
                    logger.info(
                        'Global Chess result flow: advance rank page with '
                        'safe click'
                    )
                    self._click_chess_result_continue()
                    safe_clicks += 1
                    next_rank_safe_click_at = time.monotonic() + 1.5
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            if self._close_unknown_chess_result_page():
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            # 奖励弹窗推进不代表真实返回按钮已经按下；只要按钮仍被
            # 当前帧识别到，就按主仓库间隔规则处理，不被历史标志跳过。
            if (
                not exit_clicked
                or self.appear(self.I_CHESS_EXIT_TO_LOBBY)
                or self.appear(self.I_CHESS_EXIT_TO_LOBBY_2)
            ):
                if self.appear(self.I_CHESS_EXIT_TO_LOBBY):
                    self.appear_then_click(
                        self.I_CHESS_EXIT_TO_LOBBY,
                        interval=1.5,
                    )
                    exit_clicked = True
                    time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                    continue
                if self.appear(self.I_CHESS_EXIT_TO_LOBBY_2):
                    self.appear_then_click(
                        self.I_CHESS_EXIT_TO_LOBBY_2,
                        interval=1.5,
                    )
                    exit_clicked = True
                    time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                    continue
                if self.appear(ChessAssets.I_SHARE):
                    exit_clicked = True
                    share_seen = True
                    continue
                if time.monotonic() >= fallback_exit_at:
                    logger.warning(
                        'Global Chess result flow: return image missed; '
                        'click fixed return area'
                    )
                    self.click(self.I_CHESS_EXIT_TO_LOBBY)
                    exit_clicked = True
                    time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                    continue
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            if not share_seen and self.appear(ChessAssets.I_SHARE):
                share_seen = True

            if not share_seen:
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            safe_clicks += 1
            self._click_chess_result_continue()
            time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)

        raise GameStuckError('Global Chess: failed to return to lobby after result')

    def Chess_Exit(self, return_to_lobby: bool = True) -> bool:
        """有限重试退出并等待结算；超时交给卡死恢复，避免重复进入后继续连点。"""
        logger.warning('Global Chess page handler: exit interrupted battle')
        deadline = time.monotonic() + self.CHESS_EXIT_TIMEOUT
        exit_clicks = 0
        confirm_clicks = 0
        unrecognized_confirm_logged = False
        while time.monotonic() < deadline:
            self.device.stuck_record_clear()
            self.screenshot()

            # 必选场地结束前，不能尝试退出或确认退出。
            if self.select_chess_sixrealms_if_visible():
                deadline = time.monotonic() + self.CHESS_EXIT_TIMEOUT
                continue

            # 弹窗出现后只处理确认，不能因点击间隔未到而再次点击背景退出入口。
            if self.appear(self.I_CHESS_EXIT_CONFIRM):
                if (confirm_clicks < self.CHESS_EXIT_MAX_ATTEMPTS
                        and self.appear_then_click(self.I_CHESS_EXIT_CONFIRM, interval=0.8)):
                    confirm_clicks += 1
                    if confirm_clicks == self.CHESS_EXIT_MAX_ATTEMPTS:
                        logger.warning('Chess exit confirmation retry limit reached; wait for result')
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue
            if self.chess_result_page_visible():
                logger.debug('Chess_Exit: result page reached')
                if return_to_lobby:
                    return self.return_to_chess_lobby()
                return True

            # 取消按钮也能证明退出弹窗存在；确认漏识别时等待，不点被遮挡的入口。
            if self.appear(self.I_CHESS_EXIT_CANCEL):
                if not unrecognized_confirm_logged:
                    logger.warning('Chess exit dialog visible but confirmation button not recognized')
                    unrecognized_confirm_logged = True
                time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)
                continue

            if (exit_clicks < self.CHESS_EXIT_MAX_ATTEMPTS
                    and self.appear_then_click(self.I_CHESS_EXIT, interval=6)):
                exit_clicks += 1
                if exit_clicks == self.CHESS_EXIT_MAX_ATTEMPTS:
                    logger.warning('Chess exit entry retry limit reached; wait for dialog or result')
            time.sleep(self.CHESS_EXIT_SCREENSHOT_INTERVAL)

        raise GameStuckError(
            f'Chess: failed to exit within {self.CHESS_EXIT_TIMEOUT:.0f}s; '
            f'exit_clicks={exit_clicks}, confirm_clicks={confirm_clicks}'
        )


def handle_chess_battle_page(task) -> bool:
    """GameUi 页面边动作：退出棋局战斗并返回棋局大厅。"""
    return task.Chess_Exit()


def handle_chess_result_page(task) -> bool:
    """GameUi 页面边动作：完成遗留结算并返回棋局大厅。"""
    return task.return_to_chess_lobby()
