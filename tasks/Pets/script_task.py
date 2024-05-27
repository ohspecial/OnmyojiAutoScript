# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger
from module.exception import TaskEnd
from datetime import time, datetime, timedelta

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from tasks.Pets.assets import PetsAssets
from tasks.Pets.config import PetsConfig,GoToOrochiConfig

class ScriptTask(GameUi, PetsAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        con: PetsConfig = self.config.pets.pets_config
        orichi_con: GoToOrochiConfig = self.config.go_to_orochi_config
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
        if orichi_con.go_to_orochi:
            # 御魂切换方式一
            if self.config.orochi.switch_soul.enable:
                self.ui_get_current_page()
                self.ui_goto(page_shikigami_records)
                self.run_switch_soul(self.config.orochi.switch_soul.switch_group_team)

            # 御魂切换方式二
            if self.config.orochi.switch_soul.enable_switch_by_name:
                self.ui_get_current_page()
                self.ui_goto(page_shikigami_records)
                self.run_switch_soul_by_name(self.config.orochi.switch_soul.group_name,
                                            self.config.orochi.switch_soul.team_name)
            
            self.current_count = 0
            self.limit_count = orichi_con.limin_count
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.run_alone()
        
        self.set_next_run(task='Pets', success=True, finish=True)
        raise TaskEnd('Pets')

    def orochi_enter(self) -> bool:
        logger.info('Enter orochi')
        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return True
            if self.appear_then_click(self.I_OROCHI, interval=1):
                continue

    def check_lock(self, lock: bool = True) -> bool:
        """
        检查是否锁定阵容, 要求在八岐大蛇界面
        :param lock:
        :return:
        """
        logger.info('Check lock: %s', lock)
        if lock:
            while 1:
                self.screenshot()
                if self.appear(self.I_OROCHI_LOCK):
                    return True
                if self.appear_then_click(self.I_OROCHI_UNLOCK, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_OROCHI_UNLOCK):
                    return True
                if self.appear_then_click(self.I_OROCHI_LOCK, interval=1):
                    continue

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True

    def run_alone(self):
        logger.info('Start run alone')
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        self.orochi_enter()
        layer = self.config.orochi.orochi_config.layer
        self.check_layer(layer)
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)

        def is_in_orochi(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_OROCHI_FIRE)

        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if not is_in_orochi():
                continue

            if self.current_count >= 1:
                logger.info('Orochi count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Orochi time limit out')
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_OROCHI_FIRE, interval=1):
                    pass

                if not self.appear(self.I_OROCHI_FIRE):
                    self.run_general_battle(config=self.config.orochi.general_battle_config)
                    break

        # 回去
        while 1:
            self.screenshot()
            if not self.appear(self.I_FORM_TEAM):
                break
            if self.appear_then_click(self.I_BACK_BL, interval=1):
                continue

        self.ui_current = page_soul_zones
        self.ui_goto(page_main)

    
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
