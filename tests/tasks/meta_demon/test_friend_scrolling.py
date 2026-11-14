from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.MetaDemon.assistance import GhostOffering
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.config import MetaDemon


@pytest.fixture
def offering(monkeypatch):
    task = SimpleNamespace(
        conf=MetaDemon(assistance_config={'friend_names': 'Target'}),
        start_time=datetime.now(), limit_time=timedelta(minutes=5),
        total_count=0, limit_count=10, State=SimpleNamespace(done=False),
        device=SimpleNamespace(press_and_drag=Mock()),
        S_MD_SWIPE_FRIEND_UP=MetaDemonAssets.S_MD_SWIPE_FRIEND_UP,
        I_MD_INVITE_FRIENDS=object(), screenshot=Mock(), appear=Mock(return_value=True),
        swipe=Mock(),
    )
    offering = GhostOffering(task)
    offering.selected_count = Mock(return_value=0)
    offering.select_friend = Mock(return_value=True)
    monkeypatch.setattr('tasks.MetaDemon.assistance.time.sleep', Mock())
    return offering


def test_drag_is_short_and_slow_and_waits_before_next_capture(offering, monkeypatch):
    events = []
    task = offering.task
    task.device.press_and_drag.side_effect = lambda *a, **kw: events.append('drag')
    task.screenshot.side_effect = lambda: events.append('capture')
    wait = Mock(side_effect=lambda seconds: events.append('settle'))
    monkeypatch.setattr('tasks.MetaDemon.assistance.time.sleep', wait)

    assert offering.scroll_friends()
    task.screenshot()

    assert events == ['drag', 'settle', 'capture']
    start, end = task.device.press_and_drag.call_args.args
    assert start[0] == end[0]
    assert 10 < start[1] - end[1] <= 40
    assert task.device.press_and_drag.call_args.kwargs['swipe_duration'] >= 0.5
    assert wait.call_args.args[0] >= 1.0
    task.swipe.assert_not_called()

    assert offering.scroll_friends(to_top=True)
    start, end = task.device.press_and_drag.call_args.args
    assert 10 < end[1] - start[1] <= 40


def test_reaching_top_tolerates_alternating_ocr_omissions(offering):
    full = {'Alice': [(440, 200, 80, 20)], 'Bob': [(740, 200, 50, 20)],
            '60': [(440, 230, 20, 20)], 'Carol': [(440, 400, 80, 20)]}
    partial = {name: full[name] for name in ('Alice', 'Bob')}
    offering.friend_rows = Mock(side_effect=[full, partial, full])

    assert offering.list_to_top()

    assert offering.task.device.press_and_drag.call_count == 2


def test_same_names_still_moving_are_not_a_list_boundary():
    before = {'Alice': [(440, 200, 80, 20)], 'Bob': [(740, 300, 50, 20)]}
    after = {'Alice': [(440, 160, 80, 20)], 'Bob': [(740, 260, 50, 20)]}

    assert not GhostOffering.friend_rows_unchanged(before, after)
    assert not GhostOffering.friend_rows_unchanged({}, {})
    assert not GhostOffering.friend_rows_unchanged(before, {'Carol': [(440, 200, 80, 20)]})


def test_offscreen_friend_is_found_despite_ocr_omissions_at_top(offering):
    state = {'page': 0, 'reads': 0}
    pages = [
        {'Alice': [(440, 200, 80, 20)], 'Bob': [(740, 300, 50, 20)]},
        {'Alice': [(440, 160, 80, 20)], 'Bob': [(740, 260, 50, 20)]},
        {'Bob': [(740, 220, 50, 20)], 'Target': [(440, 400, 80, 20)]},
    ]

    def drag(start, end, **kwargs):
        state['page'] = max(0, min(2, state['page'] + (1 if end[1] < start[1] else -1)))

    def read():
        state['reads'] += 1
        rows = dict(pages[state['page']])
        if state['reads'] % 2:
            rows['60'] = [(440, 230, 20, 20)]
        return rows

    offering.task.device.press_and_drag.side_effect = drag
    offering.friend_rows = Mock(side_effect=read)

    assert offering.select_friends()

    offering.select_friend.assert_called_once_with('Target', (440, 400, 80, 20))
    assert state['page'] == 2


def test_empty_ocr_never_counts_as_reaching_top(offering):
    offering.FRIEND_SCAN_LIMIT = 3
    offering.friend_rows = Mock(return_value={})

    assert not offering.list_to_top()


def test_missing_name_is_reported_only_after_scan_without_partial_selection(offering):
    offering.friend_rows = Mock(return_value={'SomeoneElse': [(440, 200, 80, 20)]})

    assert not offering.select_friends()

    offering.select_friend.assert_not_called()
    directions = [call.args[1][1] - call.args[0][1]
                  for call in offering.task.device.press_and_drag.call_args_list]
    assert any(delta > 0 for delta in directions)
    assert any(delta < 0 for delta in directions)


def test_visible_target_is_selected_without_scrolling(offering):
    offering.friend_rows = Mock(return_value={'Target': [(440, 200, 80, 20)]})

    assert offering.select_friends()

    offering.task.device.press_and_drag.assert_not_called()
    offering.select_friend.assert_called_once_with('Target', (440, 200, 80, 20))
