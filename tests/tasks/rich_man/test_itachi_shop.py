"""鼬乐礼盒购买的离线回归：所有截图、OCR 和点击均为替身。"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from module.config.config_model import ConfigModel
from module.exception import GameStuckError, TaskEnd
from tasks.Chess.assets import ChessAssets
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import ItachiCoinShop as Options, RichMan
from tasks.RichMan.itachi_shop import ItachiCoinShop
from tasks.RichMan.page import page_itachi_shop
from tasks.RichMan.script_task import ScriptTask
from tasks.GameUi.page import page_entertainment
from tasks.GameUi.registry import PageRegistry
from tasks.GameUi.session import NavigatorSession


def frame(*markers, coin=(600, 0, 600), cost=200):
    return SimpleNamespace(markers=markers, coin=coin, cost=cost)


def make_task(monkeypatch, frames):
    task = object.__new__(ItachiCoinShop)
    clock = SimpleNamespace(now=0.)
    monkeypatch.setattr('time.monotonic', lambda: clock.now)
    sequence = iter(frames)
    current = frame()
    task.device = SimpleNamespace(image=current)

    def screenshot():
        nonlocal current
        clock.now += .4
        current = next(sequence, current)
        task.device.image = current

    task.screenshot = Mock(side_effect=screenshot)
    task.appear = Mock(side_effect=lambda rule, **kw: any(rule is m for m in current.markers))
    task.click = Mock(return_value=True)
    task.appear_then_click = Mock(side_effect=lambda rule, **kw: task.click(rule) if task.appear(rule) else False)
    task.ui_reward_appear_click = Mock(return_value=True)
    task.goto_page = Mock(return_value=True)
    monkeypatch.setattr(task.O_ITACHI_COIN, 'ocr', Mock(side_effect=lambda image: image.coin))
    monkeypatch.setattr(task.O_ITACHI_BUY_COST, 'ocr', Mock(side_effect=lambda image: image.cost))
    return task


def test_old_config_and_template_keep_purchase_disabled():
    model = ConfigModel.model_validate({'rich_man': {'guild_store': {'skin_ticket': 8}}})
    assert model.rich_man.guild_store.skin_ticket == 8
    assert not model.rich_man.itachi_coin_shop.itachi_coin_buy_jade
    template = json.loads(Path('config/template.json').read_text(encoding='utf-8'))
    assert template['rich_man']['itachi_coin_shop'] == {'itachi_coin_buy_jade': False}


@pytest.mark.parametrize('options', [None, Options()])
def test_disabled_option_does_not_navigate_or_click(monkeypatch, options):
    task = make_task(monkeypatch, [])
    task.execute_itachi_coin_shop(options)
    task.goto_page.assert_not_called()
    task.screenshot.assert_not_called()
    task.click.assert_not_called()


def test_weekly_task_calls_shop_and_preserves_other_steps_and_schedule():
    task = object.__new__(ScriptTask)
    task.config = SimpleNamespace(rich_man=RichMan())
    methods = ['execute_tt', 'execute_shrine', 'execute_guild', 'execute_itachi_coin_shop',
               'execute_mall', 'set_next_run']
    actions = Mock()
    for name in methods:
        setattr(task, name, Mock())
        actions.attach_mock(getattr(task, name), name)
    with pytest.raises(TaskEnd):
        task.run()
    assert [event[0] for event in actions.mock_calls] == methods
    task.execute_itachi_coin_shop.assert_called_once_with(task.config.rich_man.itachi_coin_shop)
    task.set_next_run.assert_called_once_with(task='RichMan', success=True, finish=False)


def test_navigation_enters_and_leaves_itachi_shop():
    PageRegistry.load_all_pages()
    task = object.__new__(ScriptTask)
    task.navigator = NavigatorSession(task_category='rich_man')
    task.navigator.bootstrap(PageRegistry.all())
    source = task.navigator.resolve_page(page_entertainment)
    target = task.navigator.resolve_page(page_itachi_shop)
    path = task._build_path(source, target)
    assert len(path) == 1 and path[0].action is RichManAssets.I_ITACHI_SHOP_ENTRY
    assert len(task._build_path(target, source)) == 1


def test_successive_gifts_read_fresh_prices_and_stop_at_three(monkeypatch):
    # 四帧表示附属页关闭后已稳定一秒。每次礼盒均经历商店、购买框、奖励和扣币。
    frames = [frame()] * 4
    balance = 600
    for price in (100, 200, 300):
        dialog = frame(ItachiCoinShop.I_BUY_PLUS, coin=(balance, 600-balance, 600), cost=price)
        balance -= price
        shop = frame(RichManAssets.I_ITACHI_SHOP_CHECK, coin=(balance, 600-balance, 600))
        reward = frame(ItachiCoinShop.I_UI_REWARD)
        frames += [frame(RichManAssets.I_ITACHI_SHOP_CHECK), dialog, dialog,
                   reward, reward, shop, shop]
    task = make_task(monkeypatch, frames)
    task.execute_itachi_coin_shop(Options(itachi_coin_buy_jade=True))
    assert task.click.call_args_list == [call(task.C_ITACHI_GIFT), call(task.C_BUY_MORE)] * 3
    assert task.O_ITACHI_BUY_COST.ocr.call_count == 3
    assert task.O_ITACHI_COIN.ocr.call_count == 6
    assert task.goto_page.call_args_list == [call(page_entertainment), call(page_itachi_shop),
                                             call(page_entertainment)]


def test_overlay_must_close_and_remain_stable(monkeypatch):
    task = make_task(monkeypatch, [frame(ChessAssets.I_SKIP)] * 2 + [frame()] * 4)
    assert task._wait_entertainment_overlay_closed()
    assert task.screenshot.call_count == 6
    assert task.click.call_args_list == [call(ChessAssets.I_SKIP)] * 2


def test_stuck_overlay_never_enters_shop(monkeypatch):
    task = make_task(monkeypatch, [frame(ChessAssets.I_SKIP)])
    task.execute_itachi_coin_shop(Options(itachi_coin_buy_jade=True))
    task.goto_page.assert_called_once_with(page_entertainment)
    assert not any(c.args[0] is task.C_ITACHI_GIFT for c in task.click.call_args_list)


def test_missing_shop_marker_does_not_click_gift(monkeypatch):
    task = make_task(monkeypatch, [frame()])
    assert not task._open_front_gift_once()
    task.click.assert_not_called()


def test_sold_out_or_unresponsive_gift_is_clicked_only_once(monkeypatch):
    task = make_task(monkeypatch, [frame(RichManAssets.I_ITACHI_SHOP_CHECK)])
    assert not task._open_front_gift_once()
    task.click.assert_called_once_with(task.C_ITACHI_GIFT)


@pytest.mark.parametrize('coin,cost', [
    ((199, 401, 600), 200), ((0, 0, 0), 200), (None, 200),
    ((-1, 601, 600), 200), ((600, 0, 0), 200), ((600, 20, 600), 200),
    (('600', 0, 600), 200), ((True, 599, 600), 200),
    ((600, 0, 600), 0), ((600, 0, 600), None), ((600, 0, 600), True),
])
def test_insufficient_or_unverified_balance_and_price_never_confirm(monkeypatch, coin, cost):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS, coin=coin, cost=cost)])
    assert not task._buy_opened_gift()
    task.click.assert_not_called()


@pytest.mark.parametrize('markers', [(), (ItachiCoinShop.I_BUY_PLUS, ItachiCoinShop.I_BUY_RMB)])
def test_missing_or_wrong_currency_dialog_never_confirms(monkeypatch, markers):
    task = make_task(monkeypatch, [frame(*markers)])
    assert not task._buy_opened_gift()
    task.click.assert_not_called()


def test_return_to_shop_without_reward_does_not_count_as_success(monkeypatch):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS),
                                   frame(RichManAssets.I_ITACHI_SHOP_CHECK)])
    assert not task._buy_opened_gift()
    task.click.assert_called_once_with(task.C_BUY_MORE)
    assert task.O_ITACHI_COIN.ocr.call_count == 1


def test_stalled_confirmation_is_never_clicked_repeatedly(monkeypatch):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS)])
    assert not task._buy_opened_gift()
    task.click.assert_called_once_with(task.C_BUY_MORE)


@pytest.mark.parametrize('after,expected', [
    ((400, 200, 600), True), ((600, 0, 600), False),
    ((300, 300, 600), False), ((400, 300, 700), False), ((0, 0, 0), False),
])
def test_reward_requires_matching_coin_deduction(monkeypatch, after, expected):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS),
                                   frame(ItachiCoinShop.I_UI_REWARD),
                                   frame(), frame(coin=after)])
    assert task._buy_opened_gift() is expected
    task.click.assert_called_once_with(task.C_BUY_MORE)


def test_delayed_reward_is_accepted_within_return_grace(monkeypatch):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS),
                                   frame(), frame(), frame(ItachiCoinShop.I_UI_REWARD),
                                   frame(), frame(coin=(400, 200, 600))])
    assert task._buy_opened_gift()
    task.click.assert_called_once_with(task.C_BUY_MORE)


def test_stuck_reward_stops_before_buying_next_gift(monkeypatch):
    task = make_task(monkeypatch, [frame(ItachiCoinShop.I_BUY_PLUS),
                                   frame(ItachiCoinShop.I_UI_REWARD)])
    assert not task._buy_opened_gift()
    task.click.assert_called_once_with(task.C_BUY_MORE)
    assert task.O_ITACHI_COIN.ocr.call_count == 1


def test_purchase_failure_stops_whole_sequence(monkeypatch):
    task = make_task(monkeypatch, [])
    task._wait_entertainment_overlay_closed = Mock(return_value=True)
    task._open_front_gift_once = Mock(return_value=True)
    task._buy_opened_gift = Mock(return_value=False)
    task.execute_itachi_coin_shop(Options(itachi_coin_buy_jade=True))
    task._open_front_gift_once.assert_called_once_with()
    task._buy_opened_gift.assert_called_once_with()


def test_device_error_propagates_without_purchase(monkeypatch):
    task = make_task(monkeypatch, [])
    task.screenshot.side_effect = GameStuckError('offline')
    with pytest.raises(GameStuckError):
        task._open_front_gift_once()
    task.click.assert_not_called()
