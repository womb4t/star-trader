"""0.9.2: cargo cost follows the cargo, the trade log shows money in, money out and a running balance,
and Money / Reports compares a commander with the average.
Run with python3 -m unittest -v test_tradelog."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
import unittest.mock
from pathlib import Path
import json
import threading
import time
from unittest.mock import MagicMock
import star_trader as st
st.CHARTER_RANK = 0   # the Newcomer Charter's bonus and patrols are tested on their own (test_tradelog.CharterTests)
from save_server import Store, make_server
from save_sync import RemoteSave

FOOD, GOLD = 0, 8


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name)/'save.json'
        self.g = st.Game(None)
        self.p = self.g.p
        self.p.credits = 10000

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def buy(self, good, n, value=20):
        for _ in range(n): self.p.trade(good, True, value=value)

    def sell(self, good, value=11):
        self.p.trade(good, False, value=value)
        return self.p.trade_log[-1]['profit']


class CargoCostTests(Base):
    def test_scooped_cargo_after_losing_bought_cargo_is_pure_profit(self):
        """The reported bug: bought food was lost, then food from a pirate sold at a 'loss'."""
        self.buy(FOOD, 8, 20)
        self.g.recover_destroyed_pilot()
        self.p.credits = 100
        self.p.add_cargo(FOOD)          # canister from a dead pirate
        self.assertEqual(self.sell(FOOD, 11), 11)

    def test_seized_contraband_takes_its_cost(self):
        narcotics = st.ILLEGAL[0]
        self.buy(narcotics, 3, 50)
        self.p.clear_cargo(st.ILLEGAL)
        self.assertEqual(self.p.cargo_paid[narcotics], 0)
        self.p.add_cargo(narcotics)
        self.assertEqual(self.sell(narcotics, 40), 40)

    def test_partial_removal_keeps_average_cost(self):
        self.buy(GOLD, 4, 200)
        self.assertEqual(self.p.remove_cargo(GOLD, 1), 200)
        self.assertEqual(self.sell(GOLD, 250), 50)

    def test_scooped_cargo_lowers_average_cost(self):
        self.buy(FOOD, 1, 20)
        self.p.add_cargo(FOOD)
        self.assertEqual(self.sell(FOOD, 15), 5)   # average cost 10 a tonne

    def test_storage_carries_cost_both_ways(self):
        bay = self.p.storage[self.p.system]
        bay['owned'] = True
        self.buy(GOLD, 2, 200)
        self.g.d = MagicMock()
        self.g.selected = GOLD
        for _ in range(2): self.g.transfer_storage(True)
        self.assertEqual((self.p.cargo[GOLD], self.p.cargo_paid[GOLD], bay['paid'][GOLD]), (0, 0, 400))
        self.p.add_cargo(GOLD)           # free gold picked up meanwhile
        self.assertEqual(self.sell(GOLD, 250), 250)
        self.g.transfer_storage(False)
        self.assertEqual(self.sell(GOLD, 250), 50)

    def test_old_save_with_stale_cost_is_repaired(self):
        self.p.cargo[FOOD], self.p.cargo_paid[FOOD] = 0, 174
        self.p.add_new_commodities()
        self.assertEqual(self.p.cargo_paid[FOOD], 0)


class TradeLogTests(Base):
    def test_balance_recorded_after_each_trade(self):
        self.p.credits = 1000
        self.buy(GOLD, 1, 200)
        self.sell(GOLD, 250)
        self.assertEqual([e['balance'] for e in self.p.trade_log], [800, 1050])

    def test_columns_drawn_with_old_entries(self):
        self.p.credits = 1000
        self.buy(FOOD, 1, 20)
        self.sell(FOOD, 30)
        self.p.trade_log.insert(0, dict(time=1., system=0, side='sell', good=FOOD, price=9, unit='cr', profit=1))
        self.p.validate()
        g = self.g
        g.d = MagicMock()
        g.trades_page = 0
        g.draw_trades()
        lines = [c.args[2] for c in g.d.text.call_args_list]
        self.assertTrue(any('IN' in l and 'OUT' in l and 'BALANCE' in l for l in lines))
        self.assertTrue(any('In 39 cr, out 20 cr' in l for l in lines))
        sell = next(l for l in lines if ' SELL ' in l and '30 cr' in l)
        buy = next(l for l in lines if ' BUY ' in l)
        self.assertTrue(sell.rstrip().endswith('1,010 cr'))
        self.assertTrue(buy.rstrip().endswith('980 cr'))
        self.assertLessEqual(max(len(l) for l in lines if ' SELL ' in l or ' BUY ' in l), 92)


class LedgerTests(Base):
    def total(self): return self.p.ledger['total']

    def test_sales_and_costs_are_booked(self):
        self.buy(GOLD, 2, 200)
        self.sell(GOLD, 250)
        self.p.book('seconds', 3600)
        self.p.equipment = []
        self.p.buy_equipment(1)          # large cargo bay, 400
        self.p.fuel = 5; self.p.refuel()
        self.assertEqual(self.total()['trade'], 50)
        self.assertEqual(self.total()['equipment'], -400)
        self.assertLess(self.total()['running'], 0)
        today = self.p.ledger['days'][st.ledger_day()]
        self.assertEqual(today['trade'], 50)

    def test_destruction_counts_carried_credits_cargo_and_gear(self):
        self.p.credits = 300
        self.p.bank_balance = 1000
        self.buy(GOLD, 1, 200)            # credits now 100
        self.p.equipment = ['cargo', 'docking']
        self.p.missiles = 0
        self.g.recover_destroyed_pilot()
        # 100 carried + 200 cargo + 400 bay + 1,500 docking computer + 100 bank fee
        self.assertEqual(self.total()['destroyed'], -2300)
        self.assertEqual(self.total()['deaths'], 1)

    def test_fines_bounties_and_trips(self):
        self.p.fine = 120
        self.g.pay_fines()
        self.g.enemy_kind = 'pirate'
        self.g.enemy = [0., 0., 500., 1, 0.]
        self.g.destroy_enemy()
        self.g.launch()
        self.assertEqual(self.total()['fines'], -120)
        self.assertEqual(self.total()['bounty'], 35)
        self.assertEqual(self.total()['trips'], 1)

    def test_play_time_is_recorded(self):
        self.g.mode = 'market'
        for _ in range(12): self.g.update(1.)
        self.assertGreaterEqual(self.total()['seconds'], 10)

    def test_ledger_survives_save_and_load_and_old_saves_start_empty(self):
        self.p.book('trade', 75)
        self.p.save()
        loaded = st.Pilot(); self.assertTrue(loaded.load())
        self.assertEqual(loaded.ledger['total']['trade'], 75)
        data = json.loads(st.SAVE.read_text()); del data['ledger']; st.SAVE.write_text(json.dumps(data))
        old = st.Pilot(); self.assertTrue(old.load())
        self.assertEqual(old.ledger, dict(days={}, total={}))
        for bad in (dict(days={}, total={'credits': 5}), dict(days={'yesterday': {}}, total={}), dict(days={}, total={'trade': float('inf')})):
            self.assertFalse(st.valid_ledger(bad))

    def test_only_sixty_days_are_kept(self):
        for i in range(70):
            with unittest.mock.patch.object(st, 'ledger_day', return_value=time.strftime('%Y-%m-%d', time.localtime(1.7e9+i*86400))):
                self.p.book('trade', 1)
        self.assertEqual(len(self.p.ledger['days']), st.LEDGER_DAYS)
        self.assertEqual(self.total()['trade'], 70)

    def test_periods(self):
        days = {'2026-11-19': {'trade': 10}, '2026-11-14': {'trade': 5}, '2026-11-01': {'trade': 100}}
        ledger = dict(days=days, total={'trade': 115})
        self.assertEqual(st.ledger_period(ledger, 'today', '2026-11-19')['trade'], 10)
        self.assertEqual(st.ledger_period(ledger, 'week', '2026-11-19')['trade'], 15)
        self.assertEqual(st.ledger_period(ledger, 'all', '2026-11-19')['trade'], 115)


class ReportTests(Base):
    def ledger(self, net, seconds=3600, deaths=0):
        bucket = dict(trade=net, seconds=seconds, trips=4, deaths=deaths)
        return dict(days={'2026-11-19': bucket}, total=dict(bucket))

    def test_averages_need_three_commanders_who_played(self):
        two = [self.ledger(100), self.ledger(300), self.ledger(5000, seconds=60)]
        self.assertIsNone(st.report_averages(two, '2026-11-19')['week']['average'])
        self.assertEqual(st.report_averages(two, '2026-11-19')['week']['commanders'], 2)
        three = two+[self.ledger(500)]
        avg = st.report_averages(three, '2026-11-19')['week']
        self.assertEqual((avg['commanders'], avg['average']['net_hr']), (3, 300))

    def test_verdict_names_ship_losses_first(self):
        bucket = dict(trade=900, destroyed=-3100, deaths=1, seconds=7200, trips=6)
        lines = st.report_verdict(bucket, dict(net_hr=300))
        self.assertIn('Losing your ship cost 3,100 cr', lines[0])
        self.assertIn('losing', lines[-1])
        self.assertIn('above', ' '.join(st.report_verdict(dict(trade=2000, seconds=3600, trips=4), dict(net_hr=500))).replace('more than', 'above'))
        self.assertIn('makes 50 cr a trip', ' '.join(st.report_verdict(dict(trade=200, seconds=3600, trips=4))))
        self.assertEqual(st.report_verdict({}), ['Not enough play recorded in this period yet.'])

    def test_screen_opens_from_money_and_changes_period(self):
        g = self.g
        g.d = MagicMock()
        g.mode, g.money_return = 'money', 'flight'
        g.keyboard(ord('e'))
        self.assertEqual(g.mode, 'reports')
        g.keyboard(st.RIGHT)
        self.assertEqual(g.report_period, 2)
        g.p.book('trade', 120); g.p.book('seconds', 1800)
        g.report_averages = {'all': {'commanders': 2, 'average': None}}
        g.draw_reports()
        lines = [c.args[2] for c in g.d.text.call_args_list]
        self.assertTrue(any('ALL TIME' in l for l in lines))
        self.assertTrue(any('Trading profit' in l and '+120 cr' in l for l in lines))
        self.assertTrue(any('(2 so' in l or '2 so far' in l for l in lines))
        g.mouse_back()
        self.assertEqual(g.mode, 'money')


class ServerReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'p.sqlite3')
        for i,name in enumerate(('Kenton', 'Frank', 'Ada', 'Bo')):
            token = chr(ord('k')+i)*43
            self.store.create_player(name, token)
            (self.root/(name+'.token')).write_text(token)
            save = vars(st.Pilot()).copy()
            day = st.ledger_day()
            bucket = dict(trade=(i+1)*100, seconds=3600, trips=2)
            save['ledger'] = dict(days={day: bucket}, total=dict(bucket))
            self.store.write(token, 0, save)
        server = make_server(self.store, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), worker.join()))
        self.remote = RemoteSave('http://127.0.0.1:'+str(server.server_port), self.root/'Kenton.token', self.root/'Kenton')

    def tearDown(self): self.tmp.cleanup()

    def test_market_carries_only_averages(self):
        snap = self.remote.request(dict(trades=[], system=3), endpoint='/v1/market')
        week = snap['reports']['week']
        self.assertEqual(week['commanders'], 4)
        self.assertEqual(week['average']['net_hr'], 250)
        self.assertNotIn('Frank', json.dumps(snap['reports']))


class SellKitTests(Base):
    def index(self, key): return next(i for i,e in enumerate(st.EQUIPMENT) if e[0] == key)

    def test_buying_a_laser_explains_the_pulse_laser_is_kept(self):
        self.p.system = next(i for i,t in enumerate(st.TECH) if t >= 5)
        message = self.p.buy_equipment(self.index('mining'))
        self.assertIn('Pulse laser kept', message)
        self.assertEqual(self.p.laser, 'mining')

    def test_selling_kit_pays_half_and_resets_lasers(self):
        p = self.p
        p.equipment = ['mining', 'rear', 'beam', 'scoops']
        p.laser, p.rear_laser = 'mining', 'beam'
        p.credits = 0
        self.assertIn('sold for 400 cr', p.sell_equipment(self.index('mining')))
        self.assertEqual((p.laser, p.credits), ('pulse', 400))
        p.sell_equipment(self.index('rear'))
        self.assertEqual(p.rear_laser, 'pulse')
        p.sell_equipment(self.index('scoops'))
        self.assertEqual(p.equipment, ['beam'])
        self.assertEqual(p.ledger['total']['equipment'], 400+300+262)
        p.validate()

    def test_selling_a_laser_on_the_rear_mount(self):
        p = self.p
        p.equipment = ['rear', 'military']
        p.laser, p.rear_laser = 'pulse', 'military'
        p.sell_equipment(self.index('military'))
        self.assertEqual((p.rear_laser, p.equipment), ('pulse', ['rear']))
        p.validate()

    def test_cannot_sell_what_is_not_fitted_or_a_full_cargo_bay(self):
        p = self.p
        p.equipment = ['cargo']
        self.assertIn('not fitted', p.sell_equipment(self.index('docking')))
        p.cargo[0] = 25
        self.assertIn('Unload to 20 t', p.sell_equipment(self.index('cargo')))
        p.cargo[0] = 20
        self.assertIn('sold', p.sell_equipment(self.index('cargo')))
        p.missiles = 0
        self.assertIn('No homing missiles', p.sell_equipment(self.index('missile')))
        p.missiles = 2
        p.sell_equipment(self.index('missile'))
        self.assertEqual(p.missiles, 1)

    def test_s_sells_in_outfitting(self):
        g = self.g
        g.d = MagicMock()
        g.p.equipment = ['scoops']
        g.mode = 'outfit'; g.outfit_return = 'market'
        g.shop_selected = self.index('scoops')
        g.keyboard(ord('s'))
        self.assertEqual(g.p.equipment, [])
        self.assertIn('sold for 262 cr', g.message)


class CrymtoTests(Base):
    FEUDAL, ANARCHY, DICTATORSHIP, DEMOCRACY = 6, 4, 0, 2

    def test_lawless_ports_take_crymto_for_anything_first(self):
        p = self.p
        p.system, p.credits, p.crymto = self.FEUDAL, 1000, 500
        p.equipment = []
        message = p.buy_equipment(1)              # 400 cr cargo bay
        self.assertEqual((p.crymto, p.credits), (100, 1000))
        self.assertIn('Paid 400 in Crymto', message)
        p.trade(FOOD, True, value=150)            # a legal good with B: Crymto first, then credits
        self.assertEqual((p.crymto, p.credits), (0, 950))
        p.hull = 50
        p.repair()
        self.assertLess(p.credits, 950)

    def test_crymto_alone_can_pay_at_lawless_ports(self):
        p = self.p
        p.system, p.credits, p.crymto = self.ANARCHY, 0, 2000
        p.fuel = 2
        self.assertIn('Tank full', p.refuel())
        self.assertIn('fitted', p.buy_equipment(1))
        self.g.p.fine = 100
        self.g.pay_fines()
        self.assertEqual(p.fine, 0)

    def test_lawful_ports_still_want_credits(self):
        p = self.p
        p.system, p.credits, p.crymto = self.DEMOCRACY, 10, 5000
        p.equipment = []
        self.assertEqual(p.buy_equipment(1), 'Insufficient credits.')
        self.assertEqual(p.crymto, 5000)
        self.assertIn('anarchy and feudal ports take Crymto for anything', p.trade(FOOD, True, value=150))
        p.credits = 1000
        p.buy_equipment(1)
        self.assertEqual((p.crymto, p.credits), (5000, 600))

    def test_exchange_terms_by_government(self):
        g = self.g
        for system, fee in ((self.FEUDAL, 20), (self.ANARCHY, 20), (self.DICTATORSHIP, 30), (self.DEMOCRACY, 40)):
            g.p.system = system
            launder, buy, check = g.exchange_terms()
            self.assertEqual((launder, buy), (fee, 10))
            self.assertEqual(check == 0, system in (self.FEUDAL, self.ANARCHY))
        g.p.system = self.DEMOCRACY
        self.assertGreater(g.exchange_terms()[2], 0)

    def test_compliance_check_freezes_half_and_fines(self):
        g = self.g
        g.p.system, g.mode = self.DEMOCRACY, 'exchange'
        g.p.crymto, g.p.fine = 1000, 0
        g.exchange_amount = 1000
        cash = g.p.credits
        with unittest.mock.patch('random.random', return_value=0.):
            g.convert_crymto(True)
        self.assertEqual((g.p.crymto, g.p.fine, g.p.credits), (500, 100, cash))
        self.assertIn('COMPLIANCE CHECK', g.message)
        self.assertEqual(g.p.ledger['total']['fines'], -500)

    def test_exchange_screen_shows_the_local_terms(self):
        g = self.g
        g.d = MagicMock()
        g.mode = 'exchange'
        for system, expect in ((self.DEMOCRACY, 'compliance'), (self.FEUDAL, 'Crymto pays for anything')):
            g.p.system = system
            g.d.reset_mock()
            g.draw_exchange()
            lines = ' '.join(c.args[2] for c in g.d.text.call_args_list)
            self.assertIn(expect, lines)


if __name__ == '__main__':
    unittest.main()


class FeedbackFixTests(Base):
    """0.9.2 bug reports: engineering while docked, Crymto for contraband, no same-dock contraband profit,
    and prices that hold steadier between stops."""
    def test_engineering_training_works_when_reached_from_any_docked_screen(self):
        g = self.g
        g.mode = 'market'
        for screen in ('trades', 'money', 'help', 'vms'):
            g.p.engineering_level, g.p.credits = 0, 1000
            g.mode = screen
            if screen == 'trades': g.money_return = 'market'
            if screen == 'money': g.money_return = 'market'
            if screen == 'help': g.help_return = 'market'
            if screen == 'vms': g.vms_return = 'market'
            g.engineering_return, g.mode = screen, 'engineering'
            g.train_engineering()
            self.assertEqual(g.p.engineering_level, 1, screen)
            self.assertEqual(g.mode, 'engineering')

    def test_engineering_training_still_needs_a_dock(self):
        g = self.g
        g.engineering_return, g.mode = 'flight', 'engineering'
        g.train_engineering()
        self.assertEqual(g.p.engineering_level, 0)
        self.assertIn('docked', g.message)

    def test_b_pays_for_contraband_in_crymto_at_a_lawful_port(self):
        p = self.p
        p.system, p.credits, p.crymto = 2, 0, 2000   # a democracy
        self.assertTrue(p.trade(st.ILLEGAL[0], True, value=300).startswith('Bought'))
        self.assertEqual((p.credits, p.crymto), (0, 1700))
        self.assertEqual(p.trade_log[-1]['unit'], 'CYM')

    def test_own_trades_move_prices_at_once_but_outside_trade_only_slowly(self):
        import market as m
        mk = st.new_market(seed='calm')
        mk.advance(1000.)
        system, good = 3, 0
        calm = mk.calm[system][good]
        mk.apply(trades=[[system, good, -5]], now=1000.)
        self.assertAlmostEqual(mk.calm[system][good], calm-5)   # a commander's purchase shows straight away
        mk.change(system, good, 20)                              # a freighter unloads
        mk.settle_calm(1000.)
        lagged = mk.calm[system][good]
        mk.settle_calm(1000.+60)
        moved = mk.calm[system][good]-lagged
        self.assertGreater(moved, 0)
        self.assertLess(moved, 20*(1-__import__('math').exp(-60/m.PRICE_LAG))+.01)
        mk.settle_calm(1000.+60+20*m.PRICE_LAG)
        self.assertAlmostEqual(mk.calm[system][good], mk.stock[system][good], places=3)

    def test_the_game_prices_on_calm_stock_and_its_own_trades(self):
        st.STOCK = self.p.stock
        snap = dict(stock=[row[:] for row in self.p.stock], calm=[[float(n) for n in row] for row in self.p.stock])
        snap['calm'][1][0] = self.p.stock[1][0]+10.   # a glut has just arrived; prices have not caught up
        st.take_calm(snap)
        self.addCleanup(setattr, st, 'CALM', None)
        self.assertEqual(st.stock_level(1, 0), self.p.stock[1][0]+10)
        self.p.stock[1][0] -= 2                        # this commander buys 2 t
        self.assertEqual(st.stock_level(1, 0), self.p.stock[1][0]+10)   # 2 t fewer, at once
        st.take_calm(dict(stock=snap['stock'], calm='nonsense'))
        self.assertEqual(st.stock_level(1, 0), self.p.stock[1][0])


class CharterTests(Base):
    """New commanders earn a bonus at the Charter worlds and are often spared pirates there, until Operator."""
    def setUp(self):
        super().setUp()
        patch = unittest.mock.patch.object(st, 'CHARTER_RANK', 250)
        patch.start()
        self.addCleanup(patch.stop)

    def test_charter_pays_half_the_profit_again_up_to_the_cap(self):
        p = self.p
        p.system = 0
        self.assertTrue(p.charter)
        self.buy(FOOD, 2, value=20)
        self.assertIn('Newcomer Charter bonus', p.trade(FOOD, False, value=40))
        self.assertEqual(p.trade_log[-1]['price'], 50)          # 20 profit, 10 bonus
        p.trade(FOOD, False, value=200)
        self.assertEqual(p.trade_log[-1]['price'], 200+st.CHARTER_CAP)

    def test_no_bonus_on_a_loss_on_contraband_or_away_from_charter_worlds(self):
        p = self.p
        p.system = 0
        self.buy(FOOD, 1, value=20)
        p.trade(FOOD, False, value=15)
        self.assertEqual(p.trade_log[-1]['price'], 15)
        p.cargo[st.ILLEGAL[0]] = 1
        p.trade(st.ILLEGAL[0], False, value=100)
        self.assertEqual(p.trade_log[-1]['price'], 100)
        p.system = 1   # Corvant: not a Charter world
        self.assertFalse(p.charter)
        self.buy(FOOD, 1, value=20)
        p.trade(FOOD, False, value=40)
        self.assertEqual(p.trade_log[-1]['price'], 40)

    def test_charter_ends_at_operator(self):
        p = self.p
        p.system = 0
        p.jumps = 48   # 240 career points
        self.buy(FOOD, 1, value=0)
        result = p.trade(FOOD, False, value=100)
        self.assertEqual(p.rank, 'Operator')
        self.assertIn('Newcomer Charter ends', result)
        self.assertFalse(p.charter)

    def test_charter_patrols_turn_pirates_away_in_charter_space(self):
        g = self.g
        g.launch(); g.speed = 0
        g.station = [0., 0., st.PATROL_RADIUS+500.]
        with unittest.mock.patch.object(st.random, 'random', return_value=0.):
            g.spawn = 0; g.update(.01)
        self.assertIsNone(g.enemy)
        self.assertIn('Charter patrol', g.message)


class PoliceSettleTests(Base):
    """Flying too close to a station can be settled by radio: pay the fine and the police stand down."""
    def approach(self):
        g = self.g
        g.mode = 'flight'
        g.station, g.speed = [0., 0., 500.], 10
        g.update_station_security(.1)
        g.update_station_security(st.SECURITY_GRACE)
        self.assertTrue(g.station_hostilities[0])
        g.update_station_security(0)
        self.assertEqual(g.enemy_kind, 'police')
        return g

    def test_pay_the_fine_by_radio(self):
        g = self.approach()
        reserve = g.p.station_police_remaining[0]
        credits, fine = g.p.credits, g.p.fine
        self.assertTrue(g.can_settle())
        g.request_docking()
        self.assertEqual(g.p.credits, credits-fine)
        self.assertEqual(g.p.fine, 0)
        self.assertFalse(g.station_hostilities[0])
        self.assertIsNone(g.enemy)
        self.assertEqual(g.p.station_police_remaining[0], reserve+1)
        self.assertGreater(g.dock_clearance, 0)
        self.assertFalse(g.surrendering)

    def test_no_settling_after_firing_on_police(self):
        g = self.approach()
        g.enemy[3] -= 1
        self.assertFalse(g.can_settle())
        g.request_docking()
        self.assertTrue(g.surrendering)

    def test_cannot_pay_means_surrender(self):
        g = self.approach()
        g.p.credits = 0
        g.request_docking()
        self.assertTrue(g.surrendering)
        self.assertIn('cannot pay', g.message)

    def test_real_offences_cannot_be_settled(self):
        g = self.g
        g.mode = 'flight'
        g.station_hostile('Repeated weapons fire on station after warnings.')
        self.assertFalse(g.can_settle())
