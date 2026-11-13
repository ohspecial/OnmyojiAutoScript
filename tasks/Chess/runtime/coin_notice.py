"""Confirmed full-coin notices, deduplicated within a Chess task invocation."""

from copy import deepcopy
from datetime import datetime
import time

import requests

from module.logger import logger


class ChessCoinNoticeMixin:
    def _check_full_coins_and_notify(self) -> bool:
        full = self._coin_is_full()
        if full:
            self._notify_weekly_coin_full(confirmed=True)
        return full

    def _notify_weekly_coin_full(self, *, confirmed=False, now=None) -> bool:
        """Use the configured notifier without changing its shared settings.

        A new task invocation may notify again, including after switching game
        accounts. Notification failure must not prevent next-Monday scheduling.
        """
        if confirmed is not True or getattr(self, '_coin_notice_sent', False):
            return False
        if getattr(self, '_coin_notice_attempts', 0) >= 3:
            return False
        try:
            notifier = self.config.notifier
            if not notifier.enable:
                return False
            notifier = deepcopy(notifier)
            provider = notifier.notifier

            def bounded_request(method, endpoint, **kwargs):
                kwargs['timeout'] = (3, 5)
                return requests.request(method, endpoint, **kwargs)

            # OnePush HTTP providers all use this hook. Keep it on the copy so
            # subsequent error notifications retain their original transport.
            provider.request = bounded_request
            account = getattr(self.config, 'config_name', '')
            confirmed_at = (now or datetime.now()).isoformat(timespec='seconds')
            while getattr(self, '_coin_notice_attempts', 0) < 3:
                self._coin_notice_attempts = getattr(self, '_coin_notice_attempts', 0) + 1
                try:
                    accepted = notifier.push(
                        title='百鬼棋局鼬乐币已核验600/600',
                        content=f'本次任务已核验当周鼬乐币600/600\n脚本：{account}\n核验时间：{confirmed_at}',
                    ) is True
                except Exception:
                    accepted = False
                if accepted:
                    self._coin_notice_sent = True
                    logger.info('Chess full-coin notification accepted')
                    return True
                if self._coin_notice_attempts < 3:
                    time.sleep(0.5)
            logger.warning('Chess full-coin notification failed after three attempts')
        except Exception:
            logger.warning('Chess full-coin notification unavailable; scheduling is unchanged')
        return False
