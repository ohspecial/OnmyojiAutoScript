from time import sleep

from module.atom.ocr import RuleOcr
from module.base.timer import Timer
from module.logger import logger
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher
from tasks.GameUi.page import all_of, not_


class _MapEntryOcr(RuleOcr):
    def filter(self, boxed_results, keyword=None):
        # 大范围内含多个入口，必须命中完整名称，不能沿用通用 OCR 的单字兜底。
        keyword = self.keyword if keyword is None else keyword
        return [
            index for index, result in enumerate(boxed_results)
            if keyword in "".join(result.ocr_text.split())
        ]


class NormalClimbAct(BaseAct):
    """普通爬塔活动"""

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(
            self.I_CHECK_BATTLE_MAIN, self.I_CLIMB_MODE_AP100,
            self.I_ACT_FIRE, self.I_AS_BOSS_FIRE,
        )

    def _activity_home_matcher(self):
        return all_of(
            not_(pages.any_of(self.I_CHECK_BATTLE_MAIN, self.I_CLIMB_MODE_AP100)),
            self.O_ENTER_MAP,
        )

    def _activity_map_matcher(self):
        return all_of(
            not_(pages.any_of(self.I_CHECK_BATTLE_MAIN, self.I_CLIMB_MODE_AP100)),
            pages.any_of(
                self.O_MAP_TITLE, self.O_ENTER_PASS, self.O_ENTER_AP, self.O_ENTER_AP100,
            ),
        )

    def before_run(self):
        super().before_run()
        for name in ("O_ENTER_PASS", "O_ENTER_AP", "O_ENTER_AP100"):
            rule = getattr(self, name)
            # 每个任务实例独立保存 OCR 得到的点击位置。
            setattr(self, name, _MapEntryOcr(
                name=rule.name, mode="Full", method=rule.method,
                roi=rule.roi, area=rule.roi, keyword=rule.keyword,
            ))
        page_act = self.navigator.resolve_page(pages.page_act)
        page_act_pass = self.navigator.resolve_page(pages.page_act_pass)
        page_act_ap = self.navigator.resolve_page(pages.page_act_ap)
        page_act_ap100 = self.navigator.resolve_page(pages.page_act_ap100)
        page_act_map = self.navigator.resolve_page(pages.page_act_map)
        self._challenge_type = None
        self._map_ticket_counts = {}

        # 活动主页只负责进入磐长故地；三个副本都从地图进入和切换。
        # 只调整当前任务的页面副本，保留其他活动的全局页面定义。
        page_act.recognizer = self._activity_home_matcher()
        page_act.remove_transition(destination=page_act_map)
        page_act.connect(page_act_map, self.O_ENTER_MAP, key="page_act->page_act_map")
        page_act_map.clear_transitions()
        page_act_map.recognizer = self._activity_map_matcher()
        # 阵前战报弹窗不遮挡地图标题，到达地图时也要尝试关闭。
        page_act_map.add_enter_success_hooks(self.I_UI_BACK_RED)
        page_act_map.add_enter_failure_hooks(self.I_UI_BACK_RED)
        page_act_map.connect(
            page_act, self.I_UI_BACK_CIRCLE, key="page_act_map->page_act",
        )
        for climb_type, page, enter, recognizer in (
            ("pass", page_act_pass, self._enter_pass_challenge, self.I_CHECK_BATTLE_MAIN),
            ("ap", page_act_ap, self._enter_ap_challenge, self.I_CHECK_BATTLE_MAIN),
            ("ap100", page_act_ap100, self._enter_ap100_challenge, self.I_CLIMB_MODE_AP100),
        ):
            page.clear_transitions()
            page.on_enter_failure.clear()
            page.recognizer = all_of(
                recognizer,
                lambda task, mode=climb_type: task._challenge_type == mode,
            )
            page_act_map.connect(page, enter, key=f"page_act_map->page_act_{climb_type}")
            page.connect(
                page_act_map, self._return_to_activity_map,
                key=f"page_act_{climb_type}->page_act_map",
            )
        self.navigator.add_unknown_closer(self.I_UI_BACK_RED, self.I_UI_BACK_CIRCLE)
        # 启动时先返回副本切换地图，确定当前进入的是哪一种挑战。
        self.goto_page(pages.page_act_map)

    def _capture_map_tickets(self, mode: str):
        """进入副本前读取地图次数，避免旧副本 OCR 空值被当成零票。"""
        rule = getattr(self, f"O_MAP_REMAIN_{mode.upper()}")
        self._map_ticket_counts.pop(mode, None)
        for attempt in range(3):
            text = rule.ocr_single(self.device.image).strip()
            if text.isdecimal():
                remaining = int(text)
                self._map_ticket_counts[mode] = (remaining, self.count_map[mode])
                logger.info(f"Map {mode} remaining challenges: {remaining}")
                return
            if attempt < 2:
                self.screenshot()
        logger.warning(f"Map {mode} remaining challenges unreadable; check battle entry instead")

    def check_tickets_enough(self) -> bool:
        if self.climb_type not in ("pass", "ap", "ap100"):
            return super().check_tickets_enough()
        snapshot = self._map_ticket_counts.get(self.climb_type)
        if snapshot is None:
            # 次数无法识别时交给进入战斗的不足提示和点击上限兜底。
            return True
        remaining, count_at_entry = snapshot
        remaining -= self.count_map[self.climb_type] - count_at_entry
        logger.info(f"{self.climb_type} remaining challenges: {max(remaining, 0)}")
        return remaining > 0

    def _enter_pass_challenge(self) -> bool:
        timer = Timer(60).start()
        tickets_checked = False
        pass_selected = False
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_BATTLE_MAIN):
                self._challenge_type = "pass"
                return True
            if self.appear(self.I_UI_BACK_RED) and self.appear(self.I_PASS_4):
                break
            if self.appear(self.I_UI_BACK_RED):
                self.appear_then_click(self.I_UI_BACK_RED, interval=1)
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5):
                continue
            if self._activity_map_matcher().evaluate(self):
                if not tickets_checked:
                    self._capture_map_tickets("pass")
                    tickets_checked = True
                if not pass_selected:
                    pass_selected = self.ocr_appear_click(self.O_ENTER_PASS, interval=1.5)
                    continue
                # 战场攻占选中后仍留在地图，继续选择中央的战斗目标。
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
        timer = Timer(30).start()
        tickets_checked = False
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_BATTLE_MAIN):
                self._challenge_type = "ap"
                return True
            if self.appear(self.I_UI_BACK_RED):
                self.appear_then_click(self.I_UI_BACK_RED, interval=1)
                continue
            if self._activity_map_matcher().evaluate(self):
                if not tickets_checked:
                    self._capture_map_tickets("ap")
                    tickets_checked = True
                self.ocr_appear_click(self.O_ENTER_AP, interval=1)
        logger.warning("Enter ap challenge screen timed out")
        return False

    def _enter_ap100_challenge(self) -> bool:
        timer = Timer(30).start()
        tickets_checked = False
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CLIMB_MODE_AP100):
                self._challenge_type = "ap100"
                return True
            if self.appear(self.I_UI_BACK_RED):
                self.appear_then_click(self.I_UI_BACK_RED, interval=1)
                continue
            if self._activity_map_matcher().evaluate(self):
                if not tickets_checked:
                    self._capture_map_tickets("ap100")
                    tickets_checked = True
                self.ocr_appear_click(self.O_ENTER_AP100, interval=1)
        logger.warning("Enter ap100 challenge screen timed out")
        return False

    def _return_to_activity_map(self) -> bool:
        timer = Timer(30).start()
        map_matcher = self._activity_map_matcher()
        home_matcher = self._activity_home_matcher()
        while not timer.reached():
            self.screenshot()
            # 战报弹窗上仍能识别地图标题，先关弹窗再确认返回成功。
            if self.appear(self.I_UI_BACK_RED):
                self.appear_then_click(self.I_UI_BACK_RED, interval=1.5)
                continue
            if map_matcher.evaluate(self):
                self._challenge_type = None
                return True
            if home_matcher.evaluate(self):
                # 如果已经退到活动主页，重新进地图，避免继续退到庭院。
                self.ocr_appear_click(self.O_ENTER_MAP, interval=1.5)
                continue
            if self.appear_then_click(self.I_UI_BACK_CIRCLE, interval=1.5):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2.5):
                continue
        logger.warning("Return to activity map timed out")
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
