from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.config.config_model import ConfigModel
from tasks.MetaDemon.assistance import GhostOffering
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType, MetaDemon, OfferingOrder, OfferingStar


@pytest.mark.parametrize('star,ascending', [
    (OfferingStar.FOUR_PLUS, (4, 5, 6)),
    (OfferingStar.FIVE_PLUS, (5, 6)),
    (OfferingStar.SIX, (6,)),
])
@pytest.mark.parametrize('order', list(OfferingOrder))
def test_offering_order_round_trips_and_reaches_actual_summoning(star, ascending, order):
    conf = MetaDemon(assistance_config={'offering_star': star, 'offering_order': order})
    conf = MetaDemon.model_validate_json(conf.model_dump_json())
    expected = ascending if order == OfferingOrder.ASCENDING else ascending[::-1]
    task = object.__new__(BossBattle)
    task.conf = conf
    task.start_time = datetime.now()
    task.limit_time = timedelta(minutes=5)
    task.limit_count = 10
    task.total_count = 0
    task.State = SimpleNamespace(done=False)
    task.appear = Mock(side_effect=lambda rule: rule is task.I_MD_SUMMON_BOSS)
    task.check_and_switch_ticket = Mock(return_value=True)
    offering = GhostOffering(task, Mock())

    assert offering.tick()
    assert offering.tick()
    task.check_and_switch_ticket.assert_called_once_with(sequence=expected)


def test_legacy_profile_keeps_six_star_offering_and_exposes_new_controls():
    conf = MetaDemon(assistance_config={'role': '上供', 'friend_names': '好友'})
    assert conf.assistance_config.offering_sequence == (BossType.SIX_STARS,)
    assert conf.assistance_config.offering_order == OfferingOrder.ASCENDING
    payload = ConfigModel.script_task(SimpleNamespace(meta_demon=conf), 'MetaDemon')
    fields = {row['name']: row for row in payload['assistance_config']}
    assert fields['offering_order']['enumEnum'] == ['顺序', '倒序']
    assert fields['offering_star']['default'] == '六星'


@pytest.mark.parametrize('minimum,current,allowed', [
    (OfferingStar.FOUR_PLUS, BossType.FOUR_STARS, True),
    (OfferingStar.FIVE_PLUS, BossType.FIVE_STARS, True),
    (OfferingStar.SIX, BossType.FOUR_STARS, False),
])
def test_active_boss_is_shared_only_within_selected_star_range(minimum, current, allowed):
    task = object.__new__(BossBattle)
    task.conf = MetaDemon(assistance_config={'offering_star': minimum})
    task.cur_boss_type = current
    task._boss_generation = 1
    task.appear = Mock(side_effect=lambda rule: rule is task.I_MD_FIRE)
    offering = GhostOffering(task, Mock())
    offering.share = Mock(return_value=True)

    assert offering.tick()
    assert offering.share.called is allowed
