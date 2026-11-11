"""超鬼王移植的配置兼容、真实协同通道和素材回归。"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

from module.cooperation import Cooperation
from module.config.config_model import ConfigModel
from module.config.config_manual import ConfigManual
from module.config.config_menu import ConfigMenu
from module.exception import ScriptError
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.assistance import AssistanceLink, GhostAssistant
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import BossType, MetaDemon
from tasks.MetaDemon.ticket_stars import recognize_ticket_stars
from tasks.MetaDemon.synthesis import parse_synthesis_material_level
from tasks.MetaDemonTicket.config import MetaDemonTicket
from tasks.MetaDemonTicket.ticket_farming import run_ticket_farming


def test_new_task_is_registered_disabled_and_template_matches():
    model = ConfigModel()
    assert not model.meta_demon_ticket.scheduler.enable
    assert 'MetaDemonTicket' in ConfigMenu().menu['Activity Task']
    assert 'MetaDemonTicket' in ConfigManual.SCHEDULER_PRIORITY
    template = json.loads(Path('config/template.json').read_text(encoding='utf-8'))
    assert template['meta_demon'] == model.meta_demon.model_dump(mode='json')
    assert template['meta_demon_ticket'] == model.meta_demon_ticket.model_dump(mode='json')


def test_old_configs_migrate_without_changing_the_input_or_enabling_new_modes():
    legacy = {'meta_demon': {'scheduler': {'enable': True},
        'meta_demon_config': {'powerful_list': '5'},
        'switch_soul': {'enable': True, 'one_star': '2,3', 'two_stars': '4,1',
                        'six_stars': '高星组,六星阵容', 'enable_one_star_preset': True}}}
    before = json.dumps(legacy, ensure_ascii=False, sort_keys=True)
    model = ConfigModel(**legacy)
    assert json.dumps(legacy, ensure_ascii=False, sort_keys=True) == before
    assert model.meta_demon.switch_soul_config.switch_for('low_star').switch_group_team == '2,3'
    assert model.meta_demon.low_star_battle_conf.preset_enable
    assert model.meta_demon.switch_soul_config.switch_for('high_star').team_name == '六星阵容'
    assert model.meta_demon.meta_demon_config.high_star_powerful_enable
    assert not model.meta_demon.general_config.high_star_quick_loadout_enable
    assert not model.meta_demon_ticket.scheduler.enable


def test_existing_independent_ticket_settings_survive_legacy_migration():
    model = ConfigModel(meta_demon={'scheduler': {'enable': True},
            'meta_demon_config': {'mode': ['门票刷取：探索绘卷']}},
        meta_demon_ticket={'scheduler': {'enable': False},
                          'general_config': {'awake_layer': '玖层', 'limit_time': '00:12:00'}})
    assert model.meta_demon_ticket.general_config.awake_layer.value == '玖层'
    assert not model.meta_demon_ticket.scheduler.enable
    assert not model.meta_demon.scheduler.enable


def test_transient_miss_of_requested_ticket_does_not_end_with_another_star_visible(monkeypatch):
    task = object.__new__(BossBattle)
    task.conf = MetaDemon()
    task.State = SimpleNamespace(done=False)
    task.cur_boss_type = None
    task.current_count = 0
    state = {'frame': 0, 'selected': False, 'summoned': False, 'clock': 0}
    task.screenshot = Mock(side_effect=lambda: state.update(frame=state['frame'] + 1))
    task.I_MD_CHECK_SELECTED = SimpleNamespace(roi_front=(365, 315, 4, 4))
    task.appear = lambda rule: ((rule is task.I_MD_FIRE and state['summoned'])
        or rule is task.I_MD_GET_BOSS or (rule is task.I_MD_CHECK_SELECTED and state['selected']))
    task.ticket_matches_star = lambda rule, star: (star == BossType.SIX_STARS
        or (star == BossType.ONE_STAR and state['frame'] > 1))
    task.click = lambda *args, **kwargs: state.update(selected=True)
    task.appear_then_click = lambda *args, **kwargs: state.update(summoned=True) or True
    def now():
        state['clock'] += 0.1
        return state['clock']
    monkeypatch.setattr('tasks.MetaDemon.boss_battle.time.monotonic', now)
    assert task.check_and_switch_ticket(sequence=(BossType.ONE_STAR,))
    assert task.screenshot.call_count > 1
    assert task.cur_boss_type == BossType.ONE_STAR
    assert not task.State.done


@pytest.mark.parametrize('star,name', enumerate(
    ('ONE_STAR', 'TWO_STARS', 'THREE_STARS', 'FOUR_STARS', 'FIVE_STARS', 'SIX_STARS'), 1))
def test_each_real_ticket_template_has_the_expected_star_count(star, name):
    ticket = getattr(MetaDemonAssets, 'I_MD_' + name)
    card = np.array(Image.open(ticket.file).convert('RGB'))
    assert recognize_ticket_stars(card, (0, 0, card.shape[1], card.shape[0])) == star


@pytest.mark.parametrize('title,material', [('合成二星裂变之眼', 1), ('合成六星裂变之眼', 5),
    (' 合成 三 星 裂变之眼 ', 2), ('合成一星裂变之眼', None), ('六星', None)])
def test_synthesis_confirms_material_star_instead_of_product_star(title, material):
    assert parse_synthesis_material_level(title) == material


def save_profile(root, name, task, settings):
    folder = root / 'config'
    folder.mkdir(exist_ok=True)
    (folder / (name + '.json')).write_text(json.dumps({task: settings.model_dump(mode='json')},
        ensure_ascii=False), encoding='utf-8')


def assistance_task(root, name, role, peer):
    conf = MetaDemon(scheduler={'enable': True}, meta_demon_config={'mode': ['鬼王协助']},
                    assistance_config={'role': role, 'cooperation_script': peer, 'friend_names': '好友'})
    save_profile(root, name, 'meta_demon', conf)
    runtime = Cooperation(name, root=root)
    runtime.publish('MetaDemon')
    task = SimpleNamespace(conf=conf, config=SimpleNamespace(config_name=name, cooperation_runtime=runtime),
        start_time=datetime.now(), limit_time=timedelta(minutes=1))
    return task, runtime


def test_assistance_screenshot_and_settlement_handshake_uses_same_session(tmp_path):
    feed, feed_runtime = assistance_task(tmp_path, 'feed', '上供', 'fight')
    fight, fight_runtime = assistance_task(tmp_path, 'fight', '协助', '')
    offer_link, fight_link = AssistanceLink(feed), AssistanceLink(fight)
    assert fight_link.peer == 'feed'
    assert feed_runtime.validate('MetaDemon', 'fight')
    offer_link.publish('first-portrait')
    first = fight_link.target()
    assert first[2] == 'first-portrait'
    fight_link.confirm(first)
    assert offer_link.confirmed()
    fight_link.confirm(first, settled=True)
    assert offer_link.peer_settled()
    offer_link.publish('second-portrait')
    assert fight_link.target()[0] != first[0]
    assert not offer_link.confirmed()
    offer_link.publish()
    assert fight_link.target() is None
    fight_runtime.publish('Chess')
    assert not offer_link.peer_in_task()


def test_offering_does_not_wake_a_busy_assistant(tmp_path):
    feed, runtime = assistance_task(tmp_path, 'feed', '上供', 'fight')
    _, peer = assistance_task(tmp_path, 'fight', '协助', 'feed')
    peer.publish('Chess')
    assert runtime.prepare(feed.config, 'MetaDemon', 'fight', defer=False) is False
    assert peer.requested() == []


def test_ticket_pair_uses_matching_modes_and_fresh_completion(tmp_path):
    for name, role, peer in (('leader', 'leader', 'member'), ('member', 'member', 'leader')):
        save_profile(tmp_path, name, 'meta_demon_ticket', MetaDemonTicket(scheduler={'enable': True},
            general_config={'user_status': role}, invite_config={'cooperation_script': peer}))
    leader = Cooperation('leader', root=tmp_path)
    member = Cooperation('member', root=tmp_path)
    assert leader.matches_meta_demon_tickets('member')
    assert leader.validate('MetaDemonTicket', 'member')
    since = leader.begin_completion_phase('MetaDemonTicket', 'member')
    member.notify_task_completion('MetaDemonTicket', 'leader', 'tickets_full')
    assert leader.peer_task_completion('MetaDemonTicket', 'member', since) == 'tickets_full'
    save_profile(tmp_path, 'member', 'meta_demon_ticket', MetaDemonTicket(scheduler={'enable': True},
        general_config={'user_status': 'member', 'mode': '门票刷取：探索'},
        invite_config={'cooperation_script': 'leader'}))
    assert not leader.matches_meta_demon_tickets('member')
    with pytest.raises(ScriptError):
        leader.validate('MetaDemonTicket', 'member')


def test_configured_pair_without_runtime_does_not_fall_back_to_solo_precheck():
    owner = SimpleNamespace(config=SimpleNamespace(meta_demon_ticket=MetaDemonTicket(
        general_config={'user_status': 'member'}, invite_config={'cooperation_script': 'leader'})),
        goto_page=Mock())
    assert run_ticket_farming(owner, owner.config.meta_demon_ticket.general_config.mode) is False
    owner.goto_page.assert_not_called()


def test_assistant_reports_settlement_only_for_the_active_target():
    link = Mock()
    target = ('session', 1, 'portrait')
    link.target.return_value = target
    task = SimpleNamespace(appear=Mock(return_value=True), I_MD_SETTLING=object(),
        S_MD_SWIPE_UP=SimpleNamespace(roi_front=(1, 1, 2, 2), roi_back=(1, 3, 2, 2)))
    assistant = GhostAssistant(task, link)
    assert assistant.observe_settlement(target)
    assert assistant.observe_settlement(target)
    link.confirm.assert_called_once_with(target, settled=True)
