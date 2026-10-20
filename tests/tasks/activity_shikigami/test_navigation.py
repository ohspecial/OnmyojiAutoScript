from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import numpy as np

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
    task._map_ticket_counts = {}
    task._count_map = {"pass": 0, "ap": 0, "ap100": 0}
    task._capture_map_tickets = Mock()
    task.screenshot = Mock()
    task.goto_page = Mock()
    task.appear = Mock(return_value=False)
    task.ocr_appear = Mock(return_value=False)
    task.ocr_appear_click = Mock(return_value=False)
    task.appear_then_click = Mock(return_value=False)
    task.click = Mock(return_value=True)
    return task


def test_switching_challenge_types_returns_through_activity_map():
    task = make_task()
    original_recognizer = pages.page_act_pass.recognizer
    task.before_run()
    pass_page = task.navigator.resolve_page(pages.page_act_pass)
    ap_page = task.navigator.resolve_page(pages.page_act_ap)
    home = task.navigator.resolve_page(pages.page_act_map)

    path = task._build_path(pass_page, ap_page)
    assert [edge.destination for edge in path] == [home, ap_page]
    assert path[0].action == task._return_to_activity_map
    assert path[1].action == task._enter_ap_challenge
    reverse = task._build_path(ap_page, pass_page)
    assert [edge.destination for edge in reverse] == [home, pass_page]
    assert reverse[1].action == task._enter_pass_challenge
    assert pages.page_act_pass.recognizer is original_recognizer
    task.goto_page.assert_called_once_with(pages.page_act_map)


def test_activity_home_opens_map_before_entering_challenge():
    task = make_task()
    task.before_run()
    home = task.navigator.resolve_page(pages.page_act)
    map_page = task.navigator.resolve_page(pages.page_act_map)
    pass_page = task.navigator.resolve_page(pages.page_act_pass)

    path = task._build_path(home, pass_page)
    assert [edge.destination for edge in path] == [map_page, pass_page]
    assert path[0].action == task.O_ENTER_MAP
    reverse = task._build_path(pass_page, task.navigator.resolve_page(pages.page_main))
    assert [edge.destination for edge in reverse] == [map_page, home, pages.page_main]
    assert reverse[1].action == task.I_UI_BACK_CIRCLE


@pytest.mark.parametrize("arrived", [True, False])
def test_map_transition_closes_report_with_shared_button_even_if_title_is_hidden(arrived):
    task = make_task()
    original_hooks = (
        tuple(pages.page_act_map.on_enter_success),
        tuple(pages.page_act_map.on_enter_failure),
    )
    task.before_run()
    task.maybe_screenshot = Mock()
    task.ocr_appear_click = Mock(return_value=True)
    task.appear_then_click = Mock(return_value=True)
    task._wait_for_destination = Mock(return_value=arrived)
    map_page = task.navigator.resolve_page(pages.page_act_map)
    task._detect_current_page_with_fallback = Mock(return_value=map_page)
    transition = task._build_path(
        task.navigator.resolve_page(pages.page_act), map_page,
    )[0]

    assert task._execute_transition(transition) is arrived

    task.appear_then_click.assert_called_once_with(task.I_UI_BACK_RED, interval=0.6)
    assert tuple(pages.page_act_map.on_enter_success) == original_hooks[0]
    assert tuple(pages.page_act_map.on_enter_failure) == original_hooks[1]


@pytest.mark.parametrize("other_mode", ["pass", "ap"])
def test_ap100_switches_through_map_without_changing_global_pages(other_mode):
    task = make_task()
    original_recognizer = pages.page_act_ap100.recognizer
    original_transitions = tuple(pages.page_act_ap100.transitions)
    original_hooks = tuple(pages.page_act_ap100.on_enter_failure)
    task.before_run()
    home = task.navigator.resolve_page(pages.page_act_map)
    ap100_page = task.navigator.resolve_page(pages.page_act_ap100)
    other_page = task.navigator.resolve_page(getattr(pages, f"page_act_{other_mode}"))

    path = task._build_path(other_page, ap100_page)
    assert [edge.destination for edge in path] == [home, ap100_page]
    assert path[0].action == task._return_to_activity_map
    assert path[1].action == task._enter_ap100_challenge
    reverse = task._build_path(ap100_page, other_page)
    assert [edge.destination for edge in reverse] == [home, other_page]
    assert reverse[0].action == task._return_to_activity_map
    assert reverse[1].action == getattr(task, f"_enter_{other_mode}_challenge")
    assert pages.page_act_ap100.recognizer is original_recognizer
    assert tuple(pages.page_act_ap100.transitions) == original_transitions
    assert tuple(pages.page_act_ap100.on_enter_failure) == original_hooks
    assert not ap100_page.on_enter_failure


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


def test_ap100_is_recognized_only_after_actual_entry():
    task = make_task()
    task.before_run()
    task.__dict__["conf"] = SimpleNamespace(
        general_climb=SimpleNamespace(run_sequence_v=["ap", "ap100"])
    )
    task.run_idx = 1
    task._challenge_type = "ap"
    task.appear = lambda rule: rule in (task.I_CHECK_BATTLE_MAIN, task.I_CLIMB_MODE_AP100)
    ap100_page = task.navigator.resolve_page(pages.page_act_ap100)
    ap_page = task.navigator.resolve_page(pages.page_act_ap)

    assert task.climb_type == "ap100"
    assert not task.match_page_once(ap100_page)
    task._challenge_type = "ap100"
    assert task.match_page_once(ap100_page)
    assert not task.match_page_once(ap_page)
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act_pass))


def test_ap100_challenge_is_a_battle_exit():
    task = make_task()
    task.appear = lambda rule: rule == task.I_CLIMB_MODE_AP100

    assert task._exit_matcher().evaluate(task)


@pytest.mark.parametrize("entry_name", ["O_MAP_TITLE", "O_ENTER_PASS", "O_ENTER_AP", "O_ENTER_AP100"])
def test_activity_map_recognizes_trial_entries_without_matching_home(entry_name):
    task = make_task()
    original_recognizer = pages.page_act_map.recognizer
    task.before_run()
    task.ocr_appear = lambda rule: rule == getattr(task, entry_name)

    assert task.match_page_once(task.navigator.resolve_page(pages.page_act_map))
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act))
    assert pages.page_act_map.recognizer is original_recognizer


def test_activity_home_recognizes_third_entry_without_matching_map():
    task = make_task()
    task.before_run()
    task.ocr_appear = lambda rule: rule == task.O_ENTER_MAP

    assert task.match_page_once(task.navigator.resolve_page(pages.page_act))
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act_map))


@pytest.mark.parametrize(
    "mode, recognizer_name",
    [("pass", "I_CHECK_BATTLE_MAIN"), ("ap", "I_CHECK_BATTLE_MAIN"),
     ("ap100", "I_CLIMB_MODE_AP100")],
)
def test_challenge_is_not_home_even_when_ocr_falsely_matches(mode, recognizer_name):
    task = make_task()
    task.before_run()
    task._challenge_type = mode
    task.appear = lambda rule: rule == getattr(task, recognizer_name)
    task.ocr_appear = Mock(return_value=True)

    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act))
    assert not task.match_page_once(task.navigator.resolve_page(pages.page_act_map))
    assert task.match_page_once(task.navigator.resolve_page(getattr(pages, f"page_act_{mode}")))


@pytest.mark.parametrize(
    "text, expected",
    [("古迹演武", True), ("那伽遗迹中开人", False), ("遗迹", False), ("", False)],
)
def test_ap_entry_ocr_requires_complete_label(monkeypatch, text, expected):
    task = make_task()
    task.before_run()
    task.device = SimpleNamespace(image=np.zeros((720, 1280, 3), dtype=np.uint8))
    model = Mock()
    model.detect_and_ocr.return_value = [SimpleNamespace(
        ocr_text=text, score=0.99,
        box=np.array([[20, 20], [125, 20], [125, 48], [20, 48]]),
    )] if text else []
    monkeypatch.setitem(task.O_ENTER_AP.__dict__, "model", model)

    assert bool(normal.NormalClimbAct.ocr_appear(task, task.O_ENTER_AP)) is expected


@pytest.mark.parametrize("entry_name", ["O_ENTER_PASS", "O_ENTER_AP", "O_ENTER_AP100"])
@pytest.mark.parametrize("top", [20, 260, 540])
def test_map_entry_click_follows_label_when_its_position_changes(monkeypatch, entry_name, top):
    task = make_task()
    task.before_run()
    del task.ocr_appear
    task.device = SimpleNamespace(
        image=np.zeros((720, 1280, 3), dtype=np.uint8), click=Mock(),
    )
    rule = getattr(task, entry_name)
    other = next(
        getattr(task, name).keyword
        for name in ("O_ENTER_PASS", "O_ENTER_AP", "O_ENTER_AP100")
        if name != entry_name
    )
    model = Mock()
    model.detect_and_ocr.return_value = [
        SimpleNamespace(
            ocr_text=other, score=0.99,
            box=np.array([[30, 100], [135, 100], [135, 128], [30, 128]]),
        ),
        SimpleNamespace(
            ocr_text=rule.keyword, score=0.99,
            box=np.array([[30, top], [135, top], [135, top + 28], [30, top + 28]]),
        ),
    ]
    monkeypatch.setitem(rule.__dict__, "model", model)

    assert normal.NormalClimbAct.ocr_appear_click(task, rule)
    assert rule.area == (30, 80 + top, 105, 28)
    click = task.device.click.call_args.kwargs
    assert 30 <= click["x"] <= 135
    assert 80 + top <= click["y"] <= 108 + top
    assert click["control_name"] == rule.name


def test_pass_entry_handles_confirmation_map_and_occupation_rewards(monkeypatch):
    task = make_task()
    reward = {task.I_UI_BACK_RED, task.I_PASS_4}
    frames = iter([
        {task.I_UI_CONFIRM},
        {task.O_MAP_TITLE, task.O_ENTER_PASS},
        {task.O_MAP_TITLE, task.O_ENTER_PASS, task.I_PASS_1},  # 没有选关标志时不能点击占领入口。
        {task.O_MAP_TITLE, task.O_ENTER_PASS, task.I_PASS_3, task.I_PASS_1},
        {task.O_MAP_TITLE, task.O_ENTER_PASS, task.I_PASS_3, task.I_PASS_2},
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
    task.ocr_appear = lambda rule: rule in visible
    task.ocr_appear_click = appear_then_click
    task.appear_then_click = appear_then_click
    monkeypatch.setattr(normal, "sleep", Mock())

    assert task._enter_pass_challenge()
    assert task._challenge_type == "pass"
    assert clicked == [task.I_UI_CONFIRM, task.O_ENTER_PASS, task.I_PASS_1, task.I_PASS_2]
    task._capture_map_tickets.assert_called_once_with("pass")
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


def test_ap_entry_uses_second_map_entry():
    task = make_task()
    task._challenge_type = "pass"
    frames = iter([
        {task.O_ENTER_AP},
        {task.I_CHECK_BATTLE_MAIN},
    ])
    visible = set()
    clicked = []

    def screenshot():
        nonlocal visible
        assert task._challenge_type == "pass"
        visible = next(frames)

    def click_visible(rule, interval):
        if rule not in visible:
            return False
        clicked.append(rule)
        return True

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.ocr_appear = lambda rule: rule in visible
    task.ocr_appear_click = click_visible
    task.appear_then_click = click_visible

    assert task._enter_ap_challenge()
    assert task._challenge_type == "ap"
    assert clicked == [task.O_ENTER_AP]
    task._capture_map_tickets.assert_called_once_with("ap")


def test_ap_entry_timeout_preserves_actual_mode(monkeypatch):
    task = make_task()
    task._challenge_type = "pass"
    timer = Mock()
    timer.start.return_value = timer
    timer.reached.side_effect = [False, True]
    monkeypatch.setattr(normal, "Timer", Mock(return_value=timer))

    assert not task._enter_ap_challenge()
    assert task._challenge_type == "pass"
    task.screenshot.assert_called_once()


def test_ap_entry_resumes_from_challenge_without_clicking_entry():
    task = make_task()
    task.appear = lambda rule: rule == task.I_CHECK_BATTLE_MAIN

    assert task._enter_ap_challenge()
    assert task._challenge_type == "ap"
    task.ocr_appear_click.assert_not_called()
    task.appear_then_click.assert_not_called()


@pytest.mark.parametrize("entered", [True, False])
def test_ap100_entry_updates_mode_only_after_reaching_challenge(monkeypatch, entered):
    task = make_task()
    task._challenge_type = "ap"
    task.appear = lambda rule: entered and rule == task.I_CLIMB_MODE_AP100
    timer = Mock()
    timer.start.return_value = timer
    timer.reached.side_effect = [False, True]
    monkeypatch.setattr(normal, "Timer", Mock(return_value=timer))

    assert task._enter_ap100_challenge() is entered
    assert task._challenge_type == ("ap100" if entered else "ap")
    task.ocr_appear_click.assert_not_called()


@pytest.mark.parametrize("mode", ["pass", "ap", "ap100"])
def test_challenge_entry_closes_report_before_reading_tickets_or_selecting_entry(mode):
    task = make_task()
    entry = getattr(task, f"O_ENTER_{mode.upper()}")
    challenge = task.I_CLIMB_MODE_AP100 if mode == "ap100" else task.I_CHECK_BATTLE_MAIN
    frames = iter([
        {task.O_MAP_TITLE, task.I_UI_BACK_RED},
        {task.O_MAP_TITLE, task.I_UI_BACK_RED},
        {task.O_MAP_TITLE, entry},
        {challenge},
    ])
    visible = set()
    clicked = []
    close_attempts = 0

    def screenshot():
        nonlocal visible
        visible = next(frames)

    def click_visible(rule, interval):
        nonlocal close_attempts
        if rule not in visible:
            return False
        if rule == task.I_UI_BACK_RED:
            close_attempts += 1
            if close_attempts == 1:
                return False  # 关闭按钮仍在点击间隔内时，不能操作被遮挡的地图。
        clicked.append(rule)
        return True

    def capture_tickets(current_mode):
        assert task.I_UI_BACK_RED not in visible
        assert current_mode == mode

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.ocr_appear = lambda rule: rule in visible
    task.appear_then_click = click_visible
    task.ocr_appear_click = click_visible
    task._capture_map_tickets = Mock(side_effect=capture_tickets)

    assert getattr(task, f"_enter_{mode}_challenge")()
    assert task._challenge_type == mode
    assert close_attempts == 2
    assert clicked == [task.I_UI_BACK_RED, entry]
    task._capture_map_tickets.assert_called_once_with(mode)


def test_return_handles_all_three_back_buttons():
    task = make_task()
    task._challenge_type = "ap"
    frames = iter([
        {task.I_UI_BACK_CIRCLE}, {task.I_UI_BACK_YELLOW},
        {task.I_UI_BACK_RED}, {task.O_MAP_TITLE},
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
    task.ocr_appear = lambda rule: rule in visible
    task.appear_then_click = appear_then_click

    assert task._return_to_activity_map()
    assert task._challenge_type is None
    assert clicked == [task.I_UI_BACK_CIRCLE, task.I_UI_BACK_YELLOW, task.I_UI_BACK_RED]


def test_return_closes_report_before_accepting_map_title():
    task = make_task()
    task._challenge_type = "ap"
    frames = iter([
        {task.O_MAP_TITLE, task.I_UI_BACK_RED, task.I_UI_BACK_CIRCLE},
        {task.O_MAP_TITLE, task.I_UI_BACK_CIRCLE},
    ])
    visible = set()
    clicked = []

    def screenshot():
        nonlocal visible
        visible = next(frames)

    def click_visible(rule, interval):
        if rule not in visible:
            return False
        clicked.append(rule)
        return True

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.ocr_appear = lambda rule: rule in visible
    task.appear_then_click = click_visible

    assert task._return_to_activity_map()
    assert task._challenge_type is None
    assert clicked == [task.I_UI_BACK_RED]


@pytest.mark.parametrize("entry_name", ["O_MAP_TITLE", "O_ENTER_PASS", "O_ENTER_AP", "O_ENTER_AP100"])
def test_return_stops_on_map_even_when_back_button_is_visible(entry_name):
    task = make_task()
    task._challenge_type = "ap100"
    task.ocr_appear = lambda rule: rule == getattr(task, entry_name)
    task.appear = lambda rule: rule == task.I_UI_BACK_CIRCLE

    assert task._return_to_activity_map()
    assert task._challenge_type is None
    task.appear_then_click.assert_not_called()


@pytest.mark.parametrize("recognizer_name", ["I_CHECK_BATTLE_MAIN", "I_CLIMB_MODE_AP100"])
def test_return_leaves_challenge_before_accepting_map_entry(recognizer_name):
    task = make_task()
    task._challenge_type = "ap"
    frames = iter([
        {getattr(task, recognizer_name), task.O_ENTER_AP, task.I_UI_BACK_YELLOW},
        {task.O_ENTER_AP},
    ])
    visible = set()
    clicked = []

    def screenshot():
        nonlocal visible
        visible = next(frames)

    def click_visible(rule, interval):
        if rule not in visible:
            return False
        clicked.append(rule)
        return True

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.ocr_appear = lambda rule: rule in visible
    task.appear_then_click = click_visible

    assert task._return_to_activity_map()
    assert task._challenge_type is None
    assert clicked == [task.I_UI_BACK_YELLOW]


def test_return_reenters_map_if_it_reaches_activity_home():
    task = make_task()
    task._challenge_type = "pass"
    frames = iter([{task.O_ENTER_MAP, task.I_UI_BACK_YELLOW}, {task.O_MAP_TITLE}])
    visible = set()

    def screenshot():
        nonlocal visible
        visible = next(frames)

    task.screenshot = screenshot
    task.appear = lambda rule: rule in visible
    task.ocr_appear = lambda rule: rule in visible

    assert task._return_to_activity_map()
    task.ocr_appear_click.assert_called_once_with(task.O_ENTER_MAP, interval=1.5)
    task.appear_then_click.assert_not_called()


def make_ticket_task(mode):
    task = make_task()
    del task._capture_map_tickets
    task.device = SimpleNamespace(image=np.zeros((720, 1280, 3), dtype=np.uint8))
    task.__dict__["conf"] = SimpleNamespace(
        general_climb=SimpleNamespace(run_sequence_v=[mode])
    )
    task.run_idx = 0
    return task


@pytest.mark.parametrize("mode", ["pass", "ap", "ap100"])
def test_map_ticket_read_retries_empty_result_instead_of_treating_it_as_zero(monkeypatch, mode):
    task = make_ticket_task(mode)
    rule = getattr(task, f"O_MAP_REMAIN_{mode.upper()}")
    read = Mock(side_effect=["", "10"])
    monkeypatch.setattr(rule, "ocr_single", read)

    task._capture_map_tickets(mode)

    assert task.check_tickets_enough()
    assert task._map_ticket_counts[mode] == (10, 0)
    assert read.call_count == 2
    task.screenshot.assert_called_once()


@pytest.mark.parametrize("mode", ["pass", "ap", "ap100"])
@pytest.mark.parametrize("text, enough", [("0", False), ("", True), ("abc", True)])
def test_map_ticket_read_distinguishes_zero_from_unreadable_result(monkeypatch, mode, text, enough):
    task = make_ticket_task(mode)
    # 重新进入副本时，不能沿用上次未能刷新成功的次数。
    task._map_ticket_counts[mode] = (0, 0)
    rule = getattr(task, f"O_MAP_REMAIN_{mode.upper()}")
    monkeypatch.setattr(rule, "ocr_single", Mock(return_value=text))

    task._capture_map_tickets(mode)

    assert task.check_tickets_enough() is enough
    assert (mode in task._map_ticket_counts) is (text == "0")


@pytest.mark.parametrize("mode", ["pass", "ap", "ap100"])
def test_map_ticket_snapshot_accounts_for_consumption_and_refreshes_on_reentry(monkeypatch, mode):
    task = make_ticket_task(mode)
    rule = getattr(task, f"O_MAP_REMAIN_{mode.upper()}")
    monkeypatch.setattr(rule, "ocr_single", Mock(side_effect=["2", "4"]))
    task.count_map[mode] = 5
    task._capture_map_tickets(mode)

    task.count_map[mode] = 6
    assert task.check_tickets_enough()
    task.count_map[mode] = 7
    assert not task.check_tickets_enough()

    task._capture_map_tickets(mode)
    assert task._map_ticket_counts[mode] == (4, 7)
    assert task.check_tickets_enough()


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
