"""Feedback 3cee98f4: a long-range scanner that works with the DSC console.
Run with python3 -m unittest -v test_lrscan."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
import star_trader as st
import save_server
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
        self.g.launch()
        self.g.mode = 'flight'
        self.g.spawn = 1e9

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def caller(self, z=6000.):
        g = self.g
        g.disabled_ship = dict(object=[0., 0., z], hull=40, nature='fire', ident='MV KESTREL', detected=False,
                               acknowledged=False, next_alert=st.time.time()+999, lost_at=st.time.time()+999)
        return g.disabled_ship


class EquipmentTests(Base):
    def test_scanner_is_for_sale_and_saves_validate_on_the_server(self):
        keys = [e[0] for e in st.EQUIPMENT]
        self.assertIn('lrscan', keys)
        p = st.Pilot()
        p.equipment = ['lrscan']
        p.validate()
        save_server.validate_save(dict(vars(p)))


class RangeTests(Base):
    def test_ctrl_l_needs_the_scanner(self):
        g = self.g
        g.keyboard(ord('l'), ctrl=True)
        self.assertEqual(g.radar_range, st.SCANNER_RANGE)
        self.assertIn('Long-range scanner', g.message)

    def test_ctrl_l_switches_between_short_and_long_range(self):
        g = self.g
        g.p.equipment.append('lrscan')
        g.keyboard(ord('l'), ctrl=True)
        self.assertEqual(g.radar_range, st.LONG_RANGE)
        g.keyboard(ord('l'), ctrl=True)
        self.assertEqual(g.radar_range, st.SCANNER_RANGE)

    def test_contacts_sit_at_true_range_on_long_range(self):
        g = self.g
        g.p.equipment.append('lrscan')
        far = [0., 0., 10000.]
        rim = g.scanner_position(far)
        g.keyboard(ord('l'), ctrl=True)
        inside = g.scanner_position(far)
        self.assertGreater(inside[1], rim[1], '10 km is inside the 25 km rim, not pinned to it')

    def test_selling_the_scanner_returns_to_short_range(self):
        g = self.g
        g.p.equipment.append('lrscan')
        g.keyboard(ord('l'), ctrl=True)
        g.p.equipment.remove('lrscan')
        self.assertEqual(g.effective_radar_range(), st.SCANNER_RANGE)


class DistressTests(Base):
    def test_long_range_detects_a_distress_caller_beyond_2_5_km(self):
        g = self.g
        ship = self.caller(6000.)
        g.update_distress()
        self.assertFalse(ship['detected'])
        g.p.equipment.append('lrscan')
        g.keyboard(ord('l'), ctrl=True)
        g.update_distress()
        self.assertTrue(ship['detected'])
        labels = [c[2] for c in g.scanner_contacts()]
        self.assertIn('DISABLED SHIP', labels)

    def test_with_dsc_the_contact_carries_its_identity_and_range(self):
        g = self.g
        ship = self.caller(6000.)
        g.p.equipment += ['lrscan', 'dsc']
        g.keyboard(ord('l'), ctrl=True)
        g.ship_target = ship['object']
        self.assertIn('6.0 km', g.radar_readout())
        self.assertIn('KESTREL', g.radar_readout())


if __name__ == '__main__':
    unittest.main()
