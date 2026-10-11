from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import tasks.ActivityShikigami.activities.normal as normal
import tasks.ActivityShikigami.page as pages
from tasks.GameUi.registry import PageRegistry
from tasks.GameUi.session import NavigatorSession


def make_task():
    PageRegistry.load_all_pages()
    task = object.__new__(normal.NormalClimbAct)
    task.navigator = NavigatorSession(task_category="activity_shikigami")
    task.navigator.bootstrap(PageRegistry.all())
    task._challenge_type = None
    task.screenshot = Mock()
    task.goto_page = Mock()
    task.appear = Mock(return_value=False)
    task.appear_then_click = Mock(return_value=False)
    task.click = Mock(return_value=True)
    return task


def test_switching_challenge_types_returns_through_activity_home():
    task = make_task()
    original_recognizer = pages.page_act_pass.recognizer
    task.before_run()
    pass_page = task.navigator.resolve_page(pages.page_act_pass)
    ap_page = task.navigator.resolve_page(pages.page_act_ap)
    home = task.navigator.resolve_page(pages.page_act)

    path = task._build_path(pass_page, ap_page)
    assert [edge.destination for edge in path] == [home, ap_page]
    assert path[0].action == task._return_to_activity
    assert path[1].action == task._enter_ap_challenge
    reverse = task._build_path(ap_page, pass_page)
    assert [edge.destination for edge in reverse] == [home, pass_page]
    assert reverse[1].action == task._enter_pass_challenge
    assert pages.page_act_pass.recognizer is original_recognizer
    task.goto_page.assert_called_once_with(pages.page_act)


def test_challenge_recognition_tracks_actual_entry_when_run_sequence_advances():
    task = make_task()
    task.before_run()
    task.__dict__["conf"] = SimpleNamespace(
        general_climb=SimpleNamespace(run_sequence_v=["pass", "ap"])
    )
    task._challenge_type = "pass"
    task.run_idx = 1
    task.appear = Mock(side_effect=lambda rule: rule == task.I_CHECK_BATTLE_MAIN)

    assert task.climb_type == "ap"
    assert task.match_page_once(task.navigator.resolve_page(pages.page_act_pass))
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act_ap))
    task._challenge_type = "ap"
    assert task.match_page_once(task.navigator.resolve_page(pages.page_act_ap))
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act_pass))


def test_pass_entry_handles_confirmation_map_and_occupation_rewards(monkeypatch):
    task = make_task()
    reward = {task.I_UI_BACK_RED, task.I_PASS_4}
    frames = iter([
        {task.I_UI_CONFIRM},
        {task.I_TO_BATTLE_MAIN_2},
        {task.I_PASS_1},  # 没有地图标志时不能点击占领入口。
        {task.I_PASS_3, task.I_PASS_1},
        {task.I_PASS_3, task.I_PASS_2},
        reward,
        *[reward] * 6,
        {task.I_CHECK_BATTLE_MAIN},
    ])
    visible = set()
    clicked = []

    def screenshot():
        nonlocal visible
        visible = next(frames)

    def appear_then_click(rule, interval):
        if rule not in visible:
            return False
        clicked.append(rule)
        return True

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.appear_then_click = appear_then_click
    monkeypatch.setattr(normal, "sleep", Mock())

    assert task._enter_pass_challenge()
    assert task._challenge_type == "pass"
    assert clicked == [task.I_UI_CONFIRM, task.I_TO_BATTLE_MAIN_2, task.I_PASS_1, task.I_PASS_2]
    assert [call.args[0] for call in task.click.call_args_list] == [
        task.C_PASS_5, task.C_PASS_6, task.C_PASS_7,
        task.C_PASS_8, task.C_PASS_9, task.C_PASS_5,
    ]


def test_pass_entry_resumes_from_challenge_without_reward_clicks():
    task = make_task()
    task.appear = lambda rule: rule == task.I_CHECK_BATTLE_MAIN

    assert task._enter_pass_challenge()
    assert task._challenge_type == "pass"
    task.click.assert_not_called()
    task.appear_then_click.assert_not_called()


@pytest.mark.parametrize("entered", [True, False])
def test_ap_entry_updates_mode_only_after_reaching_challenge(entered):
    task = make_task()
    task.ui_click = Mock(return_value=entered)

    assert task._enter_ap_challenge() is entered
    assert task._challenge_type == ("ap" if entered else None)
    task.ui_click.assert_called_once_with(
        task.I_TO_BATTLE_MAIN, stop=task.I_CHECK_BATTLE_MAIN,
        interval=1, timeout=30,
    )


def test_return_handles_all_three_back_buttons():
    task = make_task()
    task._challenge_type = "ap"
    frames = iter([
        {task.I_UI_BACK_CIRCLE}, {task.I_UI_BACK_YELLOW},
        {task.I_UI_BACK_RED}, {task.I_TO_BATTLE_MAIN},
    ])
    visible = set()
    clicked = []

    def screenshot():
        nonlocal visible
        visible = next(frames)

    def appear_then_click(rule, interval):
        if rule not in visible:
            return False
        clicked.append(rule)
        return True

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.appear_then_click = appear_then_click

    assert task._return_to_activity()
    assert task._challenge_type is None
    assert clicked == [task.I_UI_BACK_CIRCLE, task.I_UI_BACK_YELLOW, task.I_UI_BACK_RED]


@pytest.mark.parametrize("reached", [[True], [False, True]])
def test_pass_entry_times_out_without_claiming_challenge_success(monkeypatch, reached):
    task = make_task()
    task.appear = lambda rule: rule in (task.I_UI_BACK_RED, task.I_PASS_4)
    timer = Mock()
    timer.start.return_value = timer
    timer.reached.side_effect = reached
    monkeypatch.setattr(normal, "Timer", Mock(return_value=timer))

    assert not task._enter_pass_challenge()
    assert task._challenge_type is None
    task.click.assert_not_called()
