from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.AutoStory.script_task import ScriptTask as StoryTask, _StoryFinished
from tasks.Exploration.config import ExplorationLevel, UserStatus
from tasks.ExplorationFight.config import ExplorationFight, ExplorationFightConfig
from tasks.ExplorationFight.script_task import ScriptTask as ChapterTask
from tasks.GameUi.game_ui import GameUi


def test_story_loading_frames_never_trigger_courtyard_completion(monkeypatch):
    task = object.__new__(StoryTask)
    frames = iter([task.I_LOADING_1, task.I_LOADING_2, task.I_STORY_BACK])
    visible = None

    def screenshot(self):
        nonlocal visible
        visible = next(frames)
        return visible

    monkeypatch.setattr(GameUi, 'screenshot', screenshot)
    monkeypatch.setattr('tasks.AutoStory.script_task.time.sleep', lambda seconds: None)
    task.appear = lambda rule: rule is visible
    task._story_monitor_enabled = False
    task._check_story_finished = Mock()
    assert task.screenshot() is task.I_STORY_BACK
    task._check_story_finished.assert_not_called()


def test_courtyard_dialogue_keeps_story_active_until_dialogue_disappears(monkeypatch):
    task = object.__new__(StoryTask)
    monkeypatch.setattr('tasks.AutoStory.script_task.time.monotonic', lambda: 10)
    markers = [task.I_CHECK_MAIN, task.I_STORY_CHAT_1]
    task.appear = lambda rule: any(rule is marker for marker in markers)
    task._story_last_check = 0
    task._check_story_finished()
    markers.pop()
    task._story_last_check = 0
    with pytest.raises(_StoryFinished):
        task._check_story_finished()


def test_discovery_mode_clamps_chapters_and_exposes_only_supported_choices():
    conf = ExplorationFight(exploration_fight_config={
        'start_chapter': '第二十七章', 'end_chapter': '第二十八章', 'discover_monsters': True,
    })
    settings = conf.exploration_fight_config
    assert settings.chapters == [ExplorationLevel.EXPLORATION_18]
    assert conf.settings_options['exploration_fight_config']['end_chapter'] == ['第十八章']
    regular = ExplorationFightConfig(start_chapter='第二十七章', end_chapter='第二十八章')
    assert regular.chapters == [ExplorationLevel.EXPLORATION_27, ExplorationLevel.EXPLORATION_28]


@pytest.mark.parametrize('difficulty,role', [('简单', UserStatus.ALONE), ('困难', UserStatus.LEADER)])
def test_chapter_runner_adapts_local_difficulty_and_invitation_configuration(difficulty, role):
    conf = ExplorationFight(exploration_fight_config={'difficulty': difficulty},
                            invite_config={'friend_list': '好友'})
    task = object.__new__(ChapterTask)
    task.config = SimpleNamespace(model=SimpleNamespace(exploration_fight=conf))
    config = task._config
    assert config.exploration_config.difficulty == difficulty
    assert config.exploration_config.user_status == role
    assert config.invite_config.friend_list_v == ['好友']
    assert not config.scrolls.scrolls_enable
