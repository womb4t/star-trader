"""0.8.13: steady deal prices, attack alarm, Y guidance, scoop announcements, feedback errors.
Run with python3 -m unittest -v test_0813."""
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import star_trader as st

_OUTBOX = tempfile.TemporaryDirectory()
st.FEEDBACK_OUTBOX = Path(_OUTBOX.name)/'feedback-outbox'
k = ord


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


class DealPriceTests(Base):
    def setUp(self):
        super().setUp()
        self.g.mode = 'market'
        self.g.p.credits = 100000
        self.g.p.equipment.append('cargo')
        self.g.selected = 0
        self.g.p.stock[self.g.p.system][0] = 30
        st.STOCK = self.g.p.stock   # prices follow stock, as in the game

    def tearDown(self):
        st.STOCK = None
        super().tearDown()

    def press(self, key, n=1):
        for _ in range(n): self.g.keyboard(k(key))

    def test_repeated_buys_keep_one_price(self):
        g = self.g
        first = g.trade_quote(0,True)
        self.press('b', 12)
        paid = [t['price'] for t in g.p.trade_log if t['side'] == 'buy']
        self.assertEqual(paid, [first]*12)
        self.assertGreater(st.quote(g.p.system,0,True), first, 'the market itself did move')

    def test_repeated_sales_keep_one_price(self):
        g = self.g
        g.p.cargo[0] = 12; g.p.cargo_paid[0] = 12
        first = g.trade_quote(0,False)
        self.press('s', 12)
        self.assertEqual([t['price'] for t in g.p.trade_log if t['side'] == 'sell'], [first]*12)

    def test_deal_ends_after_a_pause_and_your_own_buying_counts_against_you(self):
        g = self.g
        first = g.trade_quote(0,True)
        self.press('b', 12)
        g.trade_lock['at'] -= st.DEAL_PAUSE+1
        self.assertGreater(g.trade_quote(0,True), first)

    def test_selling_back_what_you_just_bought_makes_no_profit(self):
        g = self.g
        credits = g.p.credits
        self.press('b', 20)
        g.trade_lock['at'] -= st.DEAL_PAUSE+1
        self.press('s', 20)
        self.assertLess(g.p.credits, credits)

    def test_buying_back_what_you_just_sold_makes_no_profit(self):
        g = self.g
        g.p.cargo[0] = 20; g.p.cargo_paid[0] = 0
        credits = g.p.credits
        self.press('s', 20)
        g.trade_lock['at'] -= st.DEAL_PAUSE+1
        self.press('b', 20)
        self.assertLess(g.p.credits, credits)

    def test_switching_cargo_or_direction_starts_a_new_deal_and_launch_ends_the_visit(self):
        g = self.g
        self.press('b', 3)
        self.assertEqual(g.trade_lock['key'][1:], (0,True))
        self.press('s')
        self.assertEqual(g.trade_lock['key'][1:], (0,False))
        g.end_trading_visit()
        self.assertIsNone(g.trade_lock)
        self.assertEqual(g.visit_trades, {})


class AlarmTests(Base):
    def setUp(self):
        super().setUp()
        self.g.mode = 'flight'
        self.g.station[:] = [0,0,50000]
        self.g.asteroids = []
        self.g.d = MagicMock()

    def test_hostile_ship_sounds_the_alarm_until_silenced(self):
        g = self.g
        g.update_alarm(.1)
        self.assertIsNone(g.alarm)
        g.enemy = [0.,0.,800.,6,0.]
        g.update_alarm(.1)
        self.assertEqual(g.alarm, 'HOSTILE SHIP')
        g.d.beep.assert_called()
        g.keyboard(k('x'))
        self.assertIsNone(g.alarm)
        g.enemy_shot = dict(position=g.enemy[:3],kind='pirate',remaining=.25)
        g.update_alarm(.1)
        self.assertIsNone(g.alarm, 'the same fight stays quiet')
        g.enemy = g.enemy_shot = None
        g.update_alarm(.1)
        g.enemy = [0.,0.,800.,6,0.]
        g.update_alarm(.1)
        self.assertEqual(g.alarm, 'HOSTILE SHIP', 'a new fight sounds again')

    def test_mines_rocks_and_heat_sound_the_alarm(self):
        g = self.g
        g.mine_objects = [[0.,0.,300.,1.5,75.,'pirate']]
        g.update_alarm(.1); self.assertEqual(g.alarm, 'MINE AHEAD')
        g.mine_objects = [[0.,0.,300.,1.5,75.,'player']]
        g.update_alarm(.1); self.assertIsNone(g.alarm, 'your own mines are no threat')
        g.mine_objects = []
        g.asteroids = [[10.,5.,200.,3]]
        g.update_alarm(.1); self.assertEqual(g.alarm, 'COLLISION')
        g.asteroids = []
        g.heat = 75
        g.update_alarm(.1); self.assertEqual(g.alarm, 'OVERHEATING')

    def test_no_alarm_while_docked(self):
        g = self.g
        g.mode = 'market'; g.enemy = [0.,0.,800.,6,0.]
        g.update_alarm(.1)
        self.assertIsNone(g.alarm)


class FlightKeyTests(Base):
    def test_y_toggles_approach_guidance_again(self):
        g = self.g
        g.mode = 'flight'
        g.keyboard(k('y'))
        self.assertTrue(g.course_assist)
        self.assertEqual(g.key_hint(k('y')), 'Y')
        g.keyboard(k('g'), ctrl=True)
        self.assertFalse(g.course_assist, 'Ctrl+G still works')

    def test_scooping_is_a_ship_announcement_and_the_hud_says_why_not(self):
        g = self.g
        g.mode = 'flight'
        g.p.equipment.append('scoops')
        g.fragments = [[0.,0.,600.,2]]
        g.speed = 80
        self.assertEqual(g.ore_status()[1], 'SCOOP: SLOW BELOW 50')
        g.speed = 20
        self.assertEqual(g.ore_status()[1], 'SCOOP: CLOSE TO 260 m')
        g.fragments = [[0.,0.,200.,2]]
        g.auto_scoop_ore()
        self.assertEqual(g.p.cargo[2], 1)
        self.assertIsNotNone(g.alert)
        self.assertIn('Scooped', g.alert['text'])


class FeedbackErrorTests(Base):
    def test_empty_report_warning_stays_on_the_feedback_screen(self):
        g = self.g
        g.mode = 'flight'
        before = g.message
        g.keyboard(k('0'), ctrl=True)
        self.assertFalse(g.save_feedback())
        self.assertEqual(g.feedback_error, 'Write a description first.')
        g.keyboard(k('0'), ctrl=True)
        self.assertEqual(g.mode, 'flight')
        self.assertNotIn('description first', g.message)
        self.assertEqual(g.message, before)


if __name__ == '__main__':
    unittest.main()
