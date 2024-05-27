# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field
from enum import Enum

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

class UserStatus(str, Enum):
    # LEADER = 'leader'
    # MEMBER = 'member'
    ALONE = 'alone'
    # WILD = 'wild'  # 还不打算实现

class Layer(str, Enum):
    ONE = '壹层'
    TWO = '贰层'
    THREE = '叁层'
    FOUR = '肆层'
    FIVE = '伍层'
    SIX = '陆层'
    SEVEN = '柒层'
    EIGHT = '捌层'
    NINE = '玖层'
    TEN = '拾层'
    ELEVEN = '悲鸣'
    TWELVE = '神罚'

class PetsConfig(ConfigBase):
    # 其乐融融
    pets_happy: bool = Field(default=True)
    # 大餐
    pets_feast: bool = Field(default=True)

class GoToOrochiConfig(ConfigBase):
    # 打完是否要去打一把魂十
    go_to_orochi: bool = Field(default=True)
    # 身份
    user_status: UserStatus = Field(default=UserStatus.ALONE, description='user_status_help')
    # 攻打次数，默认1次
    limin_count: int = Field(default=1, description='filight_timse')
    # 层数
    layer: Layer = Field(default=Layer.TEN, description='layer_help')
    # 是否切换御魂
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    # 通用战斗设置
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

class Pets(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    pets_config: PetsConfig = Field(default_factory=PetsConfig)
    go_to_orochi_config: GoToOrochiConfig = Field(default_factory=GoToOrochiConfig)


