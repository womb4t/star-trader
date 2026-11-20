"""0.9.4: scooping takes time, cut rocks regrow slowly, a refused jump points to cruise.
Run with python3 -m unittest -v test_094."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import star_trader as st
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

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()


class ScoopTimeTests(Base):
    """Feedback 35439a0e: scooping filled the hold too quickly (a whole tonne per frame)."""

    def ready(self):
        g = self.g
        g.mode = 'flight'
        g.p.equipment.append('scoops')
        g.speed = 20
        g.fragments = [[0., 0., 200., 2], [10., 0., 210., 2], [-10., 0., 220., 2]]
        return g

    def test_one_tonne_takes_scoop_seconds_to_draw_in(self):
        g = self.ready()
        g.auto_scoop_ore(st.SCOOP_SECONDS*.5)
        self.assertEqual(g.p.cargo[2], 0, 'half way through drawing in, nothing is aboard yet')
        self.assertIn('%', g.ore_status()[1])
        g.auto_scoop_ore(st.SCOOP_SECONDS*.6)
        self.assertEqual(g.p.cargo[2], 1)
        self.assertEqual(len(g.fragments), 2)

    def test_a_cluster_of_fragments_comes_aboard_one_at_a_time(self):
        g = self.ready()
        for _ in range(10): g.auto_scoop_ore(.05)   # half a second of frames
        self.assertEqual(g.p.cargo[2], 0)
        for _ in range(int(st.SCOOP_SECONDS*3/.05)+3): g.auto_scoop_ore(.05)
        self.assertEqual(g.p.cargo[2], 3)

    def test_speeding_up_or_leaving_range_loses_the_catch(self):
        g = self.ready()
        g.auto_scoop_ore(st.SCOOP_SECONDS*.8)
        g.speed = 80
        g.auto_scoop_ore(.1)
        g.speed = 20
        g.auto_scoop_ore(st.SCOOP_SECONDS*.5)
        self.assertEqual(g.p.cargo[2], 0, 'progress restarts after breaking off')

    def test_o_key_reports_progress_instead_of_grabbing_instantly(self):
        g = self.ready()
        g.scoop()
        self.assertEqual(g.p.cargo[2], 0)
        self.assertIn('Drawing in', g.message)


class RockRegrowthTests(Base):
    """Rocks outside a station respawned in full on every launch: mine, dock, relaunch, repeat."""

    def test_cut_rocks_do_not_come_back_on_the_next_launch(self):
        g = self.g
        g.launch()
        self.assertEqual(len(g.asteroids), st.ROCK_FIELD)
        rock = g.asteroids[0]
        rock[3] = 1
        g.cut_rock(rock, 'mining')
        g.launch()
        self.assertEqual(len(g.asteroids), st.ROCK_FIELD-1)

    def test_rocks_regrow_after_rock_regrow_seconds(self):
        g = self.g
        g.p.rocks_cut[g.p.system] = [1000.]
        with patch('star_trader.time.time', return_value=1000.+st.ROCK_REGROW-1):
            g.launch()
        self.assertEqual(len(g.asteroids), st.ROCK_FIELD-1)
        with patch('star_trader.time.time', return_value=1000.+st.ROCK_REGROW+1):
            g.launch()
        self.assertEqual(len(g.asteroids), st.ROCK_FIELD)
        self.assertEqual(g.p.rocks_cut[g.p.system], [], 'regrown rocks are forgotten')

    def test_each_system_keeps_its_own_field(self):
        g = self.g
        g.p.rocks_cut[g.p.system] = [st.time.time()]*st.ROCK_FIELD
        g.p.system = 1
        g.launch()
        self.assertEqual(len(g.asteroids), st.ROCK_FIELD)

    def test_cut_rocks_are_saved_and_validated(self):
        g = self.g
        g.p.rocks_cut[3] = [123.5]
        g.p.save()
        p = st.Pilot()
        self.assertTrue(p.load())
        self.assertEqual(p.rocks_cut[3], [123.5])
        p.rocks_cut = [[]]*3
        with self.assertRaises(ValueError): p.validate()
        p.rocks_cut = [[] for _ in st.SYSTEMS]; p.rocks_cut[0] = ['x']
        with self.assertRaises(ValueError): p.validate()
        p.rocks_cut[0] = [1.]*(st.ROCK_FIELD+1)
        with self.assertRaises(ValueError): p.validate()

    def test_old_saves_without_the_field_load(self):
        g = self.g
        g.p.save()
        data = st.json.loads(st.SAVE.read_text())
        data.pop('rocks_cut', None)
        st.SAVE.write_text(st.json.dumps(data))
        p = st.Pilot()
        self.assertTrue(p.load())
        self.assertEqual(p.rocks_cut, [[] for _ in st.SYSTEMS])


class JumpAdviceTests(Base):
    """Feedback e338f39b: Corvant was suggested from Ambrell but the jump was refused; cruise reaches it."""

    def test_refused_jump_offers_cruise_and_refuel(self):
        g = self.g
        g.p.system = 7
        g.p.position = st.coordinates(7)
        g.launch()
        g.station = [0., 0., 99999.]
        g.p.fuel = 3.
        g.p.waypoint = dict(name='Corvant', position=st.coordinates(1), system=1)
        g.jump()
        self.assertIn('Jump requires', g.message)
        self.assertIn('T', g.message)
        self.assertIn('cruise', g.message.lower())
        self.assertIn('refuel', g.message.lower())

    def test_refused_jump_without_cruise_fuel_only_says_refuel(self):
        g = self.g
        g.p.system = 7
        g.p.position = st.coordinates(7)
        g.launch()
        g.station = [0., 0., 99999.]
        g.p.fuel = .1
        g.p.waypoint = dict(name='Corvant', position=st.coordinates(1), system=1)
        g.jump()
        self.assertNotIn('cruise', g.message.lower())
        self.assertIn('refuel', g.message.lower())


if __name__ == '__main__':
    unittest.main()
