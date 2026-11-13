from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from module.exception import TaskEnd
from module.ocr.ppocr import TextSystem
from tasks.Exploration import page as pages
from tasks.Exploration.base import BaseExploration
from tasks.Exploration.config import ExplorationConfig, Scrolls


@pytest.fixture(scope='module')
def ocr_model():
    # 使用本地模型回放真实字形，不依赖运行中的 OCR 服务。
    return TextSystem(ort_providers=['CPUExecutionProvider'])


@pytest.mark.parametrize('filename,current,threshold', [
    ('tickets_zero.png', 0, 6),
    ('tickets_full.png', 30, 20),
])
def test_ticket_ocr_controls_raid_handoff_for_zero_and_full_tickets(
    monkeypatch, ocr_model, filename, current, threshold,
):
    rule = BaseExploration.O_REALM_RAID_NUMBER1
    monkeypatch.setattr(rule, 'model', ocr_model)
    sample = cv2.imread(str(Path(__file__).parent / 'fixtures' / filename))
    assert sample is not None
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[14:42, 924:1000] = cv2.cvtColor(sample, cv2.COLOR_BGR2RGB)

    assert rule.ocr(image) == (current, 30 - current, 30)

    task = object.__new__(BaseExploration)
    task.device = SimpleNamespace(image=image)
    task.goto_page = Mock()
    task.set_next_run = Mock()
    scrolls = Scrolls(
        scrolls_enable=True, scrolls_threshold=threshold,
        scrolls_cd=timedelta(minutes=10),
    )

    if current < threshold:
        task.activate_realm_raid(scrolls, ExplorationConfig(), pages.page_exp_entrance)
        task.goto_page.assert_not_called()
        task.set_next_run.assert_not_called()
    else:
        with pytest.raises(TaskEnd):
            task.activate_realm_raid(scrolls, ExplorationConfig(), pages.page_exp_entrance)
        assert any(
            call.kwargs.get('task') == 'RealmRaid'
            for call in task.set_next_run.call_args_list
        )
