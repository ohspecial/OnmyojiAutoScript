# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta
import random

from cached_property import cached_property

from module.atom.image import RuleImage
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import ActivityShikigami, GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_battle, page_failed, page_reward
from tasks.base_task import BaseTask
import tasks.ActivityShikigami.page as pages


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class TicketsNotEnough(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0
    _count_map = None
    _pre_tickets_map = None

    @cached_property
    def conf(self) -> ActivityShikigami:
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._count_map

    @property
    def pre_tickets_map(self) -> dict[str, int]:
        if not getattr(self, "_pre_tickets_map", None):
            self._pre_tickets_map = {climb_type: -1 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._pre_tickets_map

    def update_status(self):
        def get_count() -> int:
            return self.count_map[self.climb_type]

        def get_limit() -> int:
            limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
            return 0 if not limit else limit

        if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        if get_count() >= get_limit():
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            return False
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class ScriptTask(StateMachine, GameUi, GeneralBattle, SwitchSoul, ActivityShikigamiAssets):
    """
    更新前请先看 ./README.md
    """

    def run(self) -> None:
        self.limit_time: timedelta = self.conf.general_climb.limit_time_v
        for climb_type in self.conf.general_climb.run_sequence_v:
            try:
                logger.hr(f'Start run {self.climb_type}', 1)
                dest_page = getattr(pages, f'page_act_{climb_type}', None)
                if dest_page is None:
                    logger.warning(f'{climb_type} page is not supported')
                    continue
                self.ui_goto_page(dest_page)
                cur_battle_conf = getattr(self.conf, f'{climb_type}_battle_conf')
                if cur_battle_conf is None:
                    logger.warning(f'{climb_type} battle config is not supported')
                    continue
                self.lock_team(cur_battle_conf)
                unknown_page_timer = Timer(10)
                while True:
                    self.update_status()
                    current_page = self.ui_get_current_page()
                    if current_page == pages.page_act_pass:
                        self._run_pass()
                    elif current_page == pages.page_act_ap:
                        self._run_ap()
                    elif current_page == pages.page_act_ap100:
                        self._run_ap100()
                    elif current_page == pages.page_act_boss:
                        self._run_boss()
                    elif current_page == page_battle:
                        self.run_general_battle(cur_battle_conf)
                    elif current_page == page_reward or current_page == page_failed:
                        self.click(pages.random_click(ltrb=(False, False, True, False)), interval=1.5)
                    else:
                        if not unknown_page_timer.started():
                            unknown_page_timer.start()
                        if unknown_page_timer.reached():
                            self.ui_goto_page(dest_page)
            except (LimitCountOut, LimitTimeOut, TicketsNotEnough):
                pass
            finally:
                self.switch_next()
        logger.hr("Exit Act", 2)
        self.ui_goto_page(pages.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        self._run_common()

    def _run_ap(self):
        self._run_common()

    def _run_ap100(self):
        self._run_common()

    def _run_boss(self):
        self._run_common()

    def _run_common(self):
        if not self.check_tickets_enough():
            logger.warning('No tickets left, wait for next time')
            raise TicketsNotEnough
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS)
        if self.conf.general_climb.random_sleep:
            random_sleep(probability=0.2)
        if self.enter_battle():
            self.run_general_battle(getattr(self.conf, f'{self.climb_type}_battle_conf'))

    def enter_battle(self):
        click_times, max_times = 0, random.randint(3, 5)
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if click_times >= max_times:
                logger.warning(f'{self.climb_type} cannot enter battle, click reach max times')
                raise TicketsNotEnough
            if self.appear(self.I_UI_BACK_RED, interval=1):
                logger.warning(
                    f'{self.climb_type} cannot enter battle, appear red close button, maybe not enough tickets'
                )
                raise TicketsNotEnough
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or self.appear_then_click(
                self.I_UI_CONFIRM, interval=1
            ):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=1.5):
                self.device.click_record_clear()
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue

    def switch_soul(self, enter_button: RuleImage):
        if self.switch_souled.get(self.climb_type, False):
            return
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        self.switch_souled[self.climb_type] = True
        logger.hr('Start switch soul', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.ui_goto(getattr(pages, f"page_act_{self.climb_type}"))

    def lock_team(self, battle_conf: GeneralBattleConfig):
        enable = battle_conf.lock_team_enable
        if enable:
            logger.info(f'Lock {self.climb_type} team')
            match self.climb_type:
                case 'ap':
                    self.ui_click(self.I_AP_UNLOCK, stop=self.I_AP_LOCK, interval=1.5)
                case _:
                    self.ui_click(self.I_UNLOCK, stop=self.I_LOCK, interval=1.5)
            return
        logger.info(f'Unlock {self.climb_type} team')
        match self.climb_type:
            case 'ap':
                self.ui_click(self.I_AP_LOCK, stop=self.I_AP_UNLOCK, interval=1.5)
            case _:
                self.ui_click(self.I_LOCK, stop=self.I_UNLOCK, interval=1.5)

    def check_tickets_enough(self) -> bool:
        logger.hr(f'Check {self.climb_type} tickets')
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        if self.climb_type == 'boss':
            remain_times = self.O_REMAIN_BOSS.ocr_digit(self.device.image)
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0


if __name__ == '__main__':
    print([1, 2, 3][2])
