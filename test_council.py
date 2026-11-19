"""The Galactic Council's fiscal rule and development fund, and the bank's risk-based pricing (prototype)."""
import unittest

import council
import economy
import econ_sim
import star_trader as st

START = 1.8e9


class CouncilTests(unittest.TestCase):
    def setUp(self):
        self.adaptive = economy.ADAPTIVE
        self.market = econ_sim.make_market('council-test', adaptive=True)
        self.market.council = None   # the tests call the reviews themselves
        self.market.advance(START)
        council.council_state(self.market, START)
        self.now = START+council.WARM_UP+council.REVIEW_EVERY

    def tearDown(self):
        economy.ADAPTIVE = self.adaptive

    def review(self):
        self.now += council.REVIEW_EVERY
        self.market.advance(self.now)
        return council.review(self.market, self.now, self.market.range, st.ILLEGAL, [s[0] for s in st.SYSTEMS], st.GOODS)

    def test_tax_rises_when_the_treasury_runs_low_and_falls_when_it_is_flush(self):
        state = self.market.state['council']
        state['treasury'] = 0.
        before = state['base_tax']
        self.review()
        self.assertAlmostEqual(state['base_tax'], before+council.TAX_STEP)
        state['treasury'] = 1e7
        before = state['base_tax']
        self.review()
        self.assertAlmostEqual(state['base_tax'], before-council.TAX_STEP)

    def test_lawless_worlds_pay_no_tax_and_struggling_ones_pay_less(self):
        self.review()
        state = self.market.state['council']
        for i, p in enumerate(self.market.profiles):
            tax = state['tax'][str(i)]
            if p['government'] in economy.LAWLESS: self.assertEqual(tax, 0.)
            else: self.assertLessEqual(tax, state['base_tax'])

    def test_a_share_of_tax_and_any_surplus_go_to_the_development_fund(self):
        self.review()
        state = self.market.state['council']
        state['fund'], state['treasury'] = 0., 2*state['target']   # healthy, below the surplus line
        self.market.pay_tax(0, 100000.)   # a lawful world with tax
        taken = state['revenue']-state['revenue_seen']
        self.assertGreater(taken, 0)
        self.review()
        self.assertGreaterEqual(state['fund']+state['spent']['grants'], council.DEV_SHARE*taken-1e-6)
        state['treasury'], tax = 1e7, state['base_tax']   # a big surplus fills the fund to its cap; the rest cuts tax
        self.review()
        self.assertAlmostEqual(state['fund']+sum(council.GRANT_COST for d in state['decrees'] if d['kind'] == 'grant' and d['at'] == self.now),
                               council.FUND_CAP, delta=1e-6)
        self.assertLess(state['base_tax'], tax)

    def test_grants_go_to_the_weakest_worlds_and_are_paid_from_the_fund(self):
        self.review()
        state = self.market.state['council']
        state['fund'] = 10*council.GRANT_COST
        weak, council.WEAK = council.WEAK, 99   # every world qualifies: the order must still favour the weakest
        try:
            self.now += council.REVIEW_EVERY
            self.market.advance(self.now)
            counts = {i: len(council.exports(self.market, i, econ_sim.RANGE, st.ILLEGAL)) for i in range(len(st.SYSTEMS))}
            made = council.review(self.market, self.now, econ_sim.RANGE, st.ILLEGAL, [s[0] for s in st.SYSTEMS], st.GOODS)
        finally:
            council.WEAK = weak
        grants = [d for d in made if d['kind'] == 'grant']
        self.assertTrue(grants)
        self.assertEqual(counts[grants[0]['system']], min(counts.values()))
        self.assertAlmostEqual(state['fund'], 10*council.GRANT_COST-len(grants)*council.GRANT_COST, delta=council.GRANT_COST*3)
        self.assertIn('Council funds', grants[0]['text'])


    def test_a_beacon_brings_new_markets_in_reach_of_a_world_weak_for_a_day(self):
        velmora = [s[0] for s in st.SYSTEMS].index('Velmora')
        self.assertEqual(len(self.market.range[velmora]), 3)
        state = self.market.state['council']
        self.review()
        state['treasury'] = 1e6
        state['weak_streak'] = {str(i): (council.BEACON_WEAK_REVIEWS if i == velmora else 0) for i in range(len(st.SYSTEMS))}
        counts = {i: len(council.exports(self.market, i, self.market.range, st.ILLEGAL)) for i in range(len(st.SYSTEMS))}
        if counts[velmora] > council.WEAK: self.skipTest('Velmora is doing well in this market')
        made = self.review()
        self.assertIn(velmora, state['beacons'])
        self.assertGreater(len(self.market.range[velmora]), 3)
        self.assertIn(velmora, self.market.range[[s[0] for s in st.SYSTEMS].index('Halvora')])   # both ways
        self.assertIn('hyperspace beacon at Velmora', ' '.join(d['text'] for d in made))


class BankPricingTests(unittest.TestCase):
    def setUp(self):
        self.adaptive = economy.ADAPTIVE

    def tearDown(self):
        economy.ADAPTIVE = self.adaptive

    def test_the_margin_covers_expected_loss_costs_and_capital(self):
        _, _, market = econ_sim.run(days=1, players=2, adaptive=True, loans=True, quiet=True, seed='bank-test')
        b = market.state['bank']
        self.assertAlmostEqual(b['margin'], b['expected_loss']+econ_sim.OPEX+econ_sim.HURDLE+b['premium'])
        clean = b['expected_loss']
        b['losses'] += 50000.   # a run of bad debts raises the cost of risk
        b['reviewed'] = -1e18
        market.bank_state(START+2*econ_sim.DAY)
        self.assertGreater(b['expected_loss'], clean)

    def test_a_loan_needs_the_ship_insured(self):
        _, _, market = econ_sim.run(days=.5, players=4, adaptive=True, loans=True, quiet=True, seed='cover-test')
        for c in market.crew:
            if c.borrowed: self.assertTrue(c.insured)


if __name__ == '__main__':
    unittest.main()
