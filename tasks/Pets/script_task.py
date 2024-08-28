# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from module.logger import logger
from module.exception import TaskEnd
from datetime import time, datetime, timedelta
from tasks.Component.GeneralBattle.general_battle import GeneralBattle

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from tasks.Pets.assets import PetsAssets
from tasks.Pets.config import PetsConfig

class ScriptTask(GameUi, PetsAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        con: PetsConfig = self.config.pets.pets_config
        self.orichi_con: GoToOrochiConfig = self.config.pets.go_to_orochi_config
        # 进入
        while 1:
            self.screenshot()
            if self.appear(self.I_PET_FEAST):
                break
            if self.appear_then_click(self.I_PET_HOUSE, interval=1):
                continue
            if self.appear_then_click(self.I_PET_CLAW, interval=1):
                continue
        logger.info('Enter Pets')
        if con.pets_happy:
            self._play()
        if con.pets_feast:
            self._feed()
        self.ui_click(self.I_PET_EXIT, self.I_CHECK_MAIN)
        
        # 如果打开了御魂开关
        if self.orichi_con.go_to_orochi:
            # 御魂切换方式一
            if self.config.pets.switch_soul.enable:
                self.ui_get_current_page()
                self.ui_goto(page_shikigami_records)
                self.run_switch_soul(self.config.pets.switch_soul.switch_group_team)

            # 御魂切换方式二
            if self.config.pets.switch_soul.enable_switch_by_name:
                self.ui_get_current_page()
                self.ui_goto(page_shikigami_records)
                self.run_switch_soul_by_name(self.config.pets.switch_soul.group_name,
                                            self.config.pets.switch_soul.team_name)
            
            self.current_count = 0
            self.limit_count = self.orichi_con.limin_count
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.run_alone()
        
        self.set_next_run(task='Pets', success=True, finish=True)
        raise TaskEnd('Pets')

    def _feed(self):
        """
        投喂
        :return:
        """
        logger.hr('Feed', 3)
        self.ui_click(self.I_PET_FEAST, self.I_PET_FEED)
        number = self.O_PET_FEED_AP.ocr(self.device.image)
        if number == 0:
            # 已经投喂过了
            logger.warning('Already feed')
            return
        self.ui_click(self.I_PET_FEED, self.I_PET_SKIP)
        self.wait_until_disappear(self.I_PET_SKIP)

    def _play(self):
        """
        玩耍
        :return:
        """
        logger.hr('Play', 3)
        self.ui_click(self.I_PET_HAPPY, self.I_PET_PLAY)
        number = self.O_PET_PLAY_GOLD.ocr(self.device.image)
        if number == 0:
            # 金币不足
            logger.warning('Gold not enough')
            return
        # 点击玩耍三次不出现就退出
        play_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_PET_SKIP):
                break
            if play_count >= 3:
                logger.warning('Play count > 3')
                break
            if self.appear_then_click(self.I_PET_PLAY, interval=1):
                play_count += 1
                logger.info(f'Play {play_count}')
                continue
        self.wait_until_disappear(self.I_PET_SKIP)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
