"""租借阵容免装魂，以及快速上阵失败后的首领识别回归。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.Component.QuickLoadout import frame_loadout
from tasks.Component.QuickLoadout.config import FrameQuickLoadoutConfig
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType, MetaDemon


@pytest.fixture
def quick_task(monkeypatch):
    monkeypatch.setattr(frame_loadout, 'sleep', lambda _: None)
    task = object.__new__(frame_loadout.FrameQuickLoadout)
    task.device = SimpleNamespace(click=Mock())
    task.screenshot = Mock()
    task.click = Mock()
    task._open_quick_loadout = Mock(return_value=True)
    task._build_quick_loadout_layout = Mock(return_value=SimpleNamespace(
        panel=(496, 224, 553, 387), preset_select_x=795,
    ))
    task._select_group = Mock(return_value=True)
    task._select_preset_row = Mock(return_value=345)
    task._equip_quick_loadout_souls = Mock()
    task._quick_loadout_panel_visible = Mock(side_effect=[True, False])
    task._quick_loadout_fight = Mock(return_value=object())
    return task, SimpleNamespace(name='QUICK_LOADOUT_FRAME')


@pytest.mark.parametrize('group,skip,expect_equip', [
    ('队伍租借', False, False),
    (' 队伍租借 ', False, False),
    ('队伍租借', True, False),
    ('活动', False, True),
    ('活动', True, False),
])
def test_rental_deploys_without_equipping_souls_and_normal_group_respects_setting(
        quick_task, group, skip, expect_equip):
    task, frame = quick_task
    config = FrameQuickLoadoutConfig(enable=True, group_name=group, preset_name='目标阵容')

    assert task.run_quick_loadout(config, frame=frame, skip_equip_soul=skip)
    assert task._equip_quick_loadout_souls.call_count == int(expect_equip)
    task._select_group.assert_called_once()
    task._select_preset_row.assert_called_once()
    task.device.click.assert_called_once_with(795, 345, control_name='QUICK_LOADOUT_PRESET')
    task.click.assert_called_once_with(task._quick_loadout_fight.return_value)


def test_failed_selection_closes_obstructing_popup_even_when_panel_is_unrecognized(quick_task):
    task, frame = quick_task
    task._quick_loadout_panel_visible.side_effect = [False, False]
    config = FrameQuickLoadoutConfig(enable=True, group_name='队伍租借', preset_name='单体阵容')

    assert not task.run_quick_loadout(config, frame=frame)
    task.click.assert_called_once_with(frame_loadout.GeneralBattleAssets.C_RANDOM_LEFT, interval=1)
    task._quick_loadout_fight.assert_not_called()
    assert task._last_quick_loadout is None


@pytest.fixture
def boss_task():
    task = object.__new__(BossBattle)
    task.conf = MetaDemon(
        general_config={'high_star_quick_loadout_enable': True},
        quick_preset_config={
            'high_star_custom_preset_enable': True,
            'high_star_custom_preset': '单体:月读,雪御前;群体:ALL',
            'preset_groups': '单体,队伍租借,第4日单体通用阵容;群体,活动,群体通用',
        },
    )
    task.cur_boss_type = BossType.FIVE_STARS
    task._boss_generation = 1
    task._active_loadout_group = None
    task._quick_loadout_panel_visible = Mock(return_value=False)
    task._dismiss_quick_loadout = Mock(return_value=True)
    task._read_quick_loadout_stage_name = Mock(return_value='月读')
    task.run_quick_loadout = Mock(return_value=True)
    return task


def test_same_boss_retry_keeps_single_target_instead_of_reading_panel_text(boss_task):
    task = boss_task
    task._read_quick_loadout_stage_name.side_effect = ['月读', '队住']
    task.run_quick_loadout.side_effect = [False, True]

    assert not task.check_and_switch_soul()
    assert task.check_and_switch_soul()

    task._read_quick_loadout_stage_name.assert_called_once()
    assert [(call.args[0].group_name, call.args[0].preset_name)
            for call in task.run_quick_loadout.call_args_list] == [
        ('队伍租借', '第4日单体通用阵容'), ('队伍租借', '第4日单体通用阵容'),
    ]


def test_new_boss_reads_name_again_and_can_switch_back_to_normal_group(boss_task):
    task = boss_task
    task._read_quick_loadout_stage_name.side_effect = ['月读', '梦山白藏主']

    assert task.check_and_switch_soul()
    task._boss_generation += 1
    assert task.check_and_switch_soul()

    assert task._read_quick_loadout_stage_name.call_count == 2
    assert [call.args[0].group_name for call in task.run_quick_loadout.call_args_list] == [
        '队伍租借', '活动',
    ]


@pytest.mark.parametrize('closed', [True, False])
def test_existing_panel_must_close_before_first_boss_name_read(boss_task, closed):
    task = boss_task
    task._quick_loadout_panel_visible.return_value = True
    task._dismiss_quick_loadout.return_value = closed

    def read_name(rule):
        task._dismiss_quick_loadout.assert_called_once()
        return '月读'

    task._read_quick_loadout_stage_name.side_effect = read_name

    assert task.check_and_switch_soul() is closed
    task._dismiss_quick_loadout.assert_called_once()
    if not closed:
        task._read_quick_loadout_stage_name.assert_not_called()
        task.run_quick_loadout.assert_not_called()
