from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from tasks.Exploration.base import BaseExploration
from tasks.Exploration import page as pages
from tasks.Exploration.script_task import ScriptTask


def make_task(current, refreshed=None):
    task = object.__new__(BaseExploration)
    task.need_exit = False
    task.wait_start_time = datetime.now() - timedelta(minutes=1)
    visible = current

    def screenshot():
        nonlocal visible
        visible = refreshed if refreshed is not None else current

    task.screenshot = Mock(side_effect=screenshot)
    task.appear = Mock(side_effect=lambda rule: rule in visible)
    task.click = Mock(return_value=True)
    return task


def test_exit_does_nothing_without_back_button():
    task = make_task({BaseExploration.I_E_SETTINGS_BUTTON})
    before = task.wait_start_time

    task.quit_exp_main()

    task.screenshot.assert_not_called()
    task.click.assert_not_called()
    assert not task.need_exit
    assert task.wait_start_time == before


@pytest.mark.parametrize(
    "refreshed",
    [set(), {BaseExploration.I_UI_BACK_YELLOW},
     {BaseExploration.I_UI_BACK_YELLOW, BaseExploration.I_E_EXPLORATION_CLICK,
      BaseExploration.I_E_SETTINGS_BUTTON}],
)
def test_exit_rechecks_frame_and_never_backs_out_of_chapter_entry(refreshed):
    task = make_task(
        {BaseExploration.I_UI_BACK_YELLOW, BaseExploration.I_E_SETTINGS_BUTTON},
        refreshed,
    )
    before = task.wait_start_time

    task.quit_exp_main()

    task.screenshot.assert_called_once()
    task.click.assert_not_called()
    assert not task.need_exit
    assert task.wait_start_time == before


@pytest.mark.parametrize(
    "marker",
    [BaseExploration.I_E_SETTINGS_BUTTON, BaseExploration.I_E_AUTO_ROTATE_ON,
     BaseExploration.I_E_AUTO_ROTATE_OFF],
)
def test_exit_accepts_each_exploration_scene_marker(marker):
    task = make_task({BaseExploration.I_UI_BACK_YELLOW, marker})
    before = task.wait_start_time

    task.quit_exp_main()

    task.click.assert_called_once_with(task.I_UI_BACK_YELLOW, interval=3.5)
    assert task.need_exit
    assert task.wait_start_time > before


def test_click_interval_does_not_claim_exit_or_reset_teammate_wait_time():
    task = make_task({BaseExploration.I_UI_BACK_YELLOW, BaseExploration.I_E_SETTINGS_BUTTON})
    task.click.return_value = False
    before = task.wait_start_time

    task.quit_exp_main()

    assert not task.need_exit
    assert task.wait_start_time == before


def test_navigation_exit_uses_same_guard_after_scene_changes_to_entry():
    task = make_task(
        {BaseExploration.I_UI_BACK_YELLOW, BaseExploration.I_E_SETTINGS_BUTTON},
        {BaseExploration.I_UI_BACK_YELLOW, BaseExploration.I_E_EXPLORATION_CLICK},
    )
    transition = next(
        edge for edge in pages.page_exp_main.transitions
        if edge.destination == pages.page_exp_exit
    )

    assert not transition.action(task)
    task.click.assert_not_called()


@pytest.mark.parametrize("need_exit", [False, True])
def test_exit_dialog_respects_exit_request(need_exit):
    task = object.__new__(ScriptTask)
    task.need_exit = need_exit
    task.appear_then_click = Mock(return_value=True)

    task.run_on_exp_exit()

    target = task.I_E_EXIT_CONFIRM if need_exit else task.I_E_EXIT_CANCEL
    task.appear_then_click.assert_called_once_with(target, interval=0.8)
