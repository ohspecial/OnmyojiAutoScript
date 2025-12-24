# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import os
import os
import random

from module.atom.animate import RuleAnimate

from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.AutoCake.assets import AutoCakeAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Restart.assets import RestartAssets
from datetime import datetime, timedelta
import time


""" 活动通用 """


class ScriptTask(GameUi, SwitchSoul, GeneralBattle ,AutoCakeAssets, ActivityShikigamiAssets):
    def run(self) -> None:
        self.start_time = datetime.now()
        config = self.config.auto_cake
        # 切换御魂
        if config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_soul_config.switch_group_team)
        if config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                config.switch_soul_config.group_name,
                config.switch_soul_config.team_name
            )

        self.ui_get_current_page()
        self.ui_goto_page(page_main)

        # 进入活动
        self.home_main()

        # 自动战斗
        self.automatic_battle()
        
        # 回到庭院
        # self.ui_get_current_page()
        self.ui_goto_page(page_main, skip_first_screenshot=False)
        if config.auto_cake_config.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

        self.set_next_run(task='AutoCake', success=True, finish=True)
        raise TaskEnd("AutoCake")
        

    def automatic_battle(self):
        config = self.config.auto_cake.auto_cake_config
        
        self.limit_time: timedelta = timedelta(hours=config.limit_time.hour, minutes=config.limit_time.minute,
                                                   seconds=config.limit_time.second)
        
        #  进入活动界面，必须锁定阵容
        if self.appear(self.I_IS_REACH2):
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear(self.I_LOCK):
                    break
        # 开启樱饼
        avtivity_ap =  self.O_REMAIN_ACTIVITY_AP.ocr_digit(self.device.image)
        if avtivity_ap > 0:
            logger.info(f"avtivity_ap : {avtivity_ap}")
            self.appear_then_click(self.I_IS_CLOSE, interval=1)
            logger.info('click cake area')
            # self.click(self.C_CAKE_AREA,interval=1)
            self.device.stuck_record_add('BATTLE_STATUS_S')
        
        # 任务开启
        swipe_timer = Timer(270)
        swipe_timer.start()
        freeze_timer = Timer(5)
        screen_freeze = RuleAnimate(self.I_REWARD, threshold=0.8)
        while 1:
            self.screenshot()
            
            # 画面静止检测
            if self.appear(self.I_REWARD):
                freeze_timer.start()
                if screen_freeze.stable(self.device.image):
                    if freeze_timer.reached():
                        logger.warning("Screen frozen for 5 seconds, exiting automatic_battle")
                        self.click(random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3]), interval=1)
                        break
                else:
                    freeze_timer.reset()
            else:
                freeze_timer.reset()

            # 时间结束判断
            if datetime.now() - self.start_time >= self.limit_time:
                # 任务执行时间超过限制时间，退出
                logger.info('Auto cake task is over time')
                break
            # # 点击准备 适配不同副本的需要
            # if self.appear(self.I_PREPARE_HIGHLIGHT, interval=5):
            #     self.device.click_record_clear()
            #     self.click(self.I_PREPARE_HIGHLIGHT)
            #     logger.info("click prepare button")
            # 攻打次数上限判断
            if self.appear(self.I_IS_OVER):
                logger.info('Auto cake task is over count')
                break
            # 定时重置状态
            if swipe_timer.reached():
                swipe_timer.reset()
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
        
        
    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面，统一入口
        :return:
        """
        logger.hr("Enter Shikigami", 2)
        while 1:
            self.screenshot()
            self.C_RANDOM_LEFT.name = "BATTLE_RANDOM"
            self.C_RANDOM_RIGHT.name = "BATTLE_RANDOM"
            self.C_RANDOM_TOP.name = "BATTLE_RANDOM"
            self.C_RANDOM_BOTTOM.name = "BATTLE_RANDOM"
            if self.appear(self.I_IS_REACH):
                break
            if self.appear_then_click(self.I_SHI, interval=1):
                continue
            if self.appear_then_click(self.I_TOGGLE_BUTTON, interval=3):
                continue
            if self.appear_then_click(self.I_SKIP_BUTTON, interval=1.5):
                continue
            # 如果出现了 “获得奖励”
            reward_click = random.choice([self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM])
            if self.appear_then_click(self.I_UI_REWARD, action=reward_click, interval=1.3):
                continue
            if self.appear_then_click(self.I_RED_EXIT, interval=1.5):
                continue
            
        # 进入活动副本
        while 1:
            self.screenshot()
            if self.appear(self.I_IS_REACH2):
                break
            if self.appear_then_click(self.I_STEP_2, interval=2):
                continue

    


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('zhu')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()