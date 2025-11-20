from pydantic import Field, BaseModel

from tasks.Component.config_base import DateTime


class AccountInfo(BaseModel):
    """
        character:   角色名字
        svr:         角色所在服务器
        account:     账号
        appleOrAndroid:  角色所属平台 安卓/苹果(可选)
                False           Apple
                True            Android
    """
    character: str = Field(default="", description='character_help')
    svr: str = Field(default="", description="svr_help")
    account: str = Field(default="", description="account_help")
    # 为防止ocr出错 暂定格式 字符串以#分割
    account_alias: str = Field(default="", description="account_alias_help")
    apple_or_android: bool = Field(default=True, description="apple_or_android_help")

    # 各个任务的最后执行时间
    last_complete_time: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description="多账号日常任务完成时间")
    last_kekkai_utilize_time: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description="寄养任务完成时间")
    last_kekkai_activation_time: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description="挂卡任务完成时间")
    last_demon_encounter_time: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description="逢魔任务完成时间")

    def is_account_alias(self, ocr_account):
        # 先检查完全匹配
        if ocr_account == self.account:
            return True

        # 对两个账号都进行预处理后比较（去除@后面的部分）
        tmp_account = AccountInfo.preprocessAccount(self.account)
        tmp_ocr_account = AccountInfo.preprocessAccount(ocr_account)

        # 预处理后的账号必须完全相等，而不是startswith
        # 这样可以避免 jiyibanana 匹配到 jiyibanana2
        if tmp_ocr_account == tmp_account:
            return True

        # 检查账号别名
        if not self.account_alias:
            return False
        _accountAliasList = self.account_alias.split('#')
        for alias in _accountAliasList:
            # 别名也使用完全匹配，避免 jiyibanana 匹配到 jiyibanana2
            if tmp_ocr_account == alias or ocr_account == alias:
                return True
        return False

    @staticmethod
    def preprocessAccount(account: str):
        """
            预处理账号信息 便于比对
            邮箱账号        去除@后面的部分 防止@被识别为其他
        @param account:
        @type account:
        @return:
        @rtype:
        """
        return account.split('@')[0]

    def is_valid(self):
        return self.character!="" and self.character is not None