"""The STA Tally: the Galactic Assay Office's daily bulletin of the economy's main points."""
import unittest

import council
import star_trader as st
import tally

DAY = 86400.
START = 20000*DAY   # a day boundary


class TallyTests(unittest.TestCase):
    def setUp(self):
        self.market = st.new_market(seed='tally')
        self.market.council = None   # the tests drive the Council's books themselves
        self.market.advance(START)
        council.council_state(self.market, START)
        self.books = self.market.state['council']
        self.books.update(inflation=.006, rate=.045, base_tax=.02)
        for station in self.market.state['stations'].values(): station['prosperity'] = .9

    def test_publishes_once_a_day(self):
        self.assertIsNotNone(tally.publish(self.market, START+60))
        self.assertIsNone(tally.publish(self.market, START+3600))
        self.assertIsNotNone(tally.publish(self.market, START+DAY+60))

    def test_first_day_has_no_change(self):
        self.books['turnover'] = 1000.
        report = tally.publish(self.market, START+60)
        self.assertEqual(report['points'][0], 'Galactic output was 1,000 cr.')
        self.assertIsNone(report['figures']['output_change'])
        self.assertEqual(report['sign_off'], 'Weighed, not judged. — Galactic Assay Office')

    def test_main_points_from_figures(self):
        self.books['turnover'] = 1000.
        tally.publish(self.market, START+60)
        self.books['turnover'] = 2021.
        report = tally.publish(self.market, START+DAY+60)
        self.assertEqual(report['points'][0], 'Galactic output rose 2.1% on the day.')
        self.assertEqual(report['points'][1], "Prices rose 0.6%; the Council's rate is 4.5%.")
        self.assertEqual(report['points'][2], 'Every world is comfortable or better.')
        self.assertEqual(report['figures']['output'], 1021.)

    def test_struggling_worlds_named(self):
        self.market.state['stations']['5']['prosperity'] = .45
        self.market.state['stations']['4']['prosperity'] = .2
        report = tally.publish(self.market, START+60)
        self.assertEqual(report['points'][2], f'2 worlds struggling: {st.SYSTEMS[4][0]}, {st.SYSTEMS[5][0]}.')

    def test_seizures_reported(self):
        self.market.smuggling(1, st.ILLEGAL[0], lost=14, now=START)
        report = tally.publish(self.market, START+60)
        self.assertIn('Customs and pirates took 14 t of contraband.', report['points'])

    def test_player_trade_counts_as_output(self):
        before = self.books.get('turnover', 0.)
        price = self.market.price(1, 0)
        self.market.apply([[1, 0, -2]], now=START)
        self.assertAlmostEqual(self.books['turnover']-before, 2*price)

    def test_snapshot_carries_the_tally(self):
        tally.publish(self.market, START+60)
        snap = self.market.snapshot(START+60)
        self.assertEqual(snap['tally']['points'], self.market.state['tally']['points'])
        self.assertNotIn('previous', snap['tally'])


if __name__ == '__main__':
    unittest.main()
