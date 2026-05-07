# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase


class PetsConfig(ConfigBase):
    pets_feast: bool = Field(default=True)


class GoToOrochiConfig(ConfigBase):
    go_to_orochi: bool = Field(default=False, description='go_to_orochi_help')


class Pets(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    pets_config: PetsConfig = Field(default_factory=PetsConfig)
    go_to_orochi_config: GoToOrochiConfig = Field(default_factory=GoToOrochiConfig)
