# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field


class Config(BaseModel):
    enable: bool = Field(default=False, description='enabled_help')
    account_name: str = Field(default='未知账号', description='name')
    enable_push_notify: bool = Field(default=False, description='消息通知')
    enable_save_image: bool = Field(default=False, description='截图保存')


class SwitchAccountConfig(BaseModel):
    config: Config = Field(default_factory=Config)
