"""The keyboard map: number row opens screens, letters act on the current screen, Ctrl for rarer flight controls.
Run with python3 -m unittest -v test_keymap."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import star_trader as st

_OUTBOX = tempfile.TemporaryDirectory()
st.FEEDBACK_OUTBOX = Path(_OUTBOX.name)/'feedback-outbox'
k = ord


class KeymapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name)/'save.json'
        self.g = st.Game(None)
        self.g.spawn = 10000

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def test_number_row_opens_the_same_screens_from_the_market(self):
        g = self.g
        for key, mode in ((k('2'),'map'),(k('3'),'vms'),(k('4'),'money'),(k('8'),'engineering'),(k('9'),'help'),(k('0'),'feedback')):
            with self.subTest(key=chr(key)):
                g.mode = 'market'
                g.keyboard(key)
                self.assertEqual(g.mode, mode)
                if mode != 'feedback':   # feedback is a text field: digits type
                    g.keyboard(key)
                    self.assertEqual(g.mode, 'market', 'pressing the screen key again goes back')

    def test_one_is_home_and_six_is_the_trade_log(self):
        g = self.g
        g.mode = 'market'; g.keyboard(k('3')); g.keyboard(k('1'))
        self.assertEqual(g.mode, 'market')
        g.keyboard(k('6'))
        self.assertEqual(g.mode, 'trades')

    def test_money_letters_open_its_services(self):
        g = self.g
        for key, mode in ((k('b'),'bank'),(k('r'),'redeem'),(k('j'),'jobs'),(k('t'),'trades')):
            with self.subTest(key=chr(key)):
                g.mode = 'market'; g.keyboard(k('4'))
                g.keyboard(key)
                self.assertEqual(g.mode, mode)

    def test_flight_letters_reach_the_right_controls(self):
        g = self.g
        g.mode = 'flight'
        for key, method in ((k('r'),'request_docking'),):
            with self.subTest(key=chr(key)), patch.object(st.Game, method) as called:
                g.keyboard(key)
                called.assert_called_once()
        before = g.rear_view
        g.keyboard(k('f'))
        self.assertNotEqual(g.rear_view, before, 'F looks behind')
        g.keyboard(k('i'))   # old fine-steering key is retired
        self.assertFalse(g.fine_control)
        g.keyboard(k('f'), ctrl=True)
        self.assertTrue(g.fine_control, 'Ctrl+F is fine steering')
        g.keyboard(k('g'), ctrl=True)
        self.assertTrue(g.course_assist, 'Ctrl+G is guidance')
        g.keyboard(k('p'), ctrl=True)
        self.assertEqual(g.nav, 'planet')

    def test_old_screen_letters_no_longer_open_screens(self):
        g = self.g
        for key in (k('g'), k('x')):
            g.mode = 'market'
            g.keyboard(key)
            self.assertEqual(g.mode, 'market')

    def test_letters_answer_hails_and_job_questions_not_digits(self):
        g = self.g
        g.mode = 'jobs'; g.p.dock_job = None
        with patch.object(st.Game, 'start_job') as start:
            g.keyboard(k('b'))
            start.assert_called_once_with(1)
        with patch.object(st.Game, 'start_job') as start:
            g.keyboard(k('2'))   # the number row doesn't answer
            start.assert_not_called()

    def test_typing_in_text_fields_is_left_alone(self):
        g = self.g
        g.mode = 'notes'
        g.keyboard(k('2'))
        self.assertEqual(g.mode, 'notes')

    def test_no_screen_maps_two_keys_to_one_action_or_one_key_twice(self):
        for mode, letters in st.SCREEN_LETTERS.items():
            actions = [v for v in letters.values() if v is not None]
            with self.subTest(mode=mode):
                self.assertEqual(len(actions), len(set(actions)))
                self.assertFalse(any(ord('0') <= key <= ord('9') for key in letters), 'digits belong to screens')
        self.assertEqual(len(set(st.FLIGHT_CTRL.values())), len(st.FLIGHT_CTRL))
        self.assertFalse(set(st.FLIGHT_CTRL) & set(st.ANY_CTRL), 'a Ctrl key means one thing')
        self.assertFalse(set(st.FLIGHT_CTRL) & {k('a'), k('c'), k('v'), k('x')}, 'Ctrl+A/C/V/X stay copy and paste')

    def test_button_hints_show_the_new_keys(self):
        g = self.g
        g.mode = 'money'
        self.assertEqual(g.key_hint(k('1')), 'B')
        self.assertEqual(g.key_hint(k('5')), 'J')
        g.mode = 'flight'
        self.assertEqual(g.key_hint(k('c')), 'D')
        self.assertEqual(g.key_hint(k('7')), 'R')
        g.mode = 'market'
        self.assertEqual(g.key_hint(k('g')), '2')
        self.assertEqual(g.key_hint(k('x')), '3')

    def test_buttons_without_a_key_show_no_hint(self):
        g = self.g
        for mode in ('flight','cruise','market','outfit','money','jobs','hail'):
            g.mode = mode
            with self.subTest(mode=mode):
                self.assertIsNone(g.key_hint(None))


if __name__ == '__main__':
    unittest.main()
