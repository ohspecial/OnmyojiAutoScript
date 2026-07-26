# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from cached_property import cached_property

from tasks.GameUi.default_pages import page_exploration, random_click

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import BattleAction, BattleContext, ExitMatcher, GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_realm_raid
from tasks.RealmRaid.assets import RealmRaidAssets
from tasks.RealmRaid.config import RealmRaid
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.RealmRaid.page import page_shikigami_records


from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.atom.image import RuleImage
from module.atom.click import RuleClick


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, RealmRaidAssets):
    round_retreat_done: bool = False

    def _handle_result(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if config.quick_exit:
            context.reward_no_battle_ts = None
            context.is_win = not self.appear(self.I_FALSE)
            return BattleAction.EXIT_WIN if context.is_win else BattleAction.EXIT_LOSE
        return super()._handle_result(context, config)

    def _exit_matcher(self) -> ExitMatcher:
        return self.I_BACK_RED

    def run(self):
        con = self.config.realm_raid
        # 直接进入个人突破页面
        self.goto_page(page_realm_raid)

        # 先检查突破券，避免没有可挑战次数时仍然切换御魂。
        if not self.check_ticket(con.raid_config.number_base):
            self.goto_page(page_exploration)
            self.set_next_run(task='RealmRaid', success=False, finish=True)
            raise TaskEnd

        # 票数足够，现在开始进行御魂切换
        if con.switch_soul_config.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
                
        if con.switch_soul_config.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)
            
        # 切换完成后，必须返回突破页面
        self.goto_page(page_realm_raid)

        # 有呱太活动的时候第一次进入还会 出现一个弹窗
        self.screenshot()
        if self.appear(self.I_FROG_RAID):
            logger.info(f'Click {self.I_FROG_RAID.name}')
            while 1:
                self.screenshot()
                if not self.appear(self.I_FROG_RAID):
                    break
                if self.appear_then_click(self.I_FROG_RAID, interval=1):
                    continue
        # 判断是不是锁定阵容
        self.ensure_lock(con.general_battle_config.lock_team_enable)
        # 判断是否是呱太活动
        frog = self.is_frog(True)
        if frog:
            logger.info(f'Frog raid')

        # 真实挑战次数不包含退四；通用战斗的 current_count 会统计快速退出，不能用于本任务的挑战上限。
        success = True
        real_attack_count = 0
        self.round_retreat_done = self.is_first_position_finished()

        while 1:
            self.screenshot()
            # 刷新确认弹窗可能因页面响应延迟残留，先关闭后再识别盘面。
            if self.appear(self.I_FRESH_ENSURE):
                logger.info("Pop-up detected: Refresh Confirmation. Clicking Confirm.")
                self.appear_then_click(self.I_FRESH_ENSURE, interval=1.5)
                continue

            if not self.check_ticket(con.raid_config.number_base):
                break

            if real_attack_count >= con.raid_config.number_attack:
                logger.info(f'Real attack count {real_attack_count}, max count {con.raid_config.number_attack}')
                break

            force_first_attack = False

            # 阶段只以游戏盘面的三胜标记为准；任务从中途盘面启动时也能正确处理已三胜的一轮。
            if self.has_three_wins(False):
                logger.info('Three wins detected, resolve current round after retreat four')
                three_win_action = self.process_three_win_stage(con)
                if three_win_action == 'refreshed':
                    continue
                if three_win_action == 'stop':
                    success = False
                    break
                force_first_attack = three_win_action == 'attack_first'

            # 屏蔽失败格后继续按勋章优先级寻找其他目标。
            failed_positions = self.get_failed_positions(False)
            if failed_positions:
                logger.info(f'Ignore failed positions: {failed_positions}')

            if force_first_attack:
                medal, index = None, 1
            else:
                medal, index = self.find_one(False, exclude_positions=set(failed_positions))
            if not medal and not index:
                logger.info('No target can be attacked, refresh current round')
                if self.refresh_round(con):
                    continue
                success = False
                break

            lock_before = con.general_battle_config.lock_team_enable

            if index == 1 and not self.ensure_retreat_four(con):
                success = False
                break

            if index != 1 and self.check_medal_is_frog(frog, medal, index):
                # 呱太需要临时取消阵容锁定，战斗结束后恢复用户原配置。
                con.general_battle_config.lock_team_enable = False

            if not self.fire(index):
                # 没有成功进入战斗则重新检查票数和盘面。
                continue

            last_battle = self.run_general_battle(con.general_battle_config)
            real_attack_count += 1

            if lock_before:
                con.general_battle_config.lock_team_enable = lock_before

            if self.reward_detect_click(False):
                logger.info('Rewards of three wins')

            if not last_battle:
                logger.info('Battle lost before three wins, continue with other targets')

        self.goto_page(page_exploration)
        self.set_next_run(task='RealmRaid', success=success, finish=True)
        raise TaskEnd

    # ----------------------------------------------------------------------------------------------------------------------
    # 2023.7.21 改版个人突破
    def ensure_lock(self, lock_team_enable: bool):
        """
        确保锁定阵容
        :param lock_team_enable:
        :return:
        """
        if lock_team_enable:
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear_then_click(self.I_UNLOCK_2, interval=1):
                    continue
                if self.appear(self.I_LOCK_2, threshold=0.9):
                    break
                if self.appear(self.I_LOCK, threshold=0.9):
                    break
            logger.info(f'Click {self.I_UNLOCK.name}')
        else:
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_LOCK, interval=1):
                    continue
                if self.appear_then_click(self.I_LOCK_2, interval=1):
                    continue
                if self.appear(self.I_UNLOCK_2, threshold=0.9):
                    break
                if self.appear(self.I_UNLOCK, threshold=0.9):
                    break
            logger.info(f'Click {self.I_LOCK.name}')

    def is_frog(self, screenshot: bool=True) -> bool:
        """
        判断是不是呱太活动
        :return:
        """
        if screenshot:
            self.screenshot()
        if self.appear(self.I_FROG_MEDAL):
            return True
        return False

    def check_ticket(self, base: int=0) -> bool:
        """
        检查是不是有票， 检查这个票是否大于等于基准
        :param base:
        :return:
        """
        if base < 0 or base > 30:
            logger.warning(f'It is not a valid base {base}')
            base = 0
        self.wait_until_appear(self.I_BACK_RED)
        self.screenshot()
        cu, res, total = self.O_NUMBER.ocr(self.device.image)

        if total == 0:
            self.reward_detect_click(True)
            # 增加出现聊天框遮挡，处理奖励之后，重新识别票数
            cu, res, total = self.O_NUMBER.ocr(self.device.image)
        if cu == 0 and cu + res == total:
            logger.warning(f'Execute raid failed, no ticket')
            return False
        elif cu + res == total and cu < base:
            logger.warning(f'Execute raid failed, ticket is not enough')
            return False
        return True

    @cached_property
    def order_medal(self) -> ImageGrid:
        order_attack = self.config.realm_raid.raid_config.order_attack
        support_number = [0, 1, 2, 3, 4, 5]
        match = {
            0: self.I_MEDAL_0,
            1: self.I_MEDAL_1,
            2: self.I_MEDAL_2,
            3: self.I_MEDAL_3,
            4: self.I_MEDAL_4,
            5: self.I_MEDAL_5,
        }
        order = order_attack.replace(' ', '').replace('\n', '')
        order = re.split(r'>', order)
        order = [int(i) for i in order]
        order = [i for i in order if i in support_number]

        images = []
        for i in order:
            images.append(match[i])
        return ImageGrid(images)

    @cached_property
    def partition(self) -> list[RuleClick]:
        return [self.C_PARTITION_1, self.C_PARTITION_2, self.C_PARTITION_3, self.C_PARTITION_4, self.C_PARTITION_5,
                self.C_PARTITION_6, self.C_PARTITION_7, self.C_PARTITION_8, self.C_PARTITION_9]

    def find_one(self, screenshot: bool=True, exclude_positions: set[int] | None=None) -> tuple:
        """
        找到一个可以打的，并且检查一下是不是这一个的是第几个的
        我们约定次序是：从左到右 上到下
        1 2 3
        4 5 6
        7 8 9
        :return: 返回的第一个参数是一个RuleImage, 第二个参数是位置信息
        如果没有找到，返回None, None
        """
        if screenshot:
            self.screenshot()
        image = self.device.image
        if exclude_positions:
            image = image.copy()
            for position in exclude_positions:
                if position < 1 or position > len(self.partition):
                    continue
                x, y, width, height = self.partition[position - 1].roi_back
                image[y:y + height, x:x + width, ...] = 0

        target = self.order_medal.find_anyone(image)
        if target:
            center = target.front_center()
            for i, click in enumerate(self.partition):
                x1, x2, y1, y2 = click.roi_front[0], click.roi_front[0] + click.roi_front[2], \
                                 click.roi_front[1], click.roi_front[1] + click.roi_front[3]
                if x1 < center[0] < x2 and y1 < center[1] < y2:
                    logger.info(f'Find one medal [{target}], order is {i + 1}')
                    return target, i + 1

        return None, None

    def check_medal_is_frog(self, is_activity: False, target: RuleImage, order: int) -> bool:
        """
        检查这个是不是呱太，为此之前你还需要判断是不是 处于呱太活动的
        :param target:
        :param is_activity: 如果不是呱太活动，那么就不需要检查了
        :param order:
        :return:
        """
        if not is_activity:
            return False
        # 好像呱太的位置是只有 789这三个
        if order < 7:
            return False
        # 有时候四星可能和五星的混一起
        if target != self.I_MEDAL_5 and target != self.I_MEDAL_4:
            return False
        match_ocr = {
            1: self.O_FROG_1,
            2: self.O_FROG_2,
            3: self.O_FROG_3,
            4: self.O_FROG_4,
            5: self.O_FROG_5,
            6: self.O_FROG_6,
            7: self.O_FROG_7,
            8: self.O_FROG_8,
            9: self.O_FROG_9,
        }
        target_ocr = match_ocr[order]
        self.screenshot()
        if target_ocr.ocr(self.device.image) == 20:
            logger.info(f'Find frog medal [{target}]')
            return True
        return False

    def get_failed_positions(self, screenshot: bool=True) -> list[int]:
        """
        识别当前九宫格中带失败标记的位置。
        :return: 位置编号列表，范围为1到9
        """
        if screenshot:
            self.screenshot()

        positions = []
        for index, roi in enumerate(self.false_roi, start=1):
            self.false_image.roi_back = roi
            if self.appear(self.false_image):
                positions.append(index)
        return positions

    def has_three_wins(self, screenshot: bool=True) -> bool:
        """
        通过游戏界面的三胜标记判断本轮是否进入全清阶段。

        不能使用本次任务的战斗计数，因为脚本可能从已经有胜场的盘面开始执行。
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_RR_THREE, threshold=0.8)

    def is_first_position_finished(self, screenshot: bool=True) -> bool:
        """
        判断左上角第一个目标是否已经成功或失败。

        位置1只要完成过正式挑战，就视为本轮已经执行过退四；任务运行期间不存在
        “退四后中断”的状态，因此不需要额外持久化退四进度。
        """
        if screenshot:
            self.screenshot()
        if self.appear(self.I_RAID_SUCCESS):
            return True

        self.false_image.roi_back = self.false_roi[0]
        return self.appear(self.false_image)

    def retreat_four_at_first(self, config: RealmRaid) -> bool:
        """
        固定在左上角第一个目标主动退出四次，不把这些退出计入真实挑战次数。
        """
        logger.info('Execute retreat four at position 1')
        quick_exit_config = self.build_quick_exit_config(config.general_battle_config)

        for count in range(1, 5):
            if not self.fire(1):
                logger.warning(f'Retreat four failed to enter battle, count={count}')
                return False

            self.run_general_battle(config=quick_exit_config)

            # 快速退出后关闭结果界面，确认重新回到个人突破页面再执行下一次。
            if not self.ui_click_until_appear_or_timeout(
                    random_click(), self.I_RR_PERSON, interval=0.8, timeout=10):
                logger.warning(f'Retreat four failed to return to realm raid page, count={count}')
                return False

        logger.info('Retreat four completed')
        return True

    def ensure_retreat_four(self, config: RealmRaid) -> bool:
        """
        开启退四时，确保当前这一轮在刷新或正式挑战位置1前已经完成退四。
        """
        if not config.raid_config.exit_four or self.round_retreat_done:
            return True

        self.screenshot()
        if self.is_first_position_finished(False):
            logger.info('Position 1 is finished, treat retreat four as completed')
            self.round_retreat_done = True
            return True

        # 主动退出不消耗突破券，但进入战斗仍要求账号当前至少持有一张券。
        if not self.check_ticket():
            logger.warning('Retreat four cannot start without a realm raid pass')
            return False
        if not self.retreat_four_at_first(config):
            return False

        self.round_retreat_done = True
        return True

    def refresh_round(self, config: RealmRaid) -> bool:
        """
        结束当前轮：三胜或无其他目标时先确保完成退四，再刷新盘面。
        """
        if not self.ensure_retreat_four(config):
            return False
        if not self.check_refresh():
            return False

        self.round_retreat_done = False
        return True

    def process_three_win_stage(self, config: RealmRaid) -> str:
        """
        处理三胜后的盘面。

        退四后，若位置1之外没有失败目标，则正式挑战位置1并继续全清；
        若其他位置存在失败目标，则尝试刷新，无法刷新时结束任务。

        :return: attack_first、continue、refreshed 或 stop
        """
        if not self.ensure_retreat_four(config):
            return 'stop'

        failed_positions = self.get_failed_positions()
        failed_positions_outside_first = [
            position for position in failed_positions if position != 1
        ]
        if failed_positions_outside_first:
            logger.info(
                f'Failed positions outside position 1: {failed_positions_outside_first}, '
                'try to refresh current round'
            )
            return 'refreshed' if self.refresh_round(config) else 'stop'

        if not self.is_first_position_finished(False):
            logger.info('No failed position outside position 1, attack position 1 and continue clearing')
            return 'attack_first'

        logger.info('No failed position outside position 1, continue clearing current round')
        return 'continue'

    def reward_detect_click(self, screenshot: bool=True) -> bool:
        """
        检测是否出现 每三次就有奖励的界面, 有就领取
        :return:
        """
        if screenshot:
            self.screenshot()
        # 由于更改识别顺序，退出战斗之后，需要先等待回到个人突破界面，即识别到红色退出按钮，再进行奖励判断
        self.wait_until_appear(self.I_BACK_RED)
        self.ui_click_until_disappear(self.I_SOUL_RAID, interval=1.2)
        text = self.O_TEXT.ocr(self.device.image)
        # 识别突破卷区域，如果识别到了且其中含有文字，即有聊天框遮挡则进入循环，等待三胜奖励出现并点击，循环退出条件为识别到票（即*/*的形式）
        if text != "" and re.search(r'[\u4e00-\u9fff]', text):
            while 1:
                self.screenshot()
                result = self.O_TEXT.ocr(self.device.image)
                if not re.search(r'[\u4e00-\u9fff]', result) and re.search(r'(\d+)/(\d+)', result):
                    return True
                if self.appear_then_click(self.I_SOUL_RAID, interval=1.5):
                    continue
        return False

    def check_refresh(self, screenshot: bool=True) -> bool:
        """
        检查是否出现了刷新的按钮
        如果可以刷新就刷新，返回True
        如果在CD中，就返回False
        :return:
        """
        if screenshot:
            self.screenshot()
        if not self.appear(self.I_FRESH):
            logger.info(f'No find refresh button and it is in CD')
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_FRESH_ENSURE):
                break
            if self.appear_then_click(self.I_FRESH, interval=1):
                continue
        while 1:
            self.screenshot()
            if not self.appear(self.I_FRESH_ENSURE):
                return True
            if self.appear_then_click(self.I_FRESH_ENSURE, interval=1):
                continue
        return False

    def fire(self, order: int) -> bool:
        """
        挑战
        :param order:  第几个
        :return: 是否点击进攻成功
        """
        click = self.partition[order - 1]
        self.wait_until_appear(self.I_RR_PERSON)
        self.device.click_record_clear()
        while True:
            self.screenshot()
            if not self.appear(self.I_RR_PERSON):
                logger.info(f'Click fire {order} success')
                return True
            if self.appear_then_click(self.I_FIRE, interval=1):
                continue
            if self.click(click, interval=2):
                continue

    @cached_property
    def false_roi(self) -> list:
        width = 86
        height = 64
        x1 = 386
        x2 = 714
        x3 = 1047
        y1 = 143
        y2 = 277
        y3 = 414
        return [
            [x1, y1, width, height],  # 左上角
            [x2, y1, width, height],
            [x3, y1, width, height],
            [x1, y2, width, height],  # 左中
            [x2, y2, width, height],
            [x3, y2, width, height],
            [x1, y3, width, height],  # 左下
            [x2, y3, width, height],
            [x3, y3, width, height],
        ]

    @cached_property
    def false_image(self):
        return RuleImage(roi_front=(0, 0, 63, 32),
                         roi_back=(0, 0, 100, 100),
                         threshold=0.8,
                         method="Template matching",
                         file="./tasks/RyouToppa/dev/loser_sign_1.png")


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device
    config = Config('zhu-1-mine')
    device = Device(config)
    t = ScriptTask(config, device)

    t.run()
