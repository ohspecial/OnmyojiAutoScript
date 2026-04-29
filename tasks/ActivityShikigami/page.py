from tasks.ActivityShikigami.assets import ActivityShikigamiAssets as asa
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets as gba
from tasks.GameUi.assets import GameUiAssets as G
from tasks.GameUi.page import Page, page_battle, page_failed, page_main, page_reward, random_click
from tasks.GlobalGame.assets import GlobalGameAssets as gga

# 活动主界面
page_act = Page(asa.I_TO_BATTLE_MAIN)
page_act.additional = [gga.I_UI_REWARD, asa.I_SKIP_BUTTON]
page_act.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=asa.I_MAIN_GOTO_ACT, destination=page_act)

# 体力爬塔页面
page_act_ap = Page(asa.I_CLIMB_MODE_AP)
page_act_ap.link(button=G.I_BACK_Y, destination=page_act)
page_act.link(button=asa.I_TO_BATTLE_AP, destination=page_act_ap)

# 活动二级页
page_act_2 = Page(asa.I_AS_CHECK_MAIN_2)
page_act_2.additional = [gga.I_UI_BACK_RED]
page_act_2.link(button=gba.I_EXIT, destination=page_act)
page_act.link(button=asa.I_TO_BATTLE_MAIN, destination=page_act_2)

# 暗黑页
page_act_dark = Page(asa.I_AS_CLOSE_EYE)
page_act_dark.additional = [gga.I_UI_BACK_RED, asa.I_AS_LOCATE]
page_act_dark.link(button=gba.I_EXIT, destination=page_act)
page_act_2.link(button=asa.I_AS_OPEN_EYE, destination=page_act_dark)

# 门票页
page_act_pass = Page(asa.I_CLIMB_MODE_PASS)
page_act_pass.link(button=G.I_BACK_Y, destination=page_act_dark)
page_act_dark.link(button=asa.I_AS_TO_PASS, destination=page_act_pass)

# 100体页
page_act_ap100 = Page(asa.I_CLIMB_MODE_AP100)
page_act_ap100.additional = [gga.I_UI_BACK_RED]
page_act_ap100.link(button=G.I_BACK_Y, destination=page_act_dark)
page_act_dark.link(button=asa.O_ENTER_AP100, destination=page_act_ap100)

# boss页
page_act_boss = Page(asa.I_CHECK_BATTLE_BOSS)
page_act_boss.additional = [gga.I_UI_BACK_RED]
page_act_boss.link(button=G.I_BACK_Y, destination=page_act)
page_act.link(button=asa.I_TO_BATTLE_BOSS, destination=page_act_boss)

# 兼容旧引用
page_climb_act = page_act
