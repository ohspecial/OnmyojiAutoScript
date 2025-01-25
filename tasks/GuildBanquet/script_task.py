# This Python file uses the following encoding: utf-8
# @author ohspecial
# github https://github.com/ohspecial
from time import sleep
from datetime import datetime ,timedelta

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_guild, page_main
from tasks.GuildBanquet.assets import GuildBanquetAssets

weekday_dict = {
    0: '星期一',
    1: '星期二',
    2: '星期三',
    3: '星期四',
    4: '星期五',
    5: '星期六',
    6: '星期日'
}

    
class ScriptTask(GameUi, GuildBanquetAssets):

    def run(self):
        self.run_time = self.config.guild_banquet.guild_banquet_time
        print(self.run_time)
        # 第一天宴会日期及时间
        self.banquet_day_1 = self.get_key_from_value(weekday_dict, self.run_time.day_1.value)
        self.banquet_day_1_start_time = self.run_time.run_time_1
        
        # 第二天宴会日期及时间
        self.banquet_day_2 = self.get_key_from_value(weekday_dict, self.run_time.day_2.value)
        self.banquet_day_2_start_time = self.run_time.run_time_2
        if not self.check_runtime():
            # 如果不是宴会日则设置下次运行时间
            self.plan_next_run()
            raise TaskEnd('GuildBanquet')
        
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        
        if self.appear(self.I_FLAG):
            wait_count = 0
            wait_timer = Timer(270)
            wait_timer.start()
            logger.info("Start guild banquet!")
            self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            # 如果没有找到FLAG，可能是宴会时间没开始，5分钟后尝试再次查找
            time_now = datetime.now()
            time_later = time_now + timedelta(minutes=5)
            self.set_next_run(task='GuildBanquet',
                              finish=True,
                              target=time_later)
            raise TaskEnd('GuildBanquet')
        # 开始宴会
        while True:
            if self.appear(self.I_ANSWER_SCORE, interval=5):
                logger.info("Wait in place or answer the question manually")
            
            if wait_timer.reached():
                wait_timer.reset()
                if wait_count >= 2:
                    # 记三次，时间到了就结束
                    logger.info('Guild banquet timeout')
                    break
                wait_count += 1
                logger.warning('In Guild banquet, wait')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.set_next_run(task="GuildBanquet",finish=True,success=True,target=datetime())
        raise TaskEnd("GuildBanquet")
        
    def check_runtime(self) -> bool:
        """
        检查日期和时间, 是否是宴会日
        """
        now = datetime.now()
        day_of_week = now.weekday()
        # 判断当前日期是否是寮宴会日
        if day_of_week in [self.banquet_day_1, self.banquet_day_2]:
            return True

    def plan_next_run(self):
        # 安排次日宴会，便于复用
        today = datetime.now().weekday()
        
        if today < self.banquet_day_1:
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=self.banquet_day_1 - today) 
        elif self.banquet_day_1 <= today < self.banquet_day_2:
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_2_start_time, time_delta=self.banquet_day_2 - today)
        elif self.banquet_day_2 <= today:
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=7 - today + self.banquet_day_1) 
        logger.info(f"Plan next run") 
        
    def get_key_from_value(self, dict, value):
        return [k for k, v in dict.items() if v == value][0]
    
    

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('xiaohao')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()

