# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import os
import random

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


class ScriptTask(GameUi, SwitchSoul, GeneralBattle , ActivityShikigamiAssets ,AutoCakeAssets):
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
        self.ui_goto(page_main)

        # 进入活动
        self.home_main()

        # 自动战斗
        self.automatic_battle()
        
        # 回到庭院
        self.ui_get_current_page()
        self.ui_goto(page_main)

        if config.auto_cake_config.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

        self.set_next_run(task='AutoCake', success=True, finish=True)
        raise TaskEnd("AutoCake")
        
        self.ui_get_current_page()
        while 1:
            self.screenshot()
            # 获得奖励
            if self.ui_reward_appear_click():
                continue
            # 误点聊天频道会自动关闭
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                continue
            for image_template in image_templates:
                current_file = os.path.basename(image_template.file)

                if current_file == '挑战.png':
                    if self.appear(image_template):
                        if over_task:
                            return
                        if enable:
                            if datetime.now() - self.start_time >= self.limit_time:
                                self.push_notify_and_log("时间限制已到，结束任务")
                                return
                            if self.current_count >= self.limit_count:
                                self.push_notify_and_log("次数限制已到，结束任务")
                                return

                if self.appear_then_click(image_template, interval=1):
                    if current_file == '御魂溢出确认.png':
                        self.push_notify_and_log("御魂溢出，结束任务")
                        over_task = True
                        self.SoulsFUll = True
                        self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

                    if current_file == '赢（鼓）.png' and current_file != last_clicked_file:
                        flag = False
                        while 1:
                            if flag:
                                break
                            action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                            self.click(action_click)
                            time.sleep(1)
                            for image_template_new in image_templates:
                                current_file_new = os.path.basename(image_template_new.file)
                                if current_file_new == '挑战.png':
                                    self.screenshot()
                                    if self.appear(image_template_new):
                                        flag = True
                                        break

                        self.current_count += 1
                        logger.info(f"Current count: {self.current_count} / {self.limit_count}")
                        task_run_time = datetime.now() - self.start_time
                        task_run_time_seconds = timedelta(seconds=int(task_run_time.total_seconds()))
                        logger.info(f"Current times: {task_run_time_seconds} / {self.limit_time}")
                        logger.hr("General battle end", 2)

                    # 判断是否连续点击同一图片
                    if current_file == last_clicked_file:
                        click_count += 1
                        if click_count >= click_count_max:
                            self.push_notify_and_log("点击同一图片最大次数，结束任务")
                            over_task = True
                    else:
                        click_count = 0  # 点击不同图片时重置计数

                    last_clicked_file = current_file  # 更新记录
                    if current_file == '挑战.png' or current_file == '准备.png':
                        self.device.stuck_record_add('BATTLE_STATUS_S')
                    break

    def automatic_battle(self):
        config = self.config.auto_cake.auto_cake_config
        
        self.limit_time: timedelta = timedelta(hours=config.limit_time.hour, minutes=config.limit_time.minute,
                                                   seconds=config.limit_time.second)
        
        #  进入活动界面，必须锁定阵容
        if self.appear(self.I_IS_REACH):
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear(self.I_LOCK):
                    break
        
        # 开启樱饼
        if self.appear_then_click(self.I_IS_CLOSE, interval=1):    
                logger.info('click cake area')
                self.click(self.C_CAKE_AREA,interval=1)
                self.device.stuck_record_add('BATTLE_STATUS_S')
        
        # 任务开启
        swipe_timer = Timer(270)
        swipe_timer.start()
        while 1:
            self.screenshot()
            # 时间结束判断
            if datetime.now() - self.start_time >= self.limit_time:
                # 任务执行时间超过限制时间，退出
                logger.info('Auto cake task is over time')
                break
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
            if self.appear_then_click(self.I_STEP_2, interval=2):
                continue

    


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('zhu')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
