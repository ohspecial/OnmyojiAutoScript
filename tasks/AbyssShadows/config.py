# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from pydantic import BaseModel, Field
from enum import Enum
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler



class AbyssShadowsConfig(BaseModel):
    
    # 防封：使用固定的随机区域进行随机点击，若为False将自动识别当前画面中的最大纯色区域作为随机点击区域
    anti_detect_click_fixed_random_area: bool = Field(default=False, description='anti_detect_click_fixed_random_area_help')

class AbyssShadows(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    abyss_shadows_config: AbyssShadowsConfig = Field(default_factory=AbyssShadowsConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)