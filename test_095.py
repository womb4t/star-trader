"""0.9.5 feedback: pirates can be brought into the sights, classic roll-and-pitch steering,
scoop totals, unknown canisters. Run with python3 -m unittest -v test_095."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
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
        self.g.spawn = 1e9

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def fight(self, enemy):
        g = self.g
        g.launch()
        g.mode = 'flight'
        g.spawn = 1e9
        g.station = [0., 0., -40000.]     # far outside the patrol zone
        g.sun = [0., 50000., 0.]
        g.planet = [0., -50000., 0.]
        g.asteroids = []
        g.p.hull = 10**6
        g.enemy_kind = 'pirate'
        g.enemy = enemy
        g.npc_mine_timer = 1e9
        return g


class PirateTests(Base):
    """Feedback 78aef994 / 243826bc: a pirate hanging at your side could never be brought into the crosshairs."""

    def test_turning_brings_a_pirate_on_your_flank_into_the_sights(self):
        g = self.fight([300., 0., -50., 6, 0.])
        g.keys = {ord('e')}           # rudder right, towards it
        seen = False
        for _ in range(200):          # 10 seconds
            g.update(.05)
            e = g.enemy
            if e[2] > 0 and abs(e[0]) < 40: seen = True; break
        self.assertTrue(seen, f'pirate never came ahead: {g.enemy[:3]}')

    def test_a_tailing_pirate_makes_a_firing_pass(self):
        g = self.fight([0., 0., -150., 6, 0.])
        g.speed = 60
        for _ in range(int((st.PIRATE_PASS+3)/.05)): g.update(.05)
        self.assertGreater(g.enemy[2], 0, 'it overshoots into view')

    def test_braking_hard_makes_a_tailing_pirate_overshoot(self):
        g = self.fight([0., 0., -150., 6, 0.])
        g.speed = 0
        for _ in range(30): g.update(.05)   # 1.5 s, well before a pass
        self.assertGreater(g.enemy[2], 0)
        self.assertIn('overshoot', g.message.lower())


class SteeringTests(Base):
    """Feedback 297e819e: left/right roll the ship, up/down pitch to make the turn; Q/E are the rudder."""

    def test_left_right_roll(self):
        g = self.g
        g.mode = 'flight'; g.speed = 0
        g.station = [0., 0., 1500.]
        g.keys = {st.RIGHT}
        g.update(.1)
        self.assertGreater(g.roll, 0)
        self.assertAlmostEqual(g.station[0], 0.)

    def test_q_e_are_the_rudder(self):
        g = self.g
        g.mode = 'flight'; g.speed = 0
        g.station = [0., 0., 1500.]
        g.keys = {ord('e')}
        g.update(.1)
        self.assertEqual(g.roll, 0)
        self.assertLess(g.station[0], 0, 'yawing right swings the station left')


class ScoopTotalTests(Base):
    """Feedback b80d1743: show what is aboard in total, not just each piece."""

    def test_scoop_message_gives_the_total_aboard(self):
        g = self.g
        g.p.cargo[2] = 4
        g.fragments = [[0., 0., 100., 2]]
        g.collect_fragment(g.fragments[0])
        self.assertIn('5 t aboard', g.message)
        self.assertIn(f'hold 5/{g.p.capacity}', g.message)


class CanisterTests(Base):
    """Feedback 4526f293: loose cargo all read ORE; a canister's contents are unknown until scooped."""

    def test_spilled_cargo_reads_canister_and_rocks_read_their_ore(self):
        g = self.g
        g.spill_cargo([0., 0., 300.], [5])
        g.fragments.append([0., 0., 400., 8])
        labels = [g.fragment_label(f) for f in g.fragments]
        self.assertEqual(labels, ['CANISTER', 'GOLD'])

    def test_scooping_a_canister_reveals_its_contents(self):
        g = self.g
        g.spill_cargo([0., 0., 100.], [5])
        g.collect_fragment(g.fragments[0])
        self.assertEqual(g.p.cargo[5], 1)
        self.assertIn('canister', g.message.lower())
        self.assertIn(st.GOODS[5].lower(), g.message.lower())


if __name__ == '__main__':
    unittest.main()
