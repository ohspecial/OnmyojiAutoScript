# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import os
import random

from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Restart.assets import RestartAssets
from datetime import datetime, timedelta
import time

""" 活动通用 """


class ScriptTask(GameUi, SwitchSoul, GeneralBattle):
    SoulsFUll = False
    def run(self) -> None:

        config = self.config.activity_common
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
        self.goto_activity()

        # 回到庭院
        self.ui_get_current_page()
        self.ui_goto(page_main)

        if config.activity_common_config.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

        if self.SoulsFUll:
            self.push_notify_and_log("御魂溢出，结束任务,重新执行任务")
            self.set_next_run(task='ActivityCommon', success=False, finish=False, target=datetime.now())
        else:
            self.set_next_run(task='ActivityCommon', success=True, finish=True)
        raise TaskEnd

    def goto_activity(self):
        config = self.config.activity_common.activity_common_config
        limit_time = config.limit_time
        enable = config.enable
        if enable:
            self.limit_count = config.limit_count
            self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                                   seconds=limit_time.second)
        # 动态加载所有图片
        image_templates = self._load_image_template()

        click_count = 0
        click_count_max = 5
        last_clicked_file = None  # 记录上一次点击的文件名
        over_task = False
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

    def push_notify_and_log(self, content):
        logger.info(f"{content}")
        self.push_notify(content=f"{content}")

    def _load_image_template(self):
        image_templates = []
        image_folder = "./tasks/ActivityCommon/auto/"
        supported_formats = ('.png', '.jpg', '.jpeg')

        # 遍历图片文件夹
        for filename in os.listdir(image_folder):
            if not filename.lower().endswith(supported_formats):
                continue
            # 构建完整路径
            file_path = os.path.join(image_folder, filename)

            # 创建RuleImage对象并添加到列表
            image_rule = RuleImage(
                roi_front=(0, 0, 1280, 720),  # 保持与原来相同的ROI参数
                roi_back=(0, 0, 1280, 720),
                threshold=0.8,
                method="Template matching",
                file=file_path
            )
            image_templates.append(image_rule)

        logger.info(f"加载图片模板集合: {image_templates}")
        logger.info(f"加载图片模板数量: {len(image_templates)}")
        return image_templates


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('mi')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
