# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger
from module.exception import TaskEnd

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.Orochi.config import Layer, UserStatus
from tasks.Orochi.script_task import ScriptTask as OrochiTask
from tasks.Pets.assets import PetsAssets
from tasks.Pets.config import PetsConfig

class ScriptTask(GameUi, PetsAssets):

    def run(self):
        self.goto_page(page_main)
        con: PetsConfig = self.config.pets.pets_config
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
        # if con.pets_happy:
        #     self._play()
        if con.pets_feast:
            self._feed()
        self.ui_click(self.I_PET_EXIT, self.I_CHECK_MAIN)
        if self.config.pets.go_to_orochi_config.go_to_orochi:
            self._run_orochi_ten_once()

        self.set_next_run(task='Pets', success=True, finish=True)
        raise TaskEnd('Pets')

    def _run_orochi_ten_once(self):
        """
        小猫咪结束后，复用原有御魂任务配置，额外打一把御魂十层。
        仅临时覆盖层数和次数，不落盘修改用户配置。
        """
        logger.hr('Run Orochi ten once after pets', 2)
        orochi_config = self.config.orochi.orochi_config
        old_layer = orochi_config.layer
        old_limit_count = orochi_config.limit_count
        old_user_status = orochi_config.user_status
        old_soul_buff_enable = orochi_config.soul_buff_enable

        try:
            orochi_config.layer = Layer.TEN
            orochi_config.limit_count = 1
            orochi_config.user_status = UserStatus.ALONE
            orochi_config.soul_buff_enable = False
            try:
                OrochiTask(self.config, self.device).run()
            except TaskEnd:
                pass
        finally:
            orochi_config.layer = old_layer
            orochi_config.limit_count = old_limit_count
            orochi_config.user_status = old_user_status
            orochi_config.soul_buff_enable = old_soul_buff_enable

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
