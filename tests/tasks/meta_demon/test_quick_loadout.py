"""租借阵容免装魂的快速上阵回归。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.Component.QuickLoadout import frame_loadout
from tasks.Component.QuickLoadout.config import FrameQuickLoadoutConfig


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
