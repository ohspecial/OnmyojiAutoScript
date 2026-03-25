# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime
from typing import Any, Dict

from pydantic import Field, BaseModel, model_validator, model_serializer, ValidationError

from deploy.logger import logger
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class MultiAccountDailyConfig(ConfigBase):
    """多账号日常任务配置"""
    # 账号数量
    account_count: int = Field(default=1, ge=1, description='账号数量')

    # 日常琐事相关
    one_summon: bool = Field(default=False, description='每日召唤')
    friend_love: bool = Field(default=False, description='收取友情点')
    luck_msg: bool = Field(default=False, description='收取吉闻')
    store_sign: bool = Field(default=False, description='商店签到')
    buy_sushi_count: int = Field(default=-1, description='购买体力次数，-1表示不购买')

    # 其他日常任务
    dokan: bool = Field(default=False, description='道馆突破')
    souls: bool = Field(default=False, description='御魂副本')
    awakening: bool = Field(default=False, description='觉醒副本')
    exp_youkai: bool = Field(default=False, description='经验妖怪')
    gold_youkai: bool = Field(default=False, description='金币妖怪')

    # 定时任务（需要检查时间间隔）
    kekkai_utilize: bool = Field(default=False, description='结界寄养')
    kekkai_utilize_interval: int = Field(default=6, ge=1, le=24, description='寄养任务间隔（小时）')

    kekkai_activation: bool = Field(default=False, description='结界挂卡')
    kekkai_activation_interval: int = Field(default=6, ge=1, le=24, description='挂卡任务间隔（小时）')

    demon_encounter: bool = Field(default=False, description='逢魔之时')
    demon_encounter_interval: int = Field(default=24, ge=1, le=48, description='逢魔任务间隔（小时）')


class MultiAccountDaily(ConfigBase):
    """多账号日常任务主配置"""
    scheduler: Scheduler = Field(default_factory=Scheduler)
    multi_account_config: MultiAccountDailyConfig = Field(default_factory=MultiAccountDailyConfig)

    # 账号列表
    account_list: list[AccountInfo] = None

    def update_account_login_history(self, account: AccountInfo):
        """更新账号登录历史"""
        for info in self.account_list:
            if info.character != account.character or info.svr != account.svr:
                continue
            info.last_complete_time = datetime.now()
            break

    def update_account_task_time(self, account: AccountInfo, task_name: str):
        """
        更新指定账号的指定任务执行时间
        :param account: 账号信息
        :param task_name: 任务名称，可选值: 'KekkaiUtilize', 'KekkaiActivation', 'DemonEncounter'
        """
        task_time_mapping = {
            'KekkaiUtilize': 'last_kekkai_utilize_time',
            'KekkaiActivation': 'last_kekkai_activation_time',
            'DemonEncounter': 'last_demon_encounter_time',
        }

        if task_name not in task_time_mapping:
            logger.warning(f"未知的任务名称: {task_name}")
            return

        time_field = task_time_mapping[task_name]
        for info in self.account_list:
            if info.character != account.character or info.svr != account.svr:
                continue
            setattr(info, time_field, datetime.now())
            logger.info(f"✅ 更新账号 {account.character}-{account.svr} 的 {task_name} 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            break

    def should_run_task(self, account: AccountInfo, task_name: str, interval_hours: int) -> bool:
        """
        判断是否需要执行任务
        :param account: 账号信息
        :param task_name: 任务名称
        :param interval_hours: 时间间隔（小时）
        :return: True 表示需要执行，False 表示不需要
        """
        from datetime import timedelta

        task_time_mapping = {
            'KekkaiUtilize': 'last_kekkai_utilize_time',
            'KekkaiActivation': 'last_kekkai_activation_time',
            'DemonEncounter': 'last_demon_encounter_time',
        }

        if task_name not in task_time_mapping:
            logger.warning(f"未知的任务名称: {task_name}")
            return False

        time_field = task_time_mapping[task_name]
        last_time = getattr(account, time_field, None)

        if not last_time:
            return True

        # 计算时间差
        time_diff = datetime.now() - last_time
        should_run = time_diff >= timedelta(hours=interval_hours)

        if should_run:
            logger.info(f"账号 {account.character}-{account.svr} 的 {task_name} 需要执行（上次执行: {last_time.strftime('%Y-%m-%d %H:%M:%S')}）")
        else:
            remaining = timedelta(hours=interval_hours) - time_diff
            logger.info(f"账号 {account.character}-{account.svr} 的 {task_name} 还未到执行时间（剩余: {remaining}）")

        return should_run

    @model_validator(mode='before')
    @classmethod
    def validator_all(cls, v: dict) -> Any:
        """验证并初始化账号列表"""
        account_count = v.get('multi_account_config', {}).get('account_count', 1)
        if account_count is None:
            account_count = v.get('account_count', 1)

        def validator_list(list_name, data, item_type=None, list_size=1):
            if list_name not in data:
                data[list_name] = []

            remove_keys = []
            for key, value in data.items():
                if list_name == key or list_name not in key:
                    continue
                try:
                    item = item_type(**value)
                    if item.is_valid():
                        data[list_name].append(item)
                    remove_keys.append(key)
                except ValidationError:
                    pass
                except TypeError:
                    pass

            for key in remove_keys:
                del data[key]

            if item_type is not None:
                if len(data[list_name]) < list_size:
                    for i in range(list_size - len(data[list_name])):
                        data[list_name].append(item_type())

        validator_list('account_list', v, AccountInfo, account_count)
        return v

    @model_serializer()
    def serializer_model(self) -> Dict[str, Any]:
        """序列化模型"""
        properties = self.__dict__
        data = {}

        def v_dump(v):
            try:
                return v.model_dump()
            except AttributeError as e:
                logger.error(e)
                return v

        for key, value in properties.items():
            if isinstance(value, list):
                for index, v in enumerate(value):
                    data[f'{key}_{index + 1}'] = v_dump(v)
            else:
                data[key] = v_dump(value)
        return data

