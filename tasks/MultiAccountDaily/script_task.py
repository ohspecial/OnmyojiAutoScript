# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import importlib
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from module.exception import TaskEnd, RequestHumanTakeover
from module.logger import logger
from tasks.Component.SwitchAccount.switch_account import SwitchAccount
from tasks.MultiAccountDaily.assets import MultiAccountDailyAssets
from tasks.MultiAccountDaily.config import MultiAccountDaily, AccountInfo
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main


class ScriptTask(GameUi, MultiAccountDailyAssets):
    """多账号日常任务脚本"""
    
    multi_conf: MultiAccountDaily = None

    def run(self):
        """主运行函数"""
        self.multi_conf = self.config.multi_account_daily

        # 记录是否是第一个账号
        is_first_account = True

        # 遍历所有账号
        for account_info in self.multi_conf.account_list:
            logger.info(f"开始处理账号: {account_info.character}-{account_info.svr}")

            # 检查是否需要登录
            if not self.is_need_login(account_info):
                logger.warning(
                    f"{account_info.character} 跳过，上次登录时间: {account_info.last_complete_time}"
                )
                continue

            # 切换账号
            # 第一个账号：正常切换（可能需要退出游戏）
            # 后续账号：从游戏内直接退出到登录界面切换
            if is_first_account:
                success = SwitchAccount(self.config, self.device, account_info).switchAccount()
                is_first_account = False
            else:
                # 后续账号：先退出到登录界面，再切换
                success = self.switch_account_from_game(account_info)

            if not success:
                logger.error(f"❌ 账号切换失败！请检查配置文件中的账号信息是否正确！")
                logger.error(f"账号: {account_info.account}, 角色: {account_info.character}, 服务器: {account_info.svr}")

                # 尝试登录第一个配置的账号，避免停留在登录界面影响后续任务
                logger.info("正在尝试登录第一个配置的账号...")
                try:
                    if self.multi_conf.account_list and len(self.multi_conf.account_list) > 0:
                        first_account = self.multi_conf.account_list[0]
                        logger.info(f"尝试登录第一个账号: {first_account.character}-{first_account.svr}")
                        from tasks.Component.SwitchAccount.login_account import LoginAccount
                        from tasks.Restart.login import LoginHandler

                        login_account = LoginAccount(self.config, self.device)
                        if login_account.login(first_account):
                            logger.info(f"✅ 成功登录第一个账号: {first_account.character}")
                            # 处理登录后的弹窗
                            login_handler = LoginHandler(config=self.config, device=self.device)
                            login_handler.set_specific_usr(first_account.svr)
                            login_handler.app_handle_login()
                        else:
                            logger.error(f"❌ 登录第一个账号失败")
                    else:
                        logger.error(f"❌ 无法获取第一个账号信息")
                except Exception as e:
                    logger.error(f"❌ 登录第一个账号时出错: {e}")

                # 设置下次运行为失败状态
                self.set_next_run('MultiAccountDaily', success=False)
                # 抛出异常结束任务，不继续执行 run_daily_tasks()
                raise TaskEnd(f"账号切换失败: {account_info.character}-{account_info.svr}")

            # 账号切换成功，执行日常任务
            try:
                logger.info(f"✅ 账号切换成功，开始执行日常任务: {account_info.character}-{account_info.svr}")

                # 执行常规日常任务
                self.run_daily_tasks()

                # 执行定时任务（寄养、挂卡、逢魔）
                self.run_timed_tasks(account_info)

                # 更新配置文件中的时间
                self.multi_conf.update_account_login_history(account_info)
                self.config.save()
                logger.info(f"✅ {account_info.character}-{account_info.svr} 所有任务全部完成")

            except TaskEnd as e:
                logger.info(f"ℹ️ {account_info.character}-{account_info.svr} 任务结束: {e}")
                self.multi_conf.update_account_login_history(account_info)
                self.config.save()
                continue
            except RequestHumanTakeover as e:
                raise
            except Exception as e:
                logger.error(f"账号 {account_info.character} 执行任务时出错: {e}")
                self.set_next_run('MultiAccountDaily', success=False)
                continue

        # 所有账号处理完成
        self.set_next_run_by_time()
        raise TaskEnd("MultiAccountDaily")

    def run_daily_tasks(self):
        """执行日常任务"""
        conf = self.multi_conf.multi_account_config

        # 确保在主界面
        self.ui_get_current_page()
        self.ui_goto(page_main)

        # 执行日常琐事
        if conf.one_summon or conf.friend_love or conf.luck_msg or conf.store_sign or conf.buy_sushi_count > 0:
            self.run_daily_trifles()

        # 执行道馆突破
        if conf.dokan:
            self.run_task_by_name("Dokan")

        # 执行御魂副本（八岐大蛇）
        if conf.souls:
            self.run_task_by_name("Orochi")

        # 执行觉醒副本
        if conf.awakening:
            self.run_task_by_name("EvoZone")

        # 执行经验妖怪
        if conf.exp_youkai:
            self.run_task_by_name("ExperienceYoukai")

        # 执行金币妖怪
        if conf.gold_youkai:
            self.run_task_by_name("GoldYoukai")

        logger.info("当前账号所有日常任务执行完成")

    def run_timed_tasks(self, account_info: AccountInfo):
        """
        执行定时任务（需要检查时间间隔的任务）
        :param account_info: 当前账号信息
        """
        conf = self.multi_conf.multi_account_config
        logger.info(f"🔍 开始检查定时任务 - 账号: {account_info.character}-{account_info.svr}")
        logger.info(f"配置状态 - 寄养: {conf.kekkai_utilize}, 挂卡: {conf.kekkai_activation}, 逢魔: {conf.demon_encounter}")

        # 执行结界寄养
        if conf.kekkai_utilize:
            logger.info(f"检查结界寄养任务...")
            if self.multi_conf.should_run_task(account_info, 'KekkaiUtilize', conf.kekkai_utilize_interval):
                try:
                    logger.info(f"✅ 开始执行结界寄养任务")
                    self.run_task_by_name("KekkaiUtilize")
                    # 更新任务时间
                    self.multi_conf.update_account_task_time(account_info, 'KekkaiUtilize')
                    self.config.save()
                    logger.info(f"✅ 结界寄养任务完成")
                except Exception as e:
                    logger.error(f"❌ 执行结界寄养任务失败: {e}")
        else:
            logger.info(f"⏭️ 结界寄养任务未启用，跳过")

        # 执行结界挂卡
        if conf.kekkai_activation:
            logger.info(f"检查结界挂卡任务...")
            if self.multi_conf.should_run_task(account_info, 'KekkaiActivation', conf.kekkai_activation_interval):
                try:
                    logger.info(f"✅ 开始执行结界挂卡任务")
                    self.run_task_by_name("KekkaiActivation")
                    # 更新任务时间
                    self.multi_conf.update_account_task_time(account_info, 'KekkaiActivation')
                    self.config.save()
                    logger.info(f"✅ 结界挂卡任务完成")
                except Exception as e:
                    logger.error(f"❌ 执行结界挂卡任务失败: {e}")
        else:
            logger.info(f"⏭️ 结界挂卡任务未启用，跳过")

        # 执行逢魔之时
        if conf.demon_encounter:
            logger.info(f"检查逢魔之时任务...")
            if self.multi_conf.should_run_task(account_info, 'DemonEncounter', conf.demon_encounter_interval):
                try:
                    logger.info(f"✅ 开始执行逢魔之时任务")
                    self.run_task_by_name("DemonEncounter")
                    # 更新任务时间
                    self.multi_conf.update_account_task_time(account_info, 'DemonEncounter')
                    self.config.save()
                    logger.info(f"✅ 逢魔之时任务完成")
                except Exception as e:
                    logger.error(f"❌ 执行逢魔之时任务失败: {e}")
        else:
            logger.info(f"⏭️ 逢魔之时任务未启用，跳过")

        logger.info(f"🔍 定时任务检查完成")

    def run_daily_trifles(self):
        """执行日常琐事任务"""
        from tasks.DailyTrifles.script_task import ScriptTask as DailyTriflesTask
        from tasks.DailyTrifles.assets import DailyTriflesAssets

        conf = self.multi_conf.multi_account_config
        
        # 创建临时的日常琐事任务实例
        # 由于我们继承了 GameUi，可以直接调用相关方法
        # 但为了使用 DailyTrifles 的具体实现，我们需要动态混入
        
        # 每日召唤
        if conf.one_summon:
            logger.info("执行每日召唤")
            self.run_task_method("DailyTrifles", "run_one_summon")
        
        # 友情点
        if conf.friend_love:
            logger.info("收取友情点")
            self.run_task_method("DailyTrifles", "run_friend_love")
        
        # 吉闻
        if conf.luck_msg:
            logger.info("收取吉闻")
            self.run_task_method("DailyTrifles", "run_luck_msg")
        
        # 商店签到或购买寿司
        if conf.store_sign or conf.buy_sushi_count > 0:
            logger.info("执行商店任务")
            self.run_task_method("DailyTrifles", "run_store")

    def run_task_by_name(self, task_name: str):
        """通过任务名称动态加载并执行任务"""
        try:
            logger.info(f"开始执行任务: {task_name}")
            
            # 动态导入任务模块
            module_path = Path.cwd() / 'tasks' / task_name / 'script_task.py'
            spec = importlib.util.spec_from_file_location('script_task', module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 创建任务实例并执行
            task = module.ScriptTask(config=self.config, device=self.device)
            task.run()
            
        except TaskEnd:
            logger.info(f"任务 {task_name} 完成")
        except Exception as e:
            logger.error(f"执行任务 {task_name} 时出错: {e}")

    def run_task_method(self, task_name: str, method_name: str):
        """执行指定任务的指定方法"""
        try:
            # 动态导入任务模块
            module_path = Path.cwd() / 'tasks' / task_name / 'script_task.py'
            spec = importlib.util.spec_from_file_location('script_task', module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 创建任务实例
            task = module.ScriptTask(config=self.config, device=self.device)
            
            # 调用指定方法
            if hasattr(task, method_name):
                method = getattr(task, method_name)
                method()
            else:
                logger.warning(f"任务 {task_name} 没有方法 {method_name}")
                
        except Exception as e:
            logger.error(f"执行 {task_name}.{method_name} 时出错: {e}")

    def switch_account_from_game(self, account_info: AccountInfo) -> bool:
        """
        从游戏内切换账号
        先退出到登录界面，再切换账号
        """
        from tasks.Component.SwitchAccount.exit_game import ExitGame
        from tasks.Component.SwitchAccount.login_account import LoginAccount
        from tasks.Restart.login import LoginHandler

        try:
            # 确保在主界面
            current_page = self.ui_get_current_page()
            if current_page != page_main:
                self.ui_goto(page_main)

            # 退出游戏到登录界面
            exit_game = ExitGame(self.config, self.device)
            exit_game.exitGame()

            # 登录新账号
            login_account = LoginAccount(self.config, self.device)
            if not login_account.login(account_info):
                return False

            logger.info(f"{account_info.character} login suc")

            # 处理登录后的弹窗
            login_handler = LoginHandler(config=self.config, device=self.device)
            login_handler.set_specific_usr(account_info.svr)
            login_handler.app_handle_login()

            return True
        except Exception as e:
            logger.error(f"从游戏内切换账号失败: {e}")
            return False

    def is_need_login(self, account: AccountInfo) -> bool:
        """
        根据上次登录时间判断是否需要登录
        规则：
        1. 距离上次登录超过13小时
        2. 上次登录在18点后或5点前，现在是5-18点之间
        3. 上次登录在5-18点之间，现在是18点后
        """
        last_time = account.last_complete_time
        now = datetime.now()

        # 超过13小时
        if now - last_time > timedelta(hours=13):
            return True

        # 上次登录在18点后或5点前，现在是5-18点之间（早上时段）
        if (last_time.hour >= 18 or last_time.hour < 5) and (18 > now.hour >= 5):
            return True

        # 上次登录在5-18点之间，现在是18点后（晚上时段）
        if (5 <= last_time.hour < 18) and now.hour >= 18:
            return True

        return False

    def restart_and_login_first_account(self):
        """
        重启游戏并登录到第一个有效账号
        用于账号切换失败后恢复游戏状态
        """
        # 停止游戏
        logger.info("停止游戏...")
        self.device.app_stop()

        # 等待一下确保游戏完全停止
        import time
        time.sleep(2)

        # 启动游戏
        logger.info("启动游戏...")
        self.device.app_start()

        # 等待游戏启动
        time.sleep(5)

        # 找到第一个有效的账号（上次登录成功的账号）
        first_valid_account = None
        for account in self.multi_conf.account_list:
            # 如果账号有登录历史（不是默认时间），说明之前登录成功过
            if account.last_complete_time.year > 2023:
                first_valid_account = account
                break

        # 如果没有找到有效账号，使用第一个账号
        if first_valid_account is None:
            first_valid_account = self.multi_conf.account_list[0]

        logger.info(f"尝试登录到账号: {first_valid_account.character}-{first_valid_account.svr}")
        logger.info(f"账号邮箱: {first_valid_account.account}")
        logger.info(f"平台: {'Android' if first_valid_account.apple_or_android else 'Apple'}")

        # 使用 SwitchAccount 处理完整的登录流程
        # 这个类会处理：退出游戏 -> 账号选择 -> Apple/Android 选择 -> 角色选择
        from tasks.Component.SwitchAccount.switch_account import SwitchAccount

        switch_account = SwitchAccount(self.config, self.device, first_valid_account)
        if switch_account.switchAccount():
            logger.info(f"✅ 成功登录到账号: {first_valid_account.character}-{first_valid_account.svr}")
        else:
            logger.error(f"❌ 登录到账号 {first_valid_account.character} 失败")
            # 即使失败也不抛出异常，让任务继续结束
            # 至少游戏已经重启了，不会一直卡在错误的登录界面

    def set_next_run_by_time(self):
        """根据当前时间设置下次运行时间"""
        now = datetime.now()

        # 如果当前是5-18点之间，下次运行时间设置为18:05
        if 5 <= now.hour < 18:
            next_run = now.replace(hour=18, minute=5, second=0, microsecond=0)
        # 如果当前是0-5点之间，下次运行时间设置为5:05
        elif now.hour < 5:
            next_run = now.replace(hour=5, minute=5, second=0, microsecond=0)
        # 如果当前是18点后，下次运行时间设置为明天5:05
        else:
            next_run = (now + timedelta(days=1)).replace(hour=5, minute=5, second=0, microsecond=0)

        self.set_next_run('MultiAccountDaily', target=next_run, success=True)
        logger.info(f"下次运行时间: {next_run}")


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('switch')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

