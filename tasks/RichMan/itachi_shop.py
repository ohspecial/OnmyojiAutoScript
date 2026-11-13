# This Python file uses the following encoding: utf-8
"""鼬乐礼盒购买，适配自 luchi5/OnmyojiAutoScript 的 5213cc85 提交。"""
import time

from module.logger import logger
from tasks.Chess.assets import ChessAssets
from tasks.Component.Buy.buy import Buy
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_entertainment
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import ItachiCoinShop as ItachiCoinShopConfig
from tasks.RichMan.page import page_itachi_shop


class ItachiCoinShop(Buy, GameUi, RichManAssets):
    """用鼬乐币依次购买自动前移的礼盒，每次最多三个。"""

    ENTERTAINMENT_OVERLAY_TIMEOUT = 8.0
    ENTERTAINMENT_STABLE_TIME = 1.0
    GIFT_DIALOG_TIMEOUT = 3.0
    PURCHASE_RESULT_TIMEOUT = 8.0
    PURCHASE_RETURN_GRACE = 3.0
    REWARD_DISMISS_TIMEOUT = 5.0
    MAX_GIFT_PURCHASES = 3

    def execute_itachi_coin_shop(self, con: ItachiCoinShopConfig) -> None:
        if con is None or not con.itachi_coin_buy_jade:
            logger.info('Itachi coin purchase is disabled')
            return

        logger.hr('Start Itachi coin shop', 1)
        self.goto_page(page_entertainment)
        if not self._wait_entertainment_overlay_closed():
            logger.warning('Itachi Park overlay did not close; skip coin purchase')
            return

        self.goto_page(page_itachi_shop)
        purchased = 0
        for _ in range(self.MAX_GIFT_PURCHASES):
            # 买完一个后商品会前移；每轮只点一次，已售罄或无响应就停止。
            if not self._open_front_gift_once():
                logger.info('未出现礼盒购买框，停止本次购买；可能已购完或界面未响应')
                break
            if not self._buy_opened_gift():
                break
            purchased += 1

        logger.info(f'Itachi coin gifts purchased: {purchased}')
        self.goto_page(page_entertainment)

    def _wait_entertainment_overlay_closed(self) -> bool:
        """先关闭鼬乐园附属页面，稳定一秒后才允许进入商店。"""
        deadline = time.monotonic() + self.ENTERTAINMENT_OVERLAY_TIMEOUT
        stable_since = None
        while time.monotonic() < deadline:
            self.screenshot()
            if self.appear(ChessAssets.I_SKIP):
                self.appear_then_click(ChessAssets.I_SKIP, interval=0.5)
                stable_since = None
                continue
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= self.ENTERTAINMENT_STABLE_TIME:
                return True
        return False

    def _open_front_gift_once(self) -> bool:
        """确认仍在商店后，只点击一次礼盒并等待购买框。"""
        self.screenshot()
        if not self.appear(self.I_ITACHI_SHOP_CHECK):
            logger.warning('Itachi shop marker lost; stop gift purchase')
            return False
        self.click(self.C_ITACHI_GIFT)
        deadline = time.monotonic() + self.GIFT_DIALOG_TIMEOUT
        while time.monotonic() < deadline:
            self.screenshot()
            if self.appear(self.I_BUY_PLUS):
                return True
        return False

    def _read_itachi_coin(self) -> tuple[int, int] | None:
        result = self.O_ITACHI_COIN.ocr(self.device.image)
        # 本地 DigitCounter 返回（当前、剩余、总数）；识别异常不能当作余额。
        if isinstance(result, (tuple, list)) and len(result) == 3:
            current, remaining, total = result
            if (all(type(value) is int for value in result)
                    and current >= 0 and remaining >= 0 and total > 0
                    and current + remaining == total):
                logger.info(f'Itachi coin: {current}/{total}')
                return current, total
        logger.warning(f'Itachi coin OCR failed: {result}')
        return None

    def _read_buy_cost(self) -> int | None:
        result = self.O_ITACHI_BUY_COST.ocr(self.device.image)
        if type(result) is int and result > 0:
            logger.info(f'Itachi gift cost: {result}')
            return result
        logger.warning(f'Itachi gift cost OCR failed: {result}')
        return None

    def _buy_opened_gift(self) -> bool:
        """只确认一次购买；等待奖励并核对扣币后才购买下一个。"""
        self.screenshot()
        if not self.appear(self.I_BUY_PLUS) or self.appear(self.I_BUY_RMB):
            logger.warning('Itachi gift purchase dialog unverified; stop purchase')
            return False
        before_coin = self._read_itachi_coin()
        cost = self._read_buy_cost()
        if before_coin is None or cost is None or before_coin[0] < cost:
            logger.warning('Itachi gift balance/cost unverified or insufficient; skip purchase')
            return False
        self.click(self.C_BUY_MORE)

        deadline = time.monotonic() + self.PURCHASE_RESULT_TIMEOUT
        dialog_absent_since = None
        while time.monotonic() < deadline:
            self.screenshot()
            if self.appear(self.I_UI_REWARD, threshold=0.6):
                if not self._dismiss_purchase_reward():
                    return False
                return self._verify_coin_cost(before_coin, cost)
            if self.appear(self.I_BUY_PLUS):
                dialog_absent_since = None
                continue
            # 返回商店不等于购买成功，留出奖励动画出现的时间后再判失败。
            if dialog_absent_since is None:
                dialog_absent_since = time.monotonic()
            elif time.monotonic() - dialog_absent_since >= self.PURCHASE_RETURN_GRACE:
                logger.warning('Itachi gift purchase failed or coin is insufficient')
                return False
        logger.warning('Itachi gift purchase result timeout')
        return False

    def _dismiss_purchase_reward(self) -> bool:
        deadline = time.monotonic() + self.REWARD_DISMISS_TIMEOUT
        while time.monotonic() < deadline:
            self.screenshot()
            if not self.appear(self.I_UI_REWARD, threshold=0.6):
                return True
            self.ui_reward_appear_click()
        logger.warning('Itachi gift reward did not close')
        return False

    def _verify_coin_cost(self, before_coin: tuple[int, int], cost: int) -> bool:
        self.screenshot()
        after_coin = self._read_itachi_coin()
        if after_coin is None:
            return False
        consumed = before_coin[0] - after_coin[0]
        if before_coin[1] == after_coin[1] and consumed == cost:
            logger.info(f'Itachi gift purchase confirmed: consumed={consumed}')
            return True
        # 扣币不符时保留现场日志并停止，避免把不确定结果当成下一轮购买依据。
        logger.warning(
            f'Itachi gift coin change mismatch: before={before_coin[0]}, '
            f'after={after_coin[0]}, cost={cost}'
        )
        return False
