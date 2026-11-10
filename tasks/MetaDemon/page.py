"""超鬼王活动导航，复用本地页面注册和任务 session。"""
import time

from module.exception import GamePageUnknownError
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.page import (
    Page, any_of, page_act_list, page_battle, page_battle_result, page_main,
    page_reward, page_shikigami_records, random_click,
)
from tasks.GameUi.assets import GameUiAssets
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.navigation_assets import MetaDemonNavigationAssets as Nav


def find_activity_entry(task):
    # 庭院侧栏会轮换活动栏目，等公共入口出现后再交给导航器点击。
    for _ in range(8):
        task.screenshot()
        if not task.appear(GameUiAssets.I_CHECK_MAIN):
            return False
        if task.appear(Nav.I_MAIN_GOTO_ACTIVITY):
            return True
        task.appear_then_click(RightActivityAssets.I_TOGGLE_BUTTON, interval=0.5)
        time.sleep(0.5)
    raise GamePageUnknownError('未找到超鬼王活动入口')


def handle_activity_overlays(task):
    # 昨日奖励可能覆盖入口；先清理覆盖层，再识别活动主界面。
    rules = (MetaDemonAssets.I_MD_GET_YESTERDAY_REWARD,
             Nav.I_ACTIVITY_SKIP_ENSURE, Nav.I_ACTIVITY_SKIP,
             MetaDemonAssets.I_MD_CLOSE_POPUP, Nav.I_ACTIVITY_GENERAL_CLOSE_RED)
    clicked = False
    for _ in range(6):
        task.screenshot()
        target = next((rule for rule in rules if task.appear(rule)), None)
        if target is None:
            return clicked
        if task.appear_then_click(target, interval=0.6):
            clicked = True
        time.sleep(0.3)
    return clicked


def enter_meta_demon_boss(task):
    return (task.appear_then_click(Nav.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE, interval=0.8)
            or task.appear_then_click(Nav.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE_BACKUP, interval=0.8))


# 其他活动仍有独立页面，入口在超鬼王分类内注册，避免抢占它们的识别。
page_activity = Page(any_of(Nav.I_PAGE_CHECK_ACTIVITY,
                            Nav.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE,
                            Nav.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE_BACKUP),
                     key='page_meta_demon_activity', category='meta_demon')
page_activity.add_enter_success_hooks(handle_activity_overlays)
page_activity.add_enter_failure_hooks(find_activity_entry, handle_activity_overlays)
page_activity.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW,
                      key='page_meta_demon_activity->page_main')
page_main.connect(page_activity, Nav.I_MAIN_GOTO_ACTIVITY,
                  key='page_main->page_meta_demon_activity')

page_act_list_meta_demon = Page(Nav.I_PAGE_METADEMON_CHECK_ACT_LIST_METADEMON_ACT)
page_act_list_meta_demon.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW)
page_act_list_meta_demon.connect(page_activity, GameUiAssets.I_ACT_LIST_GOTO_ACT)
page_meta_demon = page_activity

page_meta_demon_boss = Page(Nav.I_PAGE_METADEMON_CHECK_BOSS_PAGE,
                           key='page_meta_demon_boss', category='meta_demon')
page_meta_demon_boss.add_enter_success_hooks(MetaDemonAssets.I_MD_CLOSE_POPUP)
page_meta_demon_boss.connect(page_activity, GlobalGameAssets.I_UI_BACK_YELLOW,
                            key='page_meta_demon_boss->page_meta_demon_activity')
page_activity.connect(page_meta_demon_boss, enter_meta_demon_boss,
                      key='page_meta_demon_activity->page_meta_demon_boss')
page_reward.connect(page_meta_demon_boss, random_click(), key='page_reward->page_meta_demon_boss')
page_battle_result.connect(page_meta_demon_boss, random_click(), key='page_battle_result->page_meta_demon_boss')
reward_random_click = random_click
