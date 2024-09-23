# This Python file uses the following encoding: utf-8
# @brief    Ryou Dokan Toppa (阴阳竂道馆突破功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

import random
import numpy as np
from enum import Enum
from cached_property import cached_property
from time import sleep

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.config_base import ConfigBase, Time
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_kekkai_toppa, page_shikigami_records, page_guild
from tasks.RealmRaid.assets import RealmRaidAssets

from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.utils import point2str
from module.base.timer import Timer
from module.exception import GamePageUnknownError

from tasks.NarrowAbyss.config import NarrowAbyssConfig, NarrowAbyss
from tasks.NarrowAbyss.assets import NarrowAbyssAssets

class AreaType(NarrowAbyssAssets):
    """ 暗域类型 """
    DRAGON = NarrowAbyssAssets.I_NARROW_DRAGON  # 神龙暗域
    PEACOCK = NarrowAbyssAssets.I_NARROW_PEACOCK  # 孔雀暗域
    FOX = NarrowAbyssAssets.I_NARROW_FOX  # 白藏主暗域
    LEOPARD = NarrowAbyssAssets.I_NARROW_LEOPARD # 黑豹暗域

class EmemyType(Enum):

    """ 敌人类型 """
    BOSS = 1  #  首领
    GENERAL = 2  #  副将
    ELITE = 3  #  精英

class CilckArea(NarrowAbyssAssets):
    """ 点击区域 """
    GENERAL_1 = NarrowAbyssAssets.C_GENERAL_1_CLICK_AREA
    GENERAL_2 = NarrowAbyssAssets.C_GENERAL_2_CLICK_AREA
    ELITE_1 = NarrowAbyssAssets.C_ELITE_1_CLICK_AREA
    ELITE_2 = NarrowAbyssAssets.C_ELITE_2_CLICK_AREA
    ELITE_3 = NarrowAbyssAssets.C_ELITE_3_CLICK_AREA
    BOSS= NarrowAbyssAssets.C_BOSS_CLICK_AREA

class ScriptTask(GeneralBattle, GameUi, SwitchSoul, NarrowAbyssAssets):
    
    # team_switched: bool = False
    # green_mark_done: bool = False
    boss_fight_count = 0  # 首领战斗次数
    general_fight_count = 0  # 副将战斗次数
    elite_fight_count = 0  # 精英战斗次数
    
    def run(self):
        """ 狭间暗域主函数

        :return:
        """
        cfg: NarrowAbyss = self.config.narrow_abyss_config

        # if cfg.switch_soul_config.enable:
        #     self.ui_get_current_page()
        #     self.ui_goto(page_shikigami_records)
        #     self.run_switch_soul(cfg.switch_soul_config.switch_group_team)
        # if cfg.switch_soul_config.enable_switch_by_name:
        #     self.ui_get_current_page()
        #     self.ui_goto(page_shikigami_records)
        #     self.run_switch_soul_by_name(cfg.switch_soul_config.group_name, cfg.switch_soul_config.team_name)

        success = True
        # 进入狭间
        self.goto_narrowabbsy()
        # 第一次默认选择神龙暗域
        self.select_boss(AreaType.DRAGON)
        
        # 等待可进攻时间
        self.wait_until_appear(self.I_IS_ATTACK)

        # 准备攻打精英、副将、首领
        while 1:
            # 点击战报按钮
            find_list = [EmemyType.BOSS, EmemyType.GENERAL, EmemyType.ELITE]
            for enemy_type in find_list:
                self.find_enemy(enemy_type)
            logger.info(f"current fight times: boss {self.boss_fight_count} times, 
                                                general {self.general_fight_count}  times, 
                                                elite {self.elite_fight_count} times")
            # 正常应该打完一个区域了，检查攻打次数，如没打够则切换到下一个区域，默认神龙 -> 孔雀 -> 白藏主 -> 黑豹
            if self.boss_fight_count >= 2 and self.general_fight_count >= 4 and self.elite_fight_count >= 6:
                success = True
                break
            else:
                current_area = self.get_current_area()
                if current_area == AreaType.DRAGON:
                    self.change_area(AreaType.PEACOCK)
                elif current_area == AreaType.PEACOCK:
                    self.change_area(AreaType.FOX)
                elif current_area == AreaType.FOX:  
                    self.change_area(AreaType.LEOPARD)
        

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        # self.goto_main()

        # 设置下次运行时间
        if success:
            self.set_next_run(task='NarrowAbyss', finish=True, server=True, success=True)
        else:
            self.set_next_run(task='NarrowAbyss', finish=True, server=True, success=False)
        raise TaskEnd

    def get_current_area(self) -> AreaType:
        ''' 获取当前区域
        :return AreaType
        '''
        self.screenshot()
        if self.appear(self.I_PEACOCK_AREA):
            return AreaType.PEACOCK
        elif self.appear(self.I_DRAGON_AREA):
            return AreaType.DRAGON
        elif self.appear(self.I_FOX_AREA):
            return AreaType.FOX
        elif self.appear(self.I_LEOPARD_AREA):
            return AreaType.LEOPARD
        else:
            raise GamePageUnknownError("Unknown area")

    def change_area(self, area_name: AreaType) -> bool:
        ''' 切换到下个区域
        :return 
        '''
        while 1:
            self.screenshot()
            # 点击战报按钮
            if self.appear_then_click(self.I_CHANGE_AREA,interval=1):
                continue
            self.select_boss(area_name)
            if area_name == AreaType.PEACOCK:
                if self.appear(self.I_PEACOCK_AREA):
                    break
                else:
                    continue
            elif area_name == AreaType.DRAGON:
                if self.appear(self.I_DRAGON_AREA):
                    break
                else:
                    continue
            elif area_name == AreaType.FOX:
                if self.appear(self.I_FOX_AREA):
                    break
                else:
                    continue
            elif area_name == AreaType.LEOPARD:
                if self.appear(self.I_LEOPARD_AREA):
                    break
                else:
                    continue
        return True
    # def goto_main(self):
    #     ''' 保持好习惯，一个任务结束了就返回庭院，方便下一任务的开始或者是出错重启
    #      FIXME 退出道馆。注意：有的时候有退出确认框，有的时候没有。未找到规律。
    #            先试试用确认框的，若是实在不行，就改成等道馆时间结束后，系统自动退出
    #            但是如果出错了，需要重启任务时必须走GameUi.ui_goto(page_main)，
    #            那样有或者无确认框不确定性还是会导致ui_goto()出错
    #     '''
    #     # self.ui_current = page_dokan
    #     # self.ui_goto(page_main)

    #     max_try = 3
    #     while 1:
    #         self.screenshot()
    #         if self.appear_then_click(GeneralBattle.I_EXIT, interval=1.5):
    #             logger.info(f"Click {GeneralBattle.I_EXIT.name}")
    #             continue
    #         # 点了后EXIT后，可能无确认框
    #         if self.appear_then_click(self.I_RYOU_DOKAN_EXIT_ENSURE, interval=1.5):
    #             logger.info(f"Click {self.I_RYOU_DOKAN_EXIT_ENSURE}")
    #             break
    #         else:
    #             max_try -= 1
    #             time.sleep(1.2)

    #         if max_try <= 0:
    #             break

    #     # 退出道馆地图
    #     while 1:
    #         self.screenshot()
    #         # 确认后会跳到竂地图，再点击左上角的蓝色的返回，但是不知道这个返回有没有确认
    #         if self.appear_then_click(GameUi.I_BACK_BL, interval=2.5):
    #             logger.info(f"Click {GameUi.I_BACK_BL.name}")
    #             break

    def goto_narrowabbsy(self) -> bool:
        ''' 进入狭间
        :return bool
        '''
        self.ui_get_current_page()
        logger.info("Entering NarrowAbbsy")
        self.ui_goto(page_guild)
        # # 查找狭间
        # activity = "狭间"
        # pos = self.list_find(self.L_RYOU_ACTIVITY_LIST, activity)
        # if pos:
        #     logger.info(f"Enter NarrowAbbsy map: pos = {pos}")
        #     self.device.click(x=pos[0], y=pos[1])
        #     # 进了后的画面，我没有截图，盲猜应该是在画面正中间的
        #     return True
        # logger.info("NarrowAbbsy not found")
        while 1:
            self.screenshot()
            # 进入神社
            if self.appear_then_click(self.I_RYOU_SHENSHE,interval=1):
                logger.info("Enter Shenshe")
                continue
            # 查找狭间
            if not self.appear(self.I_NARROW_ABYSS, threshold=0.8):
                self.swipe(self.S_TO_NARROWABBSY,interval=3)
                continue
            # 进入狭间
            if self.appear_then_click(self.I_NARROW_ABYSS):
                logger.info("Enter NarrowAbbsy")
                break
        return True
 
    def select_boss(self, area_name: AreaType) -> bool:
        ''' 选择暗域类型
        :return 
        '''
        click_times = 0
        while 1:
            self.screenshot()
            # 点击战报按钮
            if self.appear_then_click(area_name,interval=1):
                click_times += 1
                logger.info(f"click {area_name} times: {click_times}")
                if click_times >= 3:    
                    raise TaskEnd("Failed to select boss")
                continue
            if self.appear(self.I_NARROW_NAVIGATION):
                break
        logger.info(f"select boss: {area_name}")
        
        return True

    def find_enemy(self, enemy_type: EmemyType) -> bool:
        ''' 寻找敌人,并开始寻路进入战斗
        :return 是否找到敌人，若目标已死亡则返回False，否则返回True
        True 找到敌人，并已经战斗完成
        '''
        print(f"find enemy: {enemy_type}")
        while 1:
            self.screenshot()
            # 点击战报按钮logger.info(f"open narrow abyss navigation")
            if self.appear(self.I_NARROW_MAP):
                break
            if self.appear_then_click(self.I_NARROW_NAVIGATION,interval=1):
                continue
 
        match enemy_type:
            case EmemyType.BOSS: success = self.run_boss_fight()
            case EmemyType.GENERAL: success = self.run_general_fight()
            case EmemyType.ELITE: success = self.run_elite_fight()
            
        return success    

    def run_boss_fight(self) -> bool:
        ''' 首领战斗
        只要进入了战斗都返回成功
        :return 
        '''
        click_times = 0
        logger.info(f"run boss fight") 
        while 1:
            self.screenshot()
            if self.appear(self.I_NARROW_MAP):
                self.click_emeny_area(CilckArea.BOSS)
                break
            else:
                click_times += 1
                if click_times >= 3:    
                    return False
                continue
        self.run_general_battle_back()
        self.boss_fight_count += 1
        logger.info(f'Fight, boss_fight_count {self.boss_fight_count} times')
        return True

    def click_emeny_area(self, click_area: CilckArea) -> bool:
        ''' 点击敌人区域
        
        :return 
        '''
        logger.info(f"click emeny area: {click_area}")
        # 点击战报
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_NARROW_NAVIGATION, interval=1.5):
                continue
            if self.appear(self.I_NARROW_MAP):
                break
        logger.info(f"Click {self.I_NARROW_NAVIGATION.name}")

        # 点击攻打区域
        while 1:
            self.screenshot()
            click_times = 0
            if self.click(click_area,interval=1.5):
                click_times += 1
                continue
            if self.appear(self.I_NARROW_GOTO_ENEMY):
                break
            if click_times >= 3:
                logger.warning(f"Failed to click {click_area}")
                return False
        
        # 点击前往按钮
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_NARROW_GOTO_ENEMY,interval=1):
                # 点击敌人后，如果是不同区域会确认框，点击确认                
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                # 跑动画比较花时间
                sleep(3)
                continue
            if self.appear(self.I_NARROW_FIRE):
                break
        logger.info(f"Click {self.I_NARROW_GOTO_ENEMY.name}")
        
        # 点击战斗按钮
        self.wait_until_appear(self.I_NARROW_FIRE)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_NARROW_FIRE,interval=1):
                # 挑战敌人后，如果是奖励次数上限，会出现确认框             
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                continue
            if self.appear(self.I_PREPARE_HIGHLIGHT):
                break
            logger.info(f"Click {self.I_NARROW_FIRE.name}")
        return True
    
        # while 1:
        #     self.screenshot()
        #     if self.is_in_prepare():
        #         break
        #     # 如果出现战报，则点击战报打开地图
        #     if self.appear(self.I_NARROW_NAVIGATION):
        #         self.click(self.I_NARROW_NAVIGATION,interval=5)
        #         continue
        #     # 已经进入战报了则点击boss区域
        #     if self.appear(self.I_NARROW_MAP):
        #         self.click(click_area)
        #         continue
        #     # 点击前往按钮
        #     if self.appear_then_click(self.I_NARROW_GOTO_ENEMY,interval=1):
        #         # TODO 点击敌人后，如果是不同区域会确认框，点击确认                
        #         if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
        #             logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
        #         # 跑动画比较花时间
        #         sleep(3)
        #         continue
        #     # 点击战斗按钮
        #     if self.appear_then_click(self.I_NARROW_FIRE,interval=1):
        #         continue
            

    def run_general_fight(self) -> bool:
        ''' 副将战斗
        :return 
        '''
        general_list = [CilckArea.GENERAL_1, CilckArea.GENERAL_2]
        logger.info(f"run general fight") 
        while 1:
            if len(general_list) != 0:
                print(f"general_list: {general_list}")
                self.click_emeny_area(general_list.pop(0))
                self.general_fight_count += 1
                self.run_general_battle_back()
                logger.info(f'Fight, general_fight_count {self.general_fight_count} times')
                continue
            else:
                break 
        return True


    def run_elite_fight(self) -> bool:
        ''' 精英战斗
        :return 
        '''
        elite_list = [CilckArea.ELITE_1, CilckArea.ELITE_2, CilckArea.ELITE_3]
        logger.info(f"run elite fight")  
               
        while 1:
            if len(elite_list) != 0:
                self.click_emeny_area(elite_list.pop(0))
                self.elite_fight_count += 1
                self.run_general_battle_back()
                logger.info(f'Fight, elite_fight_count {self.elite_fight_count} times')
                continue
            else:
                break 
        return True


    def run_general_battle_back(self) -> bool:
        """
        重写父类方法，因为狭间暗域的准备和战斗流程不一样
        进入挑战然后直接返回
        :param config:
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                continue
            if not self.appear(self.I_PRESET):
                break
        logger.info(f"Click {self.I_PREPARE_HIGHLIGHT.name}")

        # 点击返回
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT, interval=1.5):
                continue
            if self.appear(self.I_EXIT_ENSURE):
                break
        logger.info(f"Click {self.I_EXIT.name}")

        # 点击返回确认,有时不用点击胜利界面
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT_ENSURE, interval=1.5):
                continue
            if self.appear_then_click(self.I_WIN, interval=1.5):
                continue
            if self.appear(self.I_NARROW_NAVIGATION):
                break
        logger.info(f"Click {self.I_EXIT_ENSURE.name}")

        # # 点击胜利确认
        # self.wait_until_appear(self.I_WIN)
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_WIN, interval=1.5):
        #         continue
        #     if not self.appear(self.I_WIN):
        #         break
        # logger.info(f"Click {self.I_WIN.name}")

        return True

def test_goto_main():
    from module.config.config import Config
    from module.device.device import Device
    from tasks.GameUi.page import page_dokan

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    # t.run()
    t.ui_current = page_dokan
    t.ui_goto(page_main)


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('zhu')
    device = Device(config)
    t = ScriptTask(config, device)
    # t.run()
    t.find_enemy(EmemyType.GENERAL)
    # test_ocr_locate_dokan_target()
    # test_anti_detect_random_click()
    # test_goto_main()
