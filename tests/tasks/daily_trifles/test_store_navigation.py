from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import tasks.DailyTrifles.script_task as daily
from module.exception import GamePageUnknownError
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.DailyTrifles.config import DailyTrifles
from tasks.DailyTrifles.page import page_store_gift_room
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import page_main, page_mall, page_mall_recommend
from tasks.GameUi.registry import PageRegistry
from tasks.GameUi.session import NavigatorSession


def make_task(**store_options):
    task = object.__new__(daily.ScriptTask)
    task.config = SimpleNamespace(daily_trifles=DailyTrifles(
        trifles_config={"store_sign": True, **store_options},
    ))
    task.goto_page = Mock()
    task.screenshot = Mock()
    task.appear_then_click = Mock(return_value=False)
    task.appear = Mock(return_value=False)
    return task


@pytest.mark.parametrize("start", [page_main, page_mall_recommend])
def test_sign_navigation_uses_gift_entrance_without_returning_to_mall(start):
    task = make_task()
    PageRegistry.load_all_pages()
    task.navigator = NavigatorSession(task_category="daily_trifles")
    task.navigator.bootstrap(PageRegistry.all())

    path = task._build_path(task.navigator.resolve_page(start),
                            task.navigator.resolve_page(page_store_gift_room))

    actions = [edge.action for edge in path]
    expected = [DailyTriflesAssets.I_ROOM_GIFT]
    if start == page_main:
        expected.insert(0, GameUiAssets.I_MAIN_GOTO_MALL)
    assert actions == expected
    assert all(edge.destination != page_mall for edge in path)


def test_sign_only_goes_directly_to_gift_room(monkeypatch):
    task = make_task()
    monkeypatch.setattr(daily, "sleep", lambda _: None)

    task.run_store()

    assert task.goto_page.call_args_list == [call(page_store_gift_room), call(page_main)]


def test_failed_gift_navigation_leaves_sign_pending():
    task = make_task()
    recorded_time = task.config.daily_trifles.done_record.store_sign_dt
    task.goto_page.side_effect = GamePageUnknownError("gift room unavailable")

    with pytest.raises(GamePageUnknownError):
        task.run_store_sign()

    assert task.config.daily_trifles.done_record.store_sign_dt == recorded_time
    assert not task.config.daily_trifles.today_is_done("store_sign")


def test_sushi_purchase_keeps_its_mall_entry():
    task = make_task(store_sign=False, buy_sushi_count=1)
    task.run_buy_sushi = Mock()
    actions = Mock()
    actions.attach_mock(task.goto_page, "goto")
    actions.attach_mock(task.run_buy_sushi, "buy")

    task.run_store()

    assert actions.mock_calls == [call.goto(page_mall, confirm_wait=3),
                                  call.buy(), call.goto(page_main)]
