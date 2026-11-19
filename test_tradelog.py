"""0.8.14: cargo cost follows the cargo, and the trade log shows money in, money out and a running balance.
Run with python3 -m unittest -v test_tradelog."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
import star_trader as st

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


if __name__ == '__main__':
    unittest.main()
