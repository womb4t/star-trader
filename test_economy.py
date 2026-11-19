"""Station economies: people consume, workers produce, ships speed it up, events shake it, all in closed form."""
import tempfile
import threading
import unittest
from pathlib import Path

import economy
import market
import star_trader as st
from save_server import Store, make_server
from save_sync import RemoteSave

T0 = 1_800_000_000.
AGRI, INDUSTRIAL, FRONTIER = 0, 1, 4  # Halvora, Corvant, Skarrow


def quiet_economy():
    """An economy with no demand events, so tests are not at the mercy of the schedule."""
    eco = economy.Economy(st.ECONOMY_PROFILES, st.NORMAL_STOCK, {})
    return eco


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.events = economy.events_at
        economy.events_at = lambda now, profiles: []

    def tearDown(self):
        economy.events_at = self.events

    def run_station(self, eco, system, hours, levels=None, step=None, ships=0):
        levels = levels if levels is not None else [float(n) for n in st.NORMAL_STOCK[system]]
        caps = [3*n+10 for n in st.NORMAL_STOCK[system]]
        for n in range(ships): eco.visit(system, f'ship{n}', T0)
        eco.station(system, T0)
        if step:
            t = T0
            while t < T0+hours*3600:
                t = min(T0+hours*3600, t+step)
                for n in range(ships): eco.visit(system, f'ship{n}', t)
                eco.advance(system, levels, caps, t)
        else: eco.advance(system, levels, caps, T0+hours*3600)
        return levels

    def test_producers_fill_up_and_consumers_run_short(self):
        agri = self.run_station(quiet_economy(), AGRI, 12)
        industrial = self.run_station(quiet_economy(), INDUSTRIAL, 12)
        normal = st.NORMAL_STOCK
        self.assertGreater(agri[economy.FOOD], normal[AGRI][economy.FOOD])           # farms make food
        self.assertLess(industrial[economy.FOOD], normal[INDUSTRIAL][economy.FOOD])  # factory workers eat it
        self.assertGreater(industrial[economy.MACHINERY], normal[INDUSTRIAL][economy.MACHINERY])
        self.assertLess(agri[economy.MACHINERY], normal[AGRI][economy.MACHINERY])

    def test_one_big_step_matches_many_small_ones(self):
        """Lazy closed-form catch-up gives the same station as watching it all along."""
        lazy = self.run_station(quiet_economy(), INDUSTRIAL, 6)
        watched = self.run_station(quiet_economy(), INDUSTRIAL, 6, step=60)
        for a, b, n in zip(lazy, watched, st.NORMAL_STOCK[INDUSTRIAL]):
            self.assertAlmostEqual(a, b, delta=.12*n+1)

    def test_busier_stations_recover_faster(self):
        def recovered(ships):
            levels = [float(n) for n in st.NORMAL_STOCK[AGRI]]
            levels[economy.FOOD] = 0.
            return self.run_station(quiet_economy(), AGRI, .5, levels=levels, ships=ships)[economy.FOOD]
        self.assertGreater(recovered(12), recovered(0)*1.5)
        self.assertEqual(economy.traffic_factor(0), 1)
        self.assertLess(economy.traffic_factor(1000), 4.0001)

    def test_hunger_lowers_prosperity_and_output(self):
        eco = quiet_economy()
        starving = [float(n) for n in st.NORMAL_STOCK[INDUSTRIAL]]
        starving[economy.FOOD] = starving[economy.MEDICINE] = 0.
        caps = [0.]*economy.GOODS  # nothing can be restocked
        eco.station(INDUSTRIAL, T0)
        fed = quiet_economy()
        self.run_station(fed, INDUSTRIAL, 12)
        eco.advance(INDUSTRIAL, starving, [0.]*economy.GOODS, T0+12*3600)
        self.assertLess(eco.station(INDUSTRIAL, 0)['prosperity'], fed.station(INDUSTRIAL, 0)['prosperity']-.3)
        _, made_hungry = eco.flows(INDUSTRIAL, starving, eco.station(INDUSTRIAL, 0), [])
        _, made_fed = fed.flows(INDUSTRIAL, [float(n) for n in st.NORMAL_STOCK[INDUSTRIAL]], fed.station(INDUSTRIAL, 0), [])
        self.assertLess(made_hungry[economy.MACHINERY], made_fed[economy.MACHINERY])

    def test_population_follows_prosperity_slowly_and_within_bounds(self):
        eco = quiet_economy()
        self.run_station(eco, AGRI, 24*30)
        station = eco.station(AGRI, 0)
        self.assertGreater(station['population'], 1)
        self.assertLessEqual(station['population'], economy.POPULATION_RANGE[1])

    def test_events_are_shared_and_fit_the_world(self):
        economy.events_at = self.events
        seen = 0
        for window in range(300):
            events = economy.window_events(window, st.ECONOMY_PROFILES)
            self.assertEqual(events, economy.window_events(window, st.ECONOMY_PROFILES))
            for e in events:
                seen += 1
                self.assertIn(st.ECONOMY_PROFILES[e['system']]['economy'], economy.EVENTS[e['kind']][3])
                self.assertGreater(e['end'], e['start'])
        self.assertGreater(seen, 200)

    def test_a_famine_drives_food_up_in_price(self):
        eco = quiet_economy()
        levels = [float(n) for n in st.NORMAL_STOCK[INDUSTRIAL]]
        famine = dict(id='x', kind='famine', system=INDUSTRIAL, start=0, end=1e12, title='Famine', effect='')
        station = eco.station(INDUSTRIAL, T0)
        calm = eco.targets(INDUSTRIAL, levels, station, [])
        hungry = eco.targets(INDUSTRIAL, levels, station, [famine])
        self.assertLess(hungry[economy.FOOD], calm[economy.FOOD])

    def test_state_is_plain_json(self):
        import json
        eco = quiet_economy()
        self.run_station(eco, FRONTIER, 3, ships=3)
        json.loads(json.dumps(eco.state, allow_nan=False))


class MarketEconomyTests(unittest.TestCase):
    def market(self, **extra):
        return st.new_market(dict(stock=[row[:] for row in st.NORMAL_STOCK], shipments=[], next_trade=None, seq=0, seed='eco', **extra))

    def test_trades_made_in_the_game_carry_into_the_levels(self):
        m = self.market()
        m.advance(T0)
        m.stock[AGRI][economy.FOOD] -= 5  # what Pilot.trade does when docked offline
        before = m.levels[AGRI][economy.FOOD]
        m.reconcile()
        self.assertAlmostEqual(m.levels[AGRI][economy.FOOD], before-5, delta=.51)

    def test_old_market_state_gains_levels(self):
        m = st.new_market(dict(stock=[row[:] for row in st.NORMAL_STOCK], shipments=[], next_trade=None, seq=0, seed='old'))
        self.assertEqual([[round(x) for x in row] for row in m.levels], m.stock)
        m.advance(T0); m.advance(T0+3600)
        self.assertIn('economy', m.snapshot(T0+3600))

    def test_stock_stays_whole_and_in_range(self):
        m = self.market()
        for h in range(24): m.advance(T0+h*1800)
        for system, row in enumerate(m.stock):
            for good, n in enumerate(row):
                self.assertIs(type(n), int)
                self.assertTrue(0 <= n <= m.cap(system, good))

    def test_bots_leave_a_margin_for_commanders(self):
        m = self.market()
        for h in range(13): m.advance(T0+h*3600)
        st.STOCK = m.stock
        try:
            for good in range(economy.GOODS):
                prices = [st.price(i, good) for i in range(8)]
                self.assertLess(max(prices)/min(prices), market.BOT_MARGIN*1.25)
            ratios = [max(st.price(i, g) for i in range(8))/min(st.price(i, g) for i in range(8)) for g in range(economy.GOODS)]
            self.assertGreater(sum(ratios)/len(ratios), 1.3)  # still worth trading
        finally: st.STOCK = None

    def test_visitors_count_as_traffic(self):
        m = self.market()
        m.apply(trades=[[2, 0, -1]], ship='Kenton', system=2, now=T0)
        self.assertEqual(m.economy.ships(2, T0+60), 1)
        self.assertEqual(m.economy.ships(2, T0+economy.VISIT_WINDOW+1), 0)


class GameEconomyTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import MagicMock
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name)/'save.json'
        self.game = st.Game(MagicMock())
        self.event = dict(id='test-0', kind='famine', system=1, start=0, end=1e12, title='Famine',
                          effect=economy.HEADLINES['famine'])
        self.events = economy.events_at
        economy.events_at = lambda now, profiles: [self.event]

    def tearDown(self):
        economy.events_at = self.events
        st.SAVE = self.original_save
        st.STOCK = None
        self.tmp.cleanup()

    def texts(self):
        return ' '.join(str(c.args[2]) for c in self.game.d.text.call_args_list if len(c.args) > 2)

    def test_news_of_an_event_arrives_once(self):
        g = self.game
        g.update_market()
        self.assertIn('NEWS: Famine on Corvant', g.message)
        g.message = ''
        g.update_market()
        self.assertEqual(g.message, '')

    def test_a_solar_flare_blocks_news_from_other_systems(self):
        from unittest.mock import patch
        g = self.game; g.p.system = 0
        with patch.object(st, 'solar_flare', return_value=300):
            g.update_market()
            self.assertNotIn('NEWS', g.message)
            g.p.system = 1
            g.update_market()
            self.assertIn('NEWS: Famine', g.message)

    def test_market_and_planet_profile_show_the_economy(self):
        g = self.game
        g.update_market()
        g.mode = 'market'; g.draw()
        self.assertRegex(self.texts(), r'bn people, \w+, \d+ ships? trading')
        g.d.text.reset_mock()
        g.p.system = 1; g.draw()
        self.assertIn('FAMINE', self.texts())
        g.d.text.reset_mock()
        g.mode, g.profile_system = 'planet_profile', 0
        g.draw()
        text = self.texts()
        self.assertIn('Makes: Food, Textiles, Narcotics', text)
        self.assertIn('Prosperity:', text)

    def test_offline_market_runs_once_a_second(self):
        g = self.game
        g.update_market()
        first = g.market.state['stations']['0']['last']
        g.update_market()
        self.assertEqual(g.market.state['stations']['0']['last'], first)


class ServerEconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'p.sqlite3')
        self.store.create_player('Kenton', 'k'*43)
        (self.root/'Kenton.token').write_text('k'*43)
        server = make_server(self.store, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), worker.join()))
        self.remote = RemoteSave('http://127.0.0.1:'+str(server.server_port), self.root/'Kenton.token', self.root/'Kenton')

    def tearDown(self): self.tmp.cleanup()

    def test_market_reports_economy_and_counts_the_commander_at_a_station(self):
        snap = self.remote.request(dict(trades=[], system=3), endpoint='/v1/market')
        self.assertEqual(len(snap['economy']), 8)
        self.assertGreaterEqual(snap['economy'][3]['ships'], 1)
        with self.assertRaises(RuntimeError): self.remote.request(dict(system=99), endpoint='/v1/market')
        with self.assertRaises(RuntimeError): self.remote.request(dict(system='Halvora'), endpoint='/v1/market')


if __name__ == '__main__': unittest.main()


class LongGapTests(unittest.TestCase):
    def test_population_settles_without_overshooting_after_a_long_gap(self):
        import economy, star_trader as st
        m = st.new_market(seed='gap')
        m.advance(1.8e9)
        station = m.state['stations']['0']
        station['population'] = 1.
        m.advance(1.8e9+400*24*3600)   # over a year with nobody about: each economy step spans weeks
        quiet = .8+.4*station['prosperity']   # the size a world settles at with no regular traffic
        self.assertLess(abs(station['population']-quiet), .05)   # settled there, not overshot past it


if __name__ == '__main__':
    unittest.main()
