from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class FallenSunAssets: 


	# Image Rule Assets
	# 选择日轮 
	I_FALLEN_SUN = RuleImage(roi_front=(784,113,290,396), roi_back=(784,113,290,396), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_fallen_sun.png")
	# 组队 
	I_FORM_TEAM = RuleImage(roi_front=(939,594,96,90), roi_back=(939,594,96,90), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_form_team.png")
	# description 
	I_FALLEN_SUN_FIRE = RuleImage(roi_front=(1108,592,96,93), roi_back=(1108,592,96,93), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_fallen_sun_fire.png")
	# description 
	I_FALLEN_SUN_UNLOCK = RuleImage(roi_front=(557,560,31,38), roi_back=(557,560,31,38), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_fallen_sun_unlock.png")
	# description 
	I_FALLEN_SUN_LOCK = RuleImage(roi_front=(557,561,31,37), roi_back=(557,561,31,37), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_fallen_sun_lock.png")
	# 小小宠物，发现宝藏 
	I_PET_PRESENT = RuleImage(roi_front=(873,184,62,147), roi_back=(873,184,62,147), threshold=0.8, method="Template matching", file="./tasks/FallenSun/f/f_pet_present.png")


	# List Rule Assets
	# 这个是御魂界面选择不同层数的 
	L_LAYER_LIST = RuleList(folder="./tasks/FallenSun/res", direction="vertical", mode="ocr", roi_back=(138,130,359,500), size=(40, 93), 
					 array=["壹", "贰", "叁"])


	# Ocr Rule Assets
	# Ocr-description 
	O_O_TEST_OCR = RuleOcr(roi=(126,136,360,491), area=(126,136,360,491), mode="Full", method="Default", keyword="", name="o_test_ocr")


