from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class QuizAssets: 


	# Image Rule Assets
	# description 
	I_ENTRY = RuleImage(roi_front=(143,363,40,128), roi_back=(119,246,100,326), threshold=0.8, method="Template matching", file="./tasks/Quiz/quiz/quiz_entry.png")
	# 开始 
	I_START = RuleImage(roi_front=(1149,608,66,41), roi_back=(1136,574,100,100), threshold=0.8, method="Template matching", file="./tasks/Quiz/quiz/quiz_start.png")
	# 标志 
	I_MESSAGE = RuleImage(roi_front=(75,488,58,41), roi_back=(50,460,100,100), threshold=0.8, method="Template matching", file="./tasks/Quiz/quiz/quiz_message.png")
	# 失败然后离开 
	I_FAIL_QUIT = RuleImage(roi_front=(416,529,183,45), roi_back=(354,502,275,100), threshold=0.8, method="Template matching", file="./tasks/Quiz/quiz/quiz_fail_quit.png")
	# 结算分享 
	I_SHARE = RuleImage(roi_front=(1171,625,53,44), roi_back=(1152,592,100,100), threshold=0.8, method="Template matching", file="./tasks/Quiz/quiz/quiz_share.png")


	# Ocr Rule Assets
	# Ocr-description 
	O_QUESTION = RuleOcr(roi=(903,32,322,101), area=(903,32,322,101), mode="Single", method="Default", keyword="", name="question")
	# Ocr-description 
	O_ANSWER1 = RuleOcr(roi=(906,178,320,53), area=(906,178,320,53), mode="Single", method="Default", keyword="", name="answer1")
	# Ocr-description 
	O_ANSWER2 = RuleOcr(roi=(905,289,319,51), area=(905,289,319,51), mode="Single", method="Default", keyword="", name="answer2")
	# Ocr-description 
	O_ANSWER3 = RuleOcr(roi=(906,399,320,55), area=(906,399,320,55), mode="Single", method="Default", keyword="", name="answer3")
	# Ocr-description 
	O_ANSWER4 = RuleOcr(roi=(909,511,316,54), area=(909,511,316,54), mode="Single", method="Default", keyword="", name="answer4")
	# 倒计时 
	O_COUNTDOWN = RuleOcr(roi=(1045,6,27,30), area=(1045,6,27,30), mode="Digit", method="Default", keyword="4", name="countdown")
	# 倒计时 
	O_COUNTDOWN3 = RuleOcr(roi=(1045,6,27,30), area=(1045,6,27,30), mode="Digit", method="Default", keyword="3", name="countdown3")


