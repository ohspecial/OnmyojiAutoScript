from time import sleep

from module.base.timer import Timer
from module.logger import logger
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher
from tasks.GameUi.page import all_of


class NormalClimbAct(BaseAct):
    """普通爬塔活动"""

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(self.I_CHECK_BATTLE_MAIN, self.I_ACT_FIRE, self.I_AS_BOSS_FIRE)

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        page_act_pass = self.navigator.resolve_page(pages.page_act_pass)
        page_act_ap = self.navigator.resolve_page(pages.page_act_ap)
        page_act_map = self.navigator.resolve_page(pages.page_act_map)
        self._challenge_type = None

        # 本期门票和体力使用独立入口，修改当前任务的页面副本。
        page_act.remove_transition(destination=page_act_map)
        page_act_map.clear_transitions()
        page_act_map.recognizer = None
        for climb_type, page, enter in (
            ("pass", page_act_pass, self._enter_pass_challenge),
            ("ap", page_act_ap, self._enter_ap_challenge),
        ):
            page.clear_transitions()
            page.on_enter_failure.clear()
            page.recognizer = all_of(
                self.I_CHECK_BATTLE_MAIN,
                lambda task, mode=climb_type: task._challenge_type == mode,
            )
            page_act.connect(page, enter, key=f"page_act->page_act_{climb_type}")
            page.connect(
                page_act, self._return_to_activity,
                key=f"page_act_{climb_type}->page_act",
            )
        self.navigator.add_unknown_closer(self.I_UI_BACK_CIRCLE)
        # 启动时先返回活动主页，确定当前进入的是哪一种挑战。
        self.goto_page(pages.page_act)

    def _enter_pass_challenge(self) -> bool:
        timer = Timer(60).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_BATTLE_MAIN):
                self._challenge_type = "pass"
                return True
            if self.appear(self.I_UI_BACK_RED) and self.appear(self.I_PASS_4):
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5):
                continue
            if self.appear_then_click(self.I_TO_BATTLE_MAIN_2, interval=1.5):
                continue
            if not self.appear(self.I_PASS_3):
                continue
            if self.appear_then_click(self.I_PASS_1, interval=1.5):
                continue
            if self.appear_then_click(self.I_PASS_2, interval=1.5):
                continue
        else:
            logger.warning("Enter occupation reward screen timed out")
            return False

        logger.info("Enter occupation reward screen")
        clicks = [self.C_PASS_5, self.C_PASS_6, self.C_PASS_7, self.C_PASS_8, self.C_PASS_9]
        index = 0
        timer.reset()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_BATTLE_MAIN):
                self._challenge_type = "pass"
                logger.info("Enter challenge screen")
                return True
            if self.click(clicks[index], interval=1.5):
                sleep(1)
            index = (index + 1) % len(clicks)
        logger.warning("Enter pass challenge screen timed out")
        return False

    def _enter_ap_challenge(self) -> bool:
        if not self.ui_click(
            self.I_TO_BATTLE_MAIN, stop=self.I_CHECK_BATTLE_MAIN,
            interval=1, timeout=30,
        ):
            return False
        self._challenge_type = "ap"
        return True

    def _return_to_activity(self) -> bool:
        timer = Timer(30).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_TO_BATTLE_MAIN):
                self._challenge_type = None
                return True
            if self.appear_then_click(self.I_UI_BACK_CIRCLE, interval=1.5):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2.5):
                continue
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.5):
                continue
        logger.warning("Return to activity screen timed out")
        return False

    def lock_team(self, battle_conf: GeneralBattleConfig):
        enable = battle_conf.lock_team_enable
        lock_rule = self.I_LOCK
        unlock_rule = self.I_UNLOCK
        if enable:
            logger.info(f"Lock {self.climb_type} team")
            self.ui_click(unlock_rule, stop=lock_rule, interval=1.5)
            return
        logger.info(f"Unlock {self.climb_type} team")
        self.ui_click(lock_rule, stop=unlock_rule, interval=1.5)
