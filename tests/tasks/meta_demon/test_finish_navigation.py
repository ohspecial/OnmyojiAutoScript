import pickle
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from module.exception import TaskEnd
from module.image.runtime import ImageRuntime
from tasks.GameUi.default_pages import page_main
from tasks.GameUi.page_definition import Page
from tasks.GameUi.session import NavigatorSession
from tasks.MetaDemon.boss_battle import BossBattle


@pytest.fixture
def expired_frame_task(monkeypatch):
    clock = {'now': 100.0}
    monkeypatch.setattr('module.image.runtime.time.time', lambda: clock['now'])
    runtime = ImageRuntime(settings={
        'frame_cache_expire_seconds': 10,
        'cleanup_interval_seconds': 3600,
        'worker_count': 1,
    })
    try:
        task = object.__new__(BossBattle)
        task.config = SimpleNamespace()
        task.device = SimpleNamespace(image=np.zeros((8, 8, 3), dtype=np.uint8))

        def screenshot():
            frame = runtime.register_frame(pickle.dumps(task.device.image), 'assistant')
            task.device.image_frame_id = frame['frame_id']
            return task.device.image

        task.screenshot = Mock(side_effect=screenshot)
        task.screenshot()
        old_frame = task.device.image_frame_id
        task.screenshot.reset_mock()
        recognized_frames = []

        def recognize_home(current_task):
            frame_id = current_task.device.image_frame_id
            runtime.get_frame_info(frame_id)
            recognized_frames.append(frame_id)
            return True

        home = Page(recognize_home, key=page_main.key, register=False)
        task.navigator = NavigatorSession(
            task_category='meta_demon', current_page=home, pages={home.key: home},
        )
        # 模拟等待上供端超过缓存 TTL；使用真实缓存淘汰，不连接游戏或 RPC 服务。
        clock['now'] += 30
        with pytest.raises(KeyError, match='Unknown frame id'):
            runtime.get_frame_info(old_frame)
        yield task, old_frame, recognized_frames
    finally:
        runtime.shutdown()


def test_finishing_after_long_assistance_wait_refreshes_before_page_recognition(expired_frame_task):
    task, old_frame, recognized_frames = expired_frame_task

    with pytest.raises(TaskEnd):
        task.finish_task()

    assert task.screenshot.called
    assert recognized_frames
    assert old_frame not in recognized_frames
    assert task.navigator.current_page.key == page_main.key


def test_deferred_courtyard_return_does_not_use_the_expired_frame(expired_frame_task):
    task, _, recognized_frames = expired_frame_task
    task.config.defer_task_courtyard_return = True

    with pytest.raises(TaskEnd):
        task.finish_task()

    task.screenshot.assert_not_called()
    assert recognized_frames == []
