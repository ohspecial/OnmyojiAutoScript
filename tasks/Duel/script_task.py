# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

import cv2
import numpy as np
from module.atom.ocr import RuleOcr

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_duel
from tasks.Duel.config import Duel, Onmyoji
from tasks.Duel.assets import DuelAssets
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
import os
from module.atom.image import RuleImage
from tasks.GameUi.page import page_main, page_team, page_shikigami_records



class ScriptTask(GameUi, GeneralBattle, SwitchSoul, DuelAssets):
    battle_count = 0
    battle_win_count = 0
    battle_lose_count = 0
    current_score = 0
    battle_win_copy=battle_win_count
    battle_lose_copy=battle_lose_count
    def run(self):

        current_time = datetime.now().time()
        if not (time(12, 00) <= current_time < time(23, 00)):
            self.set_next_run(task='Duel', success=True, finish=False)
            raise TaskEnd('Duel')

        con = self.config.duel
        # 切换御魂
        if con.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul.switch_group_team)

        if con.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul.group_name,con.switch_soul.team_name)

        con = self.config.duel.duel_config
        celeb_con = self.config.duel.duel_celeb_config
        self.current_score = celeb_con.initial_score
        limit_time = con.limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)

        self.ui_get_current_page()
        self.ui_goto(page_main)
        # 切换阴阳师
        if con.switch_enabled:
            # 清明
            if con.switch_onmyoji == Onmyoji.Qm:
                self.switch_kagura(con, self.C_QM_ZHAN, self.I_QM_ZHAN)
            # 神乐
            elif con.switch_onmyoji == Onmyoji.Sl:
                self.switch_kagura(con, self.C_SL_ZHAN, self.I_SL_ZHAN)
            # 源博雅
            elif con.switch_onmyoji == Onmyoji.Yby:
                self.switch_kagura(con, self.C_YBY_ZHAN, self.I_YBY_ZHAN)
            # 八百比丘尼
            elif con.switch_onmyoji == Onmyoji.Bbbqn:
                self.switch_kagura(con, self.C_BBBQN_ZHAN, self.I_BBBQN_ZHAN)
            # 源赖光
            elif con.switch_onmyoji == Onmyoji.Ylg:
                self.switch_yorimitsu()
                
        self.ui_get_current_page()
        self.ui_goto(page_duel)
        # 切换御魂
        if con.switch_all_soul:
            self.switch_all_soul()

        # 循环
        duel_week_over = False
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_REWARD, interval=0.6):
                continue
            if not self.duel_main():
                continue
            # 检查分数
            current_score = self.check_score()

            # if current_score == 3000 and self.check_honor():
            #     # 3000分和满荣誉退出，退出
            #     logger.info('Duel task is over score')
            #     duel_week_over = True
            #     break

            if datetime.now() - self.start_time >= self.limit_time:
                # 任务执行时间超过限制时间，退出
                logger.info('Duel task is over time')
                break

            # 不开启名仕战斗,到达名士直接退出
            if not celeb_con.celeb_battle:
                if self.appear(self.I_D_CELEB_STAR) or self.appear(self.I_D_CELEB_HONOR):
                    logger.info('You are already a celeb（名仕）')
                    current_score = "名仕"
                    duel_week_over = True
                    break
            # 练习
            if self.appear(self.I_BATTLE_WITH_TRAIN) or self.appear(self.I_BATTLE_WITH_TRAIN2):
                break

            if con.honor_full_exit and self.check_honor():
                # 荣誉满了，退出
                logger.info('Duel task is over honor')
                break

            # 当前分数跟目标分数比较
            if current_score >= con.target_score:
                # 分数够了
                logger.info('Duel task is over score')
                break

            # 进行一次斗技
            self.duel_one(current_score, con.green_enable, con.green_mark, celeb_con.ban_name)

        logger.info('Duel battle end')
        # 记得退回去到町中
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_TOWN)

        if duel_week_over:
            self.set_next_run(task='Duel', success=True, finish=True)
        else:
            self.set_next_run(task='Duel', success=True, finish=False)

        # 调起花合战
        self.set_next_run(task='TalismanPass', target=datetime.now())
        raise TaskEnd('Duel')

    def duel_main(self, screenshot=False) -> bool:
        """
        判断是否斗技主界面
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_D_HELP) or self.appear(self.I_D_CELEB_STAR) or self.appear(self.I_D_CELEB_HONOR)

    def switch_all_soul(self):
        """
        一键切换所有御魂
        :return:
        """
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break

            if self.appear_then_click(self.I_D_TEAM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.6):
                continue
            if self.appear_then_click(self.I_D_TEAM_SWTICH, interval=1):
                click_count += 1
                continue
        logger.info('Souls Switch is complete')
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_D_TEAM)

    def switch_kagura(self,con, target1, target2):
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break
            if self.appear(self.I_YINYANGSHUOK, interval=1):
                break
            if self.appear_then_click(self.I_YINYANGSHU, interval=1):
                click_count += 1
                continue
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break
            if self.appear(self.I_YYSJIOAHUAN, interval=1):
                break
            if self.appear_then_click(self.I_JIAOTI, interval=1):
                continue
            if self.appear_then_click(self.I_YINGJIE, interval=1):
                click_count += 1
                continue
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break
            if self.appear(target2, interval=1):
                break
            if self.appear_then_click(self.I_JIAOTI, interval=1):
                continue
            if self.click(target1, interval=1):
                click_count += 1
                continue
        logger.info(f'切换阴阳师{con.switch_onmyoji}')
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def switch_yorimitsu(self):
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break
            if self.appear(self.I_YINYANGSHUOK, interval=1):
                break
            if self.appear_then_click(self.I_YINYANGSHU, interval=1):
                click_count += 1
                continue
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 4:
                break
            if self.appear(self.I_YINGJIE, interval=1):
                break
            if self.appear_then_click(self.I_YINYANGSHI, interval=1):
                click_count += 1
                continue
        logger.info('切换英杰源赖光')
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def check_honor(self) -> bool:
        """
        检查荣誉是否满了
        :return:
        """
        current, remain, total = self.O_D_HONOR.ocr(self.device.image)
        if current == total and remain == 0:
            return True
        return False

    def check_score(self) -> int or None:
        """
        检查是否达到目标分数
        :param target: 目标分数
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_D_CELEB_STAR) or self.appear(self.I_D_CELEB_HONOR):
                if self.battle_win_count - self.battle_win_copy == 1:
                    self.battle_win_copy = self.battle_win_count
                    self.current_score += 100
                elif self.battle_lose_count - self.battle_lose_copy == 1:
                    self.battle_lose_copy = self.battle_lose_count
                    self.current_score -= 100
                else:
                    self.current_score = self.current_score
            else:
                self.current_score = self.O_D_SCORE.ocr(self.device.image)
                if self.current_score > 10000:
                    # 识别错误分数超过一万, 去掉最高位
                    logger.warning('Recognition error, score is too high')
                    self.current_score = int(str(self.current_score)[1:])
            logger.info(f'battle score: {self.current_score}')
            return self.current_score

    def duel_one(self, current_score: int, enable: bool = False,
                 mark_mode: GreenMarkType = GreenMarkType.GREEN_MAIN, ban_name: str = '') -> bool:
        """
        进行一次斗技， 返回输赢结果
        :param mark_mode:
        :param enable:
        :param current_score: 当前分数, 不同的分数有不同的战斗界面
        :return:
        """
        logger.hr('Duel battle', 2)
        self.battle_count += 1
        # 是否名士
        celeb_status = False
        while 1:
            self.screenshot()
            if self.appear(self.I_D_VICTORY):
                self.ui_click_until_disappear(self.I_D_VICTORY)
                self.battle_win_copy = self.battle_win_count
                self.battle_win_count += 1
                return
            if self.appear(self.I_D_AUTO_ENTRY) or self.appear(self.I_D_PREPARE):
                break
            # 名士以上禁用
            if self.appear_then_click(self.I_BAN, interval=1):
                celeb_status = True
                continue
            # 战斗按钮
            if self.appear_then_click(self.I_D_BATTLE, interval=1) or self.appear_then_click(self.I_D_BATTLE2, interval=1):
                continue
            # 战斗带保护的按钮
            if self.appear_then_click(self.I_D_BATTLE_PROTECT, interval=1.6):
                continue
            # 斗技模式（普通）
            # if self.appear_then_click(self.I_BATTLE_TYPE_COMMON, interval=1):
            #     continue
            # 练习
            # if self.appear_then_click(self.I_BATTLE_WITH_TRAIN, interval=1) or self.appear_then_click(self.I_BATTLE_WITH_TRAIN2, interval=1):
            #     continue

        # 点击斗技 开始匹配对手
        logger.hr('Duel start match')
        while 1:
            self.screenshot()
            # 出现自动上阵
            if self.appear(self.I_D_AUTO_ENTRY):
                ban_check_success = True
                if celeb_status:
                    # 检查禁选式神
                    name_timer = Timer(5)
                    name_timer.start()
                    ban_check_success = False
                    while 1:
                        if name_timer.reached():
                            break
                        self.click(self.C_DUEL_CLICK_5)
                        sleep(0.5)
                        self.screenshot()
                        # 如果对方直接秒退，那自己就是赢的
                        if self.appear(self.I_D_VICTORY):
                            self.ui_click_until_disappear(self.I_D_VICTORY)
                            self.battle_win_copy = self.battle_win_count
                            self.battle_win_count += 1
                            return
                        ocr_ban_name = self.O_D_BAN_NAME.ocr(self.device.image)
                        if ocr_ban_name == '':
                            continue
                        if any(char in ocr_ban_name for char in ban_name):
                            ban_check_success = True
                            break
                        else:
                            break

                # 处理检查结果
                if not ban_check_success:
                    self.duel_exit_battle()
                    if self.appear(self.I_D_FAIL):
                        # 输了
                        self.ui_click_until_disappear(self.I_D_FAIL)
                        self.battle_lose_copy = self.battle_lose_count
                        self.battle_lose_count += 1
                    return

                # 等待自动上阵消失
                self.ui_click_until_disappear(self.I_D_AUTO_ENTRY)
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                self.wait_until_disappear(self.I_D_WORD_BATTLE)
                break
            if self.appear(self.I_D_PREPARE):
                # 低段位有的准备
                self.ui_click_until_disappear(self.I_D_PREPARE)
                self.wait_until_disappear(self.I_D_PREPARE_DONE)
                logger.info('Duel prepare')
                break
            # 如果对方直接秒退，那自己就是赢的
            if self.appear(self.I_D_VICTORY):
                self.ui_click_until_disappear(self.I_D_VICTORY)
                self.battle_win_copy = self.battle_win_count
                self.battle_win_count += 1
                return
        timer = Timer(10)
        timer.start()
        while 1:
            if timer.reached():
                break
            if self.is_in_battle():
                break
        while 1:
            self.screenshot()
            if self.ocr_appear(self.O_D_AUTO, interval=0.4):
                break
            if self.ocr_appear_click(self.O_D_HAND, interval=1):
                continue
            # 如果对方直接秒退，那自己就是赢的
            if self.appear(self.I_D_VICTORY):
                self.ui_click_until_disappear(self.I_D_VICTORY)
                self.battle_win_copy = self.battle_win_count
                self.battle_win_count += 1
                return
            if self.appear(self.I_D_FAIL):
                # 输了
                self.ui_click_until_disappear(self.I_D_FAIL)
                self.battle_lose_copy = self.battle_lose_count
                self.battle_lose_count += 1
                return
        # 绿标  先模板匹配找绿标名字，找不到则点击位置
        if enable:
            # 点击绿标，现在能标上绿标，但是不一定能识别到，所以不点击位置了，会导致报错重启
            self.duel_green_mark_by_template(mark_mode)
            
        # 等待结果
        logger.info('Duel wait result')
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        battle_win = True
        swipe_count = 0
        swipe_timer = Timer(270)
        swipe_timer.start()
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_D_BATTLE_DATA, action=self.C_D_BATTLE_DATA, interval=0.6):
                continue
            if self.appear(self.I_FALSE):
                # 打输了
                self.ui_click_until_disappear(self.I_FALSE)
                battle_win = False
                break
            if self.appear(self.I_D_FAIL):
                # 输了
                self.ui_click_until_disappear(self.I_D_FAIL)
                battle_win = False
                break
            if self.appear(self.I_WIN):
                # 打赢了
                self.ui_click_until_disappear(self.I_WIN)
                battle_win = True
                break
            if self.appear(self.I_D_VICTORY):
                # 打赢了
                self.ui_click_until_disappear(self.I_D_VICTORY)
                battle_win = True
                break

            if swipe_timer.reached():
                swipe_timer.reset()
                if swipe_count >= 2:
                    # 记三次，十五分钟没有结束也没谁了
                    logger.info('Duel battle timeout')
                    battle_win = False
                    break
                swipe_count += 1
                logger.warning('Duel battle stuck, swipe')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')

        if battle_win:
            self.battle_win_copy = self.battle_win_count
            self.battle_win_count += 1
        else:
            self.battle_lose_copy = self.battle_lose_count
            self.battle_lose_count += 1

        task_run_time = datetime.now() - self.start_time
        # 格式化时间，只保留整数部分的秒
        task_run_time_seconds = timedelta(seconds=int(task_run_time.total_seconds()))

        logger.info(f'battle result: {battle_win}')
        logger.info(f'battle count: {self.battle_count} | win: {self.battle_win_count} failure: {self.battle_lose_count}')
        logger.info(f'battle time: {task_run_time_seconds} / {self.limit_time}')
        return battle_win

    def duel_exit_battle(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_D_FAIL) or self.appear(self.I_FALSE):
                return
            if self.appear_then_click(self.I_EXIT_ENSURE):
                continue
            if self.appear_then_click(self.I_DUEL_EXIT, interval=1):
                continue
    
    def duel_green_mark_by_template(self, mark_mode: GreenMarkType = GreenMarkType.GREEN_MAIN) -> bool:
        match mark_mode:
            case GreenMarkType.GREEN_LEFT1:
                target = self.I_GREEN_MARK_IMG1
                logger.info("Green left 1")
            case GreenMarkType.GREEN_LEFT2:
                target = self.I_GREEN_MARK_IMG2
                logger.info("Green left 2")
            case GreenMarkType.GREEN_LEFT3:
                target = self.I_GREEN_MARK_IMG3
                logger.info("Green left 3")
            case GreenMarkType.GREEN_LEFT4:
                target = self.I_GREEN_MARK_IMG4
                logger.info("Green left 4")
            case GreenMarkType.GREEN_LEFT5:
                target = self.I_GREEN_MARK_IMG5
                logger.info("Green left 5")
            case GreenMarkType.GREEN_MAIN:
                return

        logger.info('------进行图片匹配识别绿标位置------')
        # 点击绿标
        mark_timer = Timer(5)
        mark_timer.start()
        while 1:
            if mark_timer.reached():
                logger.info('Duel green mark timeout, dont appear I_GREEN_MARK_IMG')
                return False
            self.screenshot()
            if self.appear(target, interval=0.5):
                new_roi_front = (target.roi_front[0],
                                 target.roi_front[1] + 60,
                                 10,
                                 100)
                self.C_DUEL_GREEN_LEFT_FULL.roi_front = new_roi_front
                logger.info(f'old Image roi {target.roi_front}')
                logger.info(f'new Image roi {self.C_DUEL_GREEN_LEFT_FULL.roi_front}')
                break
        # 点击绿标
        mark_timer = Timer(5)
        mark_timer.start()
        while 1:
            if mark_timer.reached():
                logger.info('Duel green mark timeout')
                return False
            self.screenshot()
            if self.I_GREEN_MARK.match(self.device.image):
                logger.info("识别到绿标,返回")
                return True
            
            self.click(self.C_DUEL_GREEN_LEFT_FULL, interval=4)

    def duel_green_mark_by_region(self, mark_mode: GreenMarkType = GreenMarkType.GREEN_MAIN):
        """
        绿标， 如果不使能就直接返回
        :param enable:
        :param mark_mode:
        :return:
        """
        logger.info('------进行区域点击识别绿标位置------')
        if self.wait_until_appear(self.I_GREEN_MARK, wait_time=1):
            # logger.info("识别到绿标，返回")
            return
        # logger.info("Green is enable")
        x, y = None, None
        match mark_mode:
            case GreenMarkType.GREEN_LEFT1:
                x, y = self.C_DUEL_GREEN_LEFT_1.coord()
                logger.info("Green left 1")
            case GreenMarkType.GREEN_LEFT2:
                x, y = self.C_GREEN_LEFT_2.coord()
                logger.info("Green left 2")
            case GreenMarkType.GREEN_LEFT3:
                x, y = self.C_GREEN_LEFT_3.coord()
                logger.info("Green left 3")
            case GreenMarkType.GREEN_LEFT4:
                x, y = self.C_GREEN_LEFT_4.coord()
                logger.info("Green left 4")
            case GreenMarkType.GREEN_LEFT5:
                x, y = self.C_DUEL_GREEN_LEFT_5.coord()
                logger.info("Green left 5")
            case GreenMarkType.GREEN_MAIN:
                x, y = self.C_GREEN_MAIN.coord()
                logger.info("Green main")

        # 等待那个准备的消失
        while 1:
            self.screenshot()
            if not self.appear(self.I_PREPARE_HIGHLIGHT):
                break

        # 点击绿标 ，增加斗技点击次数
        mark_timer = Timer(5)
        mark_timer.start()
        while 1:
            self.screenshot()
            if self.I_GREEN_MARK.match(self.device.image):
                logger.info("匹配识别到绿标,返回")
                break
            if mark_timer.reached():
                # logger.warning("识别绿标超时,返回")
                break
            # 点击绿标
            self.device.click(x, y)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('zhu')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
