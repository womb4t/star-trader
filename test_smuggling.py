"""Contraband's risk premium: losses to customs and pirates raise the price where they happen (prototype)."""
import unittest

import economy
import econ_sim
import market as M
import star_trader as st

START = 1.8e9


class RiskPremiumTests(unittest.TestCase):
    def setUp(self):
        self.adaptive = economy.ADAPTIVE
        self.market = econ_sim.make_market('smuggling-test', adaptive=True)
        self.market.council = None
        self.market.advance(START)
        self.world, self.good = 1, st.ILLEGAL[0]
        self.risk = self.market.contraband_risk
        self.market.contraband_risk = None   # most tests look at the learned record alone

    def tearDown(self):
        economy.ADAPTIVE = self.adaptive

    def test_no_risk_still_pays_the_reward(self):
        self.assertEqual(self.market.risk_premium(self.world, self.good), 1+M.RISK_REWARD)

    def test_seizures_raise_the_price_there_and_nowhere_else(self):
        sell = lambda w: econ_sim.quote(self.market, w, self.good, False)
        before, elsewhere, buy = sell(self.world), sell(2), econ_sim.quote(self.market, self.world, self.good)
        self.market.smuggling(self.world, self.good, lost=10, now=START)
        self.assertAlmostEqual(self.market.risk_premium(self.world, self.good), (1+M.RISK_REWARD)/(1-10/(10+M.SMUGGLING_PRIOR)))
        self.assertGreater(sell(self.world), before)
        self.assertEqual(sell(2), elsewhere)
        self.assertEqual(econ_sim.quote(self.market, self.world, self.good), buy)   # buying there costs no more

    def test_deliveries_dilute_the_premium(self):
        self.market.smuggling(self.world, self.good, lost=10, now=START)
        high = self.market.risk_premium(self.world, self.good)
        self.market.smuggling(self.world, self.good, delivered=40, now=START)
        self.assertLess(self.market.risk_premium(self.world, self.good), high)

    def test_premium_is_capped_and_fades(self):
        self.market.smuggling(self.world, self.good, lost=1000, now=START)
        self.assertEqual(self.market.risk_premium(self.world, self.good), M.RISK_PREMIUM_CAP)
        self.market.advance(START+16*M.SMUGGLING_HALF_LIFE)
        self.assertLess(self.market.risk_premium(self.world, self.good), 1.05*(1+M.RISK_REWARD))

    def test_expected_risk_is_priced_in_before_any_loss(self):
        self.market.contraband_risk = lambda system: .5 if system == self.world else 0.
        self.assertAlmostEqual(self.market.risk_premium(self.world, self.good), 2*(1+M.RISK_REWARD))
        self.assertEqual(self.market.risk_premium(2, self.good), 1+M.RISK_REWARD)

    def test_deliveries_that_get_through_bring_the_premium_down_towards_what_really_happens(self):
        self.market.contraband_risk = lambda system: .5
        self.market.smuggling(self.world, self.good, delivered=200, now=START)
        self.assertLess(self.market.risk_premium(self.world, self.good), 1.1*(1+M.RISK_REWARD))

    def test_lawless_worlds_have_no_customs(self):
        lawless = next(i for i in range(len(st.SYSTEMS)) if econ_sim.lawless(i))
        self.assertEqual(econ_sim.customs(self.market, lawless), 0.)

    def test_legal_goods_have_no_premium(self):
        before = econ_sim.quote(self.market, self.world, 0, False)
        self.market.state.setdefault('smuggling', {})[str(self.world)] = {'0': [1000., 0., START]}
        self.assertEqual(econ_sim.quote(self.market, self.world, 0, False), before)


class StartingPoliceTests(unittest.TestCase):
    def test_worlds_start_policed_before_the_first_review(self):
        import council
        market = econ_sim.make_market('police-test', adaptive=True)
        council.council_state(market, START)
        for i in range(len(st.SYSTEMS)):
            government = st.PROFILES[i][0]
            if government in ('Anarchy', 'Feudal'): self.assertEqual(council.customs(market, i), 0.)
            else: self.assertAlmostEqual(council.customs(market, i), council.CUSTOMS_SEARCH*council.SAFETY_TARGET[government])



class StakeTests(unittest.TestCase):
    def buy(self, good, smuggler=True):
        from unittest.mock import patch
        import council
        market = econ_sim.make_market('stake', adaptive=True)
        market.council = None
        market.advance(START)
        council.council_state(market, START)
        cmdr = econ_sim.Commander('t', 1, __import__('random').Random(2))
        cmdr.smuggler, cmdr.credits, cmdr.came_from = smuggler, 2000., 1
        market.stock[1][good] = 50
        with patch.object(econ_sim, 'opportunities', return_value=[(1., good, 2)]), patch.object(cmdr, 'bank'):
            cmdr.act(market, START+60)
        return cmdr.cargo[2] if cmdr.cargo else 0.

    def test_smugglers_stake_at_most_half_their_credits(self):
        self.assertLessEqual(self.buy(st.ILLEGAL[0]), 1000.)
        self.assertGreater(self.buy(st.ILLEGAL[0]), 0.)

    def test_legal_cargo_is_not_limited(self):
        self.assertGreater(self.buy(8), 1000.)   # gold: dear enough that a hold costs more than half


if __name__ == '__main__':
    unittest.main()
