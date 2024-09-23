from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class ActivityShikigamiAssets: 


	# Image Rule Assets
	# description 
	I_N_BATTLE = RuleImage(roi_front=(131,164,86,86), roi_back=(119,50,1075,635), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/0110/0110_n_battle.png")
	# description 
	I_N_CONFIRM = RuleImage(roi_front=(670,402,176,63), roi_back=(670,402,176,63), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/0110/0110_n_confirm.png")
	# description 
	I_C_CONFIRM1 = RuleImage(roi_front=(560,341,37,38), roi_back=(560,341,37,38), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/0110/0110_c_confirm1.png")


	# Click Rule Assets
	# description 
	C_RANDOM_LEFT = RuleClick(roi_front=(21,23,290,599), roi_back=(21,23,290,599), name="random_left")
	# description 
	C_RANDOM_RIGHT = RuleClick(roi_front=(969,55,296,638), roi_back=(969,55,296,638), name="random_right")
	# description 
	C_RANDOM_TOP = RuleClick(roi_front=(85,46,1159,101), roi_back=(85,46,1159,101), name="random_top")
	# description 
	C_RANDOM_BOTTOM = RuleClick(roi_front=(182,539,1063,100), roi_back=(182,539,1063,100), name="random_bottom")
	# description 
	C_RANDOM_ALL = RuleClick(roi_front=(42,94,1207,543), roi_back=(42,94,1207,543), name="random_all")


	# Image Rule Assets
	# 进入活动 
	I_SHI = RuleImage(roi_front=(440,169,50,43), roi_back=(337,115,301,424), threshold=0.7, method="Template matching", file="./tasks/ActivityShikigami/as/as_shi.png")
	# 左上角返回 
	I_BACK_GREEN = RuleImage(roi_front=(23,27,44,44), roi_back=(23,27,44,44), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_back_green.png")
	# 进入爬塔 
	I_BATTLE = RuleImage(roi_front=(1104,179,50,166), roi_back=(1104,179,138,315), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_battle.png")
	# 归鹿之途 
	I_DRUM = RuleImage(roi_front=(885,310,29,145), roi_back=(885,310,29,145), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_drum.png")
	# 上锁图标 
	I_LOCK = RuleImage(roi_front=(829.5,655,20,32), roi_back=(793,641,47,56), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_lock.png")
	# 还未上锁图片 
	I_UNLOCK = RuleImage(roi_front=(823,654,23,23), roi_back=(782,640,69,50), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_unlock.png")
	# 点击战斗 
	I_FIRE = RuleImage(roi_front=(1134,587,84,78), roi_back=(1134,587,84,78), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_fire.png")
	# 体力按钮 
	I_AP = RuleImage(roi_front=(1122,516,29,26), roi_back=(1092,487,103,71), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_ap.png")
	# 活动体力 
	I_AP_ACTIVITY = RuleImage(roi_front=(1128,517,21,25), roi_back=(1090,500,84,54), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_ap_activity.png")
	# 切换按键 
	I_SWITCH = RuleImage(roi_front=(1211,518,23,23), roi_back=(1200,497,69,56), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_switch.png")
	# 购买活动的体力 
	I_BUY_JADE = RuleImage(roi_front=(1004,192,38,42), roi_back=(1004,192,38,42), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_buy_jade.png")
	# 增加到最大 
	I_ADD_MAX = RuleImage(roi_front=(17,24,33,37), roi_back=(17,24,33,37), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_add_max.png")
	# description 
	I_NEW = RuleImage(roi_front=(1004,192,65,52), roi_back=(1004,192,65,52), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_new.png")
	# description 
	I_ENTER = RuleImage(roi_front=(441,199,38,30), roi_back=(431,182,62,61), threshold=0.8, method="Template matching", file="./tasks/ActivityShikigami/as/as_enter.png")


	# Ocr Rule Assets
	# 体力的数量检测 
	O_REMAIN_AP = RuleOcr(roi=(1178,679,87,25), area=(1178,679,87,25), mode="DigitCounter", method="Default", keyword="", name="remain_ap")
	# 活动体力的剩余检测 
	O_REMAIN_AP_ACTIVITY = RuleOcr(roi=(714,24,95,30), area=(714,24,95,30), mode="DigitCounter", method="Default", keyword="", name="remain_ap_activity")
	# 还有多少次购买体力的机会 
	O_REMAIN_BUY = RuleOcr(roi=(808,531,39,42), area=(808,531,39,42), mode="DigitCounter", method="Default", keyword="", name="remain_buy")


