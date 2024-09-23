from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class NarrowAbyssAssets: 


	# Click Rule Assets
	# 首领 
	C_BOSS_CLICK_AREA = RuleClick(roi_front=(679,164,83,54), roi_back=(679,164,83,54), name="boss_click_area")
	# 副将1 
	C_GENERAL_1_CLICK_AREA = RuleClick(roi_front=(539,306,64,56), roi_back=(539,306,64,56), name="general_1_click_area")
	# 副将2 
	C_GENERAL_2_CLICK_AREA = RuleClick(roi_front=(856,293,58,50), roi_back=(856,293,58,50), name="general_2_click_area")
	# 精英1 
	C_ELITE_1_CLICK_AREA = RuleClick(roi_front=(453,418,54,45), roi_back=(453,418,54,45), name="elite_1_click_area")
	# 精英2 
	C_ELITE_2_CLICK_AREA = RuleClick(roi_front=(694,420,58,44), roi_back=(694,420,58,44), name="elite_2_click_area")
	# 精英3 
	C_ELITE_3_CLICK_AREA = RuleClick(roi_front=(938,413,60,44), roi_back=(938,413,60,44), name="elite_3_click_area")
	# 前往阵眼 
	C_CHANGE_ZONE = RuleClick(roi_front=(1000,606,54,54), roi_back=(1000,606,54,54), name="change_zone")
	# 神龙暗域 
	C_DRAGON_AREA = RuleClick(roi_front=(123,150,75,66), roi_back=(123,150,75,66), name="dragon_area")
	# 孔雀暗域 
	C_PEACOCK_AREA = RuleClick(roi_front=(125,278,74,62), roi_back=(125,278,74,62), name="peacock_area")
	# 白藏主暗域 
	C_FOX_AREA = RuleClick(roi_front=(126,409,79,74), roi_back=(126,409,79,74), name="fox_area")
	# 黑豹暗域 
	C_LEOPARD_AREA = RuleClick(roi_front=(122,537,81,76), roi_back=(122,537,81,76), name="leopard_area")


	# Image Rule Assets
	# 阴阳竂->神社 
	I_RYOU_SHENSHE = RuleImage(roi_front=(872,659,62,25), roi_back=(872,659,62,25), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_ryou_shenshe.png")
	# 神社->狭间暗域 
	I_RYOU_NARROW_ABYSS = RuleImage(roi_front=(707,492,110,27), roi_back=(707,492,110,27), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_ryou_narrow_abyss.png")
	# 狭间_神龙入口 
	I_NARROW_DRAGON = RuleImage(roi_front=(224,200,57,155), roi_back=(224,200,57,155), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_dragon.png")
	# 狭间_孔雀入口 
	I_NARROW_PEACOCK = RuleImage(roi_front=(515,149,58,170), roi_back=(515,149,58,170), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_peacock.png")
	# 狭间_白藏主入口 
	I_NARROW_FOX = RuleImage(roi_front=(811,173,56,179), roi_back=(811,173,56,179), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_fox.png")
	# 狭间_黑豹入口 
	I_NARROW_LEOPARD = RuleImage(roi_front=(1141,165,50,161), roi_back=(1141,165,50,161), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_leopard.png")
	# 战报 
	I_NARROW_NAVIGATION = RuleImage(roi_front=(1199,374,50,44), roi_back=(1199,374,50,44), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_navigation.png")
	# 式神录 
	I_NARROW_SHIKI = RuleImage(roi_front=(1199,462,47,53), roi_back=(1199,462,47,53), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_shiki.png")
	# 狭间暗域 
	I_NARROW_ABYSS = RuleImage(roi_front=(711,489,107,38), roi_back=(711,489,107,38), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_abyss.png")
	# 开启狭间暗域 
	I_OPEN_NARROW_ABYSS = RuleImage(roi_front=(1133,602,74,58), roi_back=(1133,602,74,58), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_open_narrow_abyss.png")
	# 战报页面 
	I_NARROW_MAP = RuleImage(roi_front=(306,147,170,48), roi_back=(306,147,170,48), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_map.png")
	# 战报退出按钮 
	I_NARROW_MAP_EXIT = RuleImage(roi_front=(1154,96,32,32), roi_back=(1154,96,32,32), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_map_exit.png")
	# 挑战按钮 
	I_NARROW_FIRE = RuleImage(roi_front=(1121,605,77,50), roi_back=(1121,605,77,50), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_fire.png")
	# 前往 
	I_NARROW_GOTO_ENEMY = RuleImage(roi_front=(1120,610,75,45), roi_back=(1120,610,75,45), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_narrow_goto_enemy.png")
	# description 
	I_CHANGE_AREA = RuleImage(roi_front=(993,610,63,61), roi_back=(993,610,63,61), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_change_area.png")
	# description 
	I_ENSURE_BUTTON = RuleImage(roi_front=(672,405,169,55), roi_back=(672,405,169,55), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_ensure_button.png")
	# 进攻中 
	I_IS_ATTACK = RuleImage(roi_front=(586,62,73,27), roi_back=(586,62,73,27), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_is_attack.png")
	# description 
	I_PEACOCK_AREA = RuleImage(roi_front=(577,14,127,36), roi_back=(577,14,127,36), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_peacock_area.png")
	# 黑豹领域 
	I_LEOPARD_AREA = RuleImage(roi_front=(589,13,104,39), roi_back=(589,13,104,39), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_leopard_area.png")
	# 白藏主领域 
	I_FOX_AREA = RuleImage(roi_front=(581,18,121,29), roi_back=(581,18,121,29), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_fox_area.png")
	# 更换领域 
	I_CHANGE_AREA = RuleImage(roi_front=(511,20,27,27), roi_back=(511,20,27,27), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_change_area.png")
	# 神龙领域 
	I_DRAGON_AREA = RuleImage(roi_front=(584,15,111,34), roi_back=(584,15,111,34), threshold=0.8, method="Template matching", file="./tasks/NarrowAbyss/res/res_dragon_area.png")


	# List Rule Assets
	# 这个是当前活跃的竂活动列表界面 
	L_RYOU_ACTIVITY_LIST = RuleList(folder="./tasks/NarrowAbyss/res", direction="vertical", mode="ocr", roi_back=(35,157,37,250), size=(42, 27), 
					 array=["道馆", "首领", "狭间"])


	# Swipe Rule Assets
	# 滑到狭间 
	S_TO_NARROWABBSY = RuleSwipe(roi_front=(752,395,62,66), roi_back=(758,193,62,48), mode="default", name="to_narrowabbsy")


