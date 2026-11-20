"""0.9.5: the splash holds 4 seconds; The Relay's news ticker runs along the bottom of every screen.
Run with python3 -m unittest -v test_ticker."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import star_trader as st
import startup
st.CHARTER_RANK = 0

_OUTBOX = tempfile.TemporaryDirectory()
st.FEEDBACK_OUTBOX = Path(_OUTBOX.name)/'feedback-outbox'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name)/'save.json'
        self.g = st.Game(None)
        self.g.spawn = 10000
        self.view = st.VIEW
        st.VIEW = dict(decrees=[dict(id='a', system=0, text='Halvora tax cut to 3%'),
                                dict(id='b', system=5, text='Velmora granted a shipyard')],
                       tally=dict(day=3, points=['Galactic output rose 2%', 'Customs and pirates took 40 t']),
                       tax=[0.]*8)

    def tearDown(self):
        st.VIEW = self.view
        st.SAVE = self.original_save
        self.tmp.cleanup()


class SplashTests(unittest.TestCase):
    def test_splash_holds_four_seconds(self):
        self.assertEqual(startup.SPLASH_SECONDS, 4)


class TickerItemTests(Base):
    def test_ticker_carries_decrees_tally_and_events(self):
        g = self.g
        event = dict(id='e1', system=2, title='Famine', effect='food wanted')
        with patch.object(st.Game, 'station_events', return_value=[event]), patch('star_trader.solar_flare', return_value=0):
            items = g.ticker_items(1000.)
        text = ' | '.join(items)
        self.assertIn('Velmora granted a shipyard', text)
        self.assertIn('Galactic output rose 2%', text)
        self.assertIn('Customs and pirates took 40 t', text)
        self.assertIn('Famine', text)
        self.assertIn('Meridel', text)
        self.assertTrue(items[0].startswith('COUNCIL') or items[0].startswith('STA'), 'newest decree leads')

    def test_solar_flare_cuts_the_subnet_to_local_news(self):
        g = self.g
        g.p.system = 0
        with patch.object(st.Game, 'station_events', return_value=[]), patch('star_trader.solar_flare', return_value=300):
            items = g.ticker_items(1000.)
        text = ' | '.join(items)
        self.assertIn('SOLAR FLARE', text)
        self.assertIn('Halvora tax cut', text, 'local decrees still reach you')
        self.assertNotIn('Velmora', text)
        self.assertNotIn('Galactic output', text)

    def test_no_news_says_so(self):
        g = self.g
        st.VIEW = None
        with patch.object(st.Game, 'station_events', return_value=[]), patch('star_trader.solar_flare', return_value=0):
            self.assertEqual(g.ticker_items(1000.), [st.TICKER_QUIET])


class TickerDrawTests(Base):
    def test_every_screen_and_the_cockpit_draw_the_ticker(self):
        g = self.g
        for mode in ('flight', 'market', 'vms', 'money', 'menu', 'trades', 'map', 'cruise', 'hyperspace', 'dead'):
            with self.subTest(mode=mode), patch.object(st.Game, 'draw_ticker') as ticker:
                g.d = _Recorder()
                g.mode = mode
                try: g.draw()
                except Exception: pass   # some screens need state the recorder lacks; the ticker comes first
                ticker.assert_called()

    def test_ticker_scrolls_and_wraps(self):
        g = self.g
        g.d = _Recorder()
        with patch.object(st.Game, 'ticker_items', return_value=['ONE', 'TWO']):
            g.draw_ticker(0.)
            first = [c for c in g.d.calls if c[0] == 'text' and c[3].startswith('ONE')]
            g.d.calls.clear()
            g.draw_ticker(1.)
            later = [c for c in g.d.calls if c[0] == 'text' and c[3].startswith('ONE')]
        self.assertTrue(first and later)
        self.assertLess(later[0][1], first[0][1], 'text moves left')
        for c in first+later: self.assertGreaterEqual(c[2], st.TICKER_Y)
        self.assertGreaterEqual(st.H, st.TICKER_Y+st.TICKER_H)


class _Recorder:
    """A display stand-in that records drawing calls."""
    def __init__(self):
        self.calls = []
        self.r = self.sdl = None
    def text(self, x, y, text, color=None): self.calls.append(('text', x, y, str(text)))
    def __getattr__(self, name):
        return lambda *a, **k: self.calls.append((name,)+a)


if __name__ == '__main__':
    unittest.main()
