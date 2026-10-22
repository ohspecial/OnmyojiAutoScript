from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.Duel.script_task import ScriptTask


def make_task(counter):
    task = object.__new__(ScriptTask)
    task.device = SimpleNamespace(image=object())
    task.appear = Mock(return_value=False)
    task.I_DUEL_HONOR = SimpleNamespace(roi_front=[240, 641, 20, 20])
    task.O_D_HONOR = SimpleNamespace(
        roi=list(ScriptTask.O_D_HONOR.roi),
        ocr=Mock(return_value=counter),
    )
    return task


@pytest.mark.parametrize("icon_visible", [False, True])
def test_full_honor_uses_configured_region_even_if_old_icon_is_missing_or_moved(icon_visible):
    task = make_task((4400, 0, 4400))
    task.appear.return_value = icon_visible
    configured_roi = list(task.O_D_HONOR.roi)
    observed_rois = []

    def read_honor(image):
        observed_rois.append(list(task.O_D_HONOR.roi))
        return 4400, 0, 4400

    task.O_D_HONOR.ocr.side_effect = read_honor

    assert task.check_honor()

    task.O_D_HONOR.ocr.assert_called_once_with(task.device.image)
    assert observed_rois == [configured_roi]
    assert task.O_D_HONOR.roi == configured_roi


@pytest.mark.parametrize(
    "counter, expected",
    [
        ((4400, 0, 4400), True),
        ((5400, 0, 5400), True),
        ((4300, 100, 4400), False),
        ((0, 4400, 4400), False),
        ((0, 0, 0), False),
        ((4500, -100, 4400), False),
    ],
)
def test_only_valid_full_honor_stops_duel(counter, expected):
    task = make_task(counter)
    task.appear.return_value = True

    assert task.check_honor() is expected


@pytest.mark.parametrize("honor_full_exit", [True, False])
def test_full_honor_prevents_next_battle_only_when_enabled(honor_full_exit):
    task = make_task((4400, 0, 4400))
    task.start_time = datetime.now()
    task.limit_time = timedelta(minutes=30)
    task.get_and_update_cur_score = Mock(return_value=1800)
    task.is_celeb = False
    task.conf = SimpleNamespace(
        duel_config=SimpleNamespace(target_score=2400, honor_full_exit=honor_full_exit),
        duel_celeb_config=SimpleNamespace(celeb_battle=False),
    )

    assert task.can_start_duel() is (not honor_full_exit)

    if honor_full_exit:
        task.O_D_HONOR.ocr.assert_called_once_with(task.device.image)
    else:
        task.O_D_HONOR.ocr.assert_not_called()
