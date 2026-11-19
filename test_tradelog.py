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


if __name__ == '__main__':
    unittest.main()
