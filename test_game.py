"""Offline regression checks. Run with python3 -m unittest -v test_game."""
import json
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
import star_trader as st

# Keep logged feedback out of the real outbox.
_OUTBOX = tempfile.TemporaryDirectory()
st.FEEDBACK_OUTBOX = Path(_OUTBOX.name)/'feedback-outbox'


class GameplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name) / 'save.json'
        self.game = st.Game(None)
        self.game.spawn = 10000

    def test_escape_emergency_close_from_every_screen_preserves_progress(self):
        modes = ('market','flight','cruise','hyperspace','dead','menu','notes','redeem',
                 'money','vms','outfit','help','updates','map','planet_profile','jobs',
                 'bank','exchange','trade_deal','departure','engineering','launch_warning',
                 'distress','feedback','rename')
        for mode in modes:
            with self.subTest(mode=mode):
                st.SAVE.unlink(missing_ok=True)
                g = st.Game(None)
                g.mode = mode
                g.p.credits = 12345
                g.p.notes = 'Keep my testing notes'
                if mode == 'map': g.map_input = 'coordinates'
                g.key(27)
                self.assertFalse(g.running)
                saved = json.loads(st.SAVE.read_text())
                self.assertEqual(saved['credits'],12345)
                self.assertEqual(saved['notes'],'Keep my testing notes')
                self.assertIn('_session',saved)

    def test_backspace_goes_back_from_every_screen_without_quitting(self):
        expected = {'money':'market','vms':'market','outfit':'market','help':'market','updates':'market','map':'market',
                    'planet_profile':'map','jobs':'money','bank':'money','exchange':'money','trade_deal':'market',
                    'departure':'market','engineering':'market','launch_warning':'market','menu':'market','distress':'flight'}
        for mode,back in expected.items():
            with self.subTest(mode=mode):
                g = st.Game(None)
                g.mode = mode
                g.key(8)
                self.assertTrue(g.running)
                self.assertEqual(g.mode,back)
        for mode in ('market','flight','cruise','hyperspace'):
            with self.subTest(mode=mode):
                g = st.Game(None); g.mode = mode
                g.key(8)
                self.assertTrue(g.running)
                self.assertEqual(g.mode,mode)

    def test_repeated_backspace_always_reaches_market_or_cockpit(self):
        import random
        keys = [ord(c) for c in 'gx9`2u8jie145']+[st.UP,st.DOWN]
        for seed in range(300):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                g = st.Game(None); g.spawn = 10**6
                if rng.random() < .5: g.launch(); g.speed = 0
                base = g.mode
                for _ in range(rng.randint(1,8)):
                    g.key(rng.choice(keys))
                    if g.mode in ('market','flight'): base = g.mode
                for _ in range(25):
                    if g.mode in ('market','flight'): break
                    g.key(8)
                self.assertTrue(g.running)
                self.assertEqual(g.mode,base)

    def test_new_pilots_see_the_introduction_once(self):
        from unittest.mock import MagicMock
        g = st.Game(MagicMock())
        self.assertEqual(g.mode,'intro')
        for _ in range(len(g.INTRO)-1): g.key(13)
        self.assertEqual(g.intro_page,len(g.INTRO)-1)
        g.key(LEFT := st.LEFT); self.assertEqual(g.intro_page,len(g.INTRO)-2)
        g.key(13); g.key(13)
        self.assertEqual(g.mode,'market')
        self.assertTrue(g.p.intro_seen)
        again = st.Game(MagicMock())
        self.assertEqual(again.mode,'market')
        again.open_utility('menu'); again.choose_menu_action(len(again.menu_actions())-1)
        self.assertEqual((again.mode,again.intro_page),('intro',0))
        again.key(8)
        self.assertEqual(again.mode,'market')

    def test_backspace_still_deletes_in_text_fields(self):
        g = st.Game(None)
        for mode,attr in (('notes','notes'),('rename','name')):
            g.mode = mode
            setattr(g.p,attr,'abc')
            g.key(8)
            self.assertEqual((g.mode,getattr(g.p,attr)),(mode,'ab'))
        g.mode = 'redeem'; g.credit_code_text = 'XY'; g.key(8)
        self.assertEqual((g.mode,g.credit_code_text),('redeem','X'))
        g.mode = 'map'; g.map_input = 'search'; g.map_text = 'ab'
        g.key(8)
        self.assertEqual(g.mode,'map')

    def test_cancel_mouse_button_navigates_without_triggering_escape(self):
        g = self.game
        g.mode,g.launch_return = 'launch_warning','market'
        g.footer_actions = []
        g.mouse_button(35,674,200,'Cancel',27)
        self.assertIsNone(g.footer_actions[0][1])
        g.footer_actions[0][2]()
        self.assertTrue(g.running)
        self.assertEqual(g.mode,'market')
        g.mode,g.outfit_return = 'outfit','vms'
        g.mouse_back()
        self.assertTrue(g.running)
        self.assertEqual(g.mode,'vms')

    def finish_jump(self,game):
        game.speed = 0
        game.keys = {ord('h')}
        for _ in range(61): game.update(.05)
        self.assertEqual(game.mode,'hyperspace')
        game.update(1.6)

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def test_guidance_centres_without_throttle_or_roll(self):
        g = self.game
        g.mode = 'flight'
        g.station = [100.,40.,1500.]
        g.speed,g.roll = 12.,.4
        g.key(ord('y'))
        g.update(.1)
        self.assertLess(g.station[0],100)
        self.assertLess(g.station[1],40)
        self.assertEqual(g.speed,12)
        self.assertEqual(g.roll,.4)
        self.assertEqual(g.dock_clearance,0)
        g.key(st.LEFT)
        self.assertFalse(g.course_assist)

    def test_fine_steering_reduces_turn_and_roll(self):
        g = self.game
        g.mode = 'flight'
        g.keys = {st.RIGHT,ord('e')}
        g.key(ord('i'))
        g.update(.1)
        self.assertAlmostEqual(g.roll,.02)
        self.assertAlmostEqual(g.station[0],-1500*st.math.sin(.013)*st.math.cos(.02))
        g.key(ord('i'))
        self.assertFalse(g.fine_control)

    def test_guidance_rejects_remote_course_and_behind(self):
        g = self.game
        g.mode = 'flight'
        g.nav = 'course'
        g.p.waypoint = dict(position=st.coordinates(1),system=1,name='Corvant')
        g.key(ord('y'))
        g.update(.1)
        self.assertFalse(g.course_assist)
        g.nav = 'station'
        g.station = [0.,0.,-200.]
        g.key(ord('y'))
        g.update(.1)
        self.assertFalse(g.course_assist)

    def test_station_warns_before_dispatching_police(self):
        g = self.game
        g.mode = 'flight'
        g.station,g.speed = [0.,0.,500.],10
        g.update_station_security(.1)
        self.assertIn('WARNING',g.message)
        self.assertIsNone(g.enemy)
        g.update_station_security(6)
        self.assertIn('FINAL',g.message)
        self.assertIsNone(g.enemy)
        g.update_station_security(6)
        self.assertTrue(g.station_hostilities[0])
        g.update_station_security(0)
        self.assertEqual(g.enemy_kind,'police')
        self.assertIsNotNone(g.enemy)
        self.assertFalse(g.station_allows())

    def test_station_clearance_or_retreat_stops_warning(self):
        g = self.game
        g.station,g.speed = [0.,0.,500.],10
        g.update_station_security(7)
        g.dock_clearance = 120
        g.update_station_security(20)
        self.assertEqual(g.security_elapsed,0)
        self.assertFalse(g.station_hostilities[0])
        g.dock_clearance = 0
        g.station[2] = 900
        g.update_station_security(20)
        self.assertFalse(g.station_hostilities[0])

    def test_repeated_station_fire_turns_hostile_once_and_survives_reload(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,600.]
        for _ in range(st.STRAY_SHOT_LIMIT+1):
            g.cooldown = 0
            g.fire_laser()
        self.assertTrue(g.station_hostilities[0])
        self.assertEqual(g.enemy_kind,'police')
        fine = g.p.fine
        g.station_hostile('Repeated attack')
        self.assertEqual(g.p.fine,fine)
        g.checkpoint()
        restored = st.Game(None)
        self.assertTrue(restored.station_hostilities[0])

    def test_turn_preserves_range_and_matches_radar_and_view(self):
        g = self.game
        g.station = [300.,80.,1500.]
        before = sum(v*v for v in g.station)
        view_before = g.project(g.station)[0]
        radar_before = g.scanner_position(g.station)[0]
        g.turn_world(.1,0)
        self.assertAlmostEqual(sum(v*v for v in g.station),before)
        self.assertLess(g.project(g.station)[0],view_before)
        self.assertLess(g.scanner_position(g.station)[0],radar_before)
        g.roll = st.math.pi/2
        g.station = [0.,300.,1000.]
        self.assertGreater(g.scanner_position(g.station)[0],955)
        self.assertGreater(g.project(g.station)[0],st.W/2)
        g.rear_view = True
        self.assertLess(g.scanner_position(g.station)[0],955)

    def test_pitch_turns_preserve_range_and_match_vertical_view(self):
        g = self.game
        g.mode = 'flight'
        g.speed = 0
        g.station = [0.,0.,1500.]
        for key,sign in ((st.UP,1),(st.DOWN,-1)):
            g.station = [0.,0.,1500.]
            g.keys = {key}
            g.update(.1)
            self.assertAlmostEqual(sum(v*v for v in g.station),1500**2)
            self.assertGreater(sign*g.station[1],0)
            self.assertGreater(sign*(g.project(g.station)[1]-330),0)
        # Opposite rotations undo each other, including while rolled.
        g.roll = .7
        g.station = [100.,200.,900.]
        original = g.station[:]
        g.turn_world(.2,0)
        g.turn_world(-.2,0)
        g.turn_world(0,.2)
        g.turn_world(0,-.2)
        for actual,expected in zip(g.station,original):
            self.assertAlmostEqual(actual,expected)

    def test_broke_pilot_can_work_buy_fuel_and_not_claim_twice(self):
        g = self.game
        g.p.credits,g.p.fuel = 0,0
        g.key(ord('j'))
        g.key(ord('1'))
        for _ in range(5): g.answer_job(g.p.dock_job['answer'])
        g.update_job(59)
        self.assertEqual(g.p.credits,0)
        g.update_job(1)
        self.assertEqual(g.p.credits,25)
        self.assertEqual(g.p.fuel,0)
        g.update_job(60)
        self.assertEqual(g.p.credits,25)
        g.key(ord('j'))
        self.assertEqual(g.mode,'money')
        g.key(ord('9'))
        g.key(ord('f'))
        self.assertEqual(g.p.fuel,7)
        self.assertEqual(g.p.credits,4)

    def test_job_mistakes_preserve_base_pay_and_workshop_experience(self):
        g = self.game
        g.mode = 'jobs'
        before = g.engineering_chance()
        g.start_job(2)
        for _ in range(5): g.answer_job((g.p.dock_job['answer']+1)%3)
        cash = g.p.credits
        g.update_job(90)
        self.assertEqual(g.p.credits,cash+25)
        self.assertEqual(g.p.workshop_xp,10)
        self.assertGreater(g.engineering_chance(),before)
        self.assertEqual(g.p.engineering_level,0)

    def test_job_pauses_and_resumes_after_reload_without_offline_pay(self):
        g = self.game
        g.mode = 'jobs'
        g.start_job(1)
        g.update_job(20)
        g.answer_job(g.p.dock_job['answer'])
        g.mouse_back()
        g.update_job(80)
        self.assertEqual(g.p.dock_job['elapsed'],20)
        restored = st.Game(None)
        self.assertEqual(restored.mode,'market')
        self.assertEqual(restored.p.dock_job['step'],1)
        self.assertEqual(restored.p.dock_job['elapsed'],20)
        restored.key(ord('j'))
        for _ in range(4): restored.answer_job(restored.p.dock_job['answer'])
        cash = restored.p.credits
        restored.update_job(55)
        self.assertEqual(restored.p.credits,cash+35)

    def test_jobs_only_accessible_docked(self):
        g = self.game
        g.mode = 'flight'
        g.key(ord('j'))
        self.assertEqual(g.mode,'flight')
        g.start_job(0)
        self.assertIsNone(g.p.dock_job)

    def test_jobs_accessible_from_bank_and_arrow_enter_selection(self):
        g = self.game
        g.mode = 'bank'
        g.key(ord('j'))
        self.assertEqual(g.mode,'jobs')
        g.key(st.DOWN)
        g.key(13)
        self.assertEqual(g.p.dock_job['kind'],1)

    def test_pirate_hit_in_front_of_station_does_not_make_station_hostile(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,1500.]
        g.enemy = [0.,0.,400.,1,0]
        g.fire_laser()
        self.assertIsNone(g.enemy)
        self.assertFalse(g.station_hostilities[0])
        self.assertEqual(g.p.fine,0)

    def test_shots_near_station_do_not_count_as_hull_hits(self):
        g = self.game
        g.mode = 'flight'
        g.station = [250.,0.,3000.]
        self.assertTrue(g.on_target(g.station,60))
        g.fire_laser()
        self.assertFalse(g.station_hostilities[0])
        self.assertEqual(g.p.fine,0)

    def test_nearest_hull_blocks_laser(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,500.]
        g.enemy = [0.,0.,1000.,6,0]
        g.fire_laser()
        self.assertEqual((g.station_strikes,g.p.fine),(1,st.STRAY_SHOT_FINE))
        self.assertEqual(g.enemy[3],6)
        g.station_strikes = 0
        g.station = [0.,0.,1500.]
        g.enemy = [0.,0.,1000.,6,0]
        g.asteroids = [[0.,0.,300.,3]]
        g.fire_laser()
        self.assertEqual(g.station_strikes,0)
        self.assertEqual(g.enemy[3],6)

    def test_incoming_enemy_fire_has_visible_timed_beam(self):
        g = self.game
        g.mode = 'flight'
        g.speed = 0
        g.station = [0.,0.,9000.]  # outside the patrol zone
        g.enemy = [0.,0.,500.,6,1.95]
        g.update(.1)
        self.assertIsNotNone(g.enemy_shot)
        self.assertEqual(g.enemy_shot['kind'],'pirate')
        self.assertGreater(g.enemy_shot['remaining'],0)
        self.assertLess(g.shield,100)
        g.update(.3)
        self.assertIsNone(g.enemy_shot)

    def test_station_job_limits_persist_and_refresh_after_24_hours(self):
        g = self.game
        g.mode = 'jobs'
        with patch.object(st.time,'time',return_value=1000000):
            board,limits,_ = g.station_job_board()
            deadline = board['refresh_at']
            for _ in range(limits[0]):
                g.start_job(0)
                for _ in range(5): g.answer_job(g.p.dock_job['answer'])
                g.update_job(60)
            cash = g.p.credits
            g.start_job(0)
            self.assertIsNone(g.p.dock_job)
            self.assertEqual(g.p.credits,cash)
            g.checkpoint()
            restored = st.Game(None)
            restored.mode = 'jobs'
            restored.start_job(0)
            self.assertIsNone(restored.p.dock_job)
        with patch.object(st.time,'time',return_value=deadline-1):
            restored.start_job(0)
            self.assertIsNone(restored.p.dock_job)
        with patch.object(st.time,'time',return_value=deadline):
            restored.start_job(0)
            self.assertIsNotNone(restored.p.dock_job)
            self.assertEqual(restored.p.job_boards[0]['used'][0],1)

    def test_station_boards_are_independent_and_refresh_keeps_active_shift(self):
        g = self.game
        g.mode = 'jobs'
        with patch.object(st.time,'time',return_value=1000000):
            g.start_job(2)
            deadline = g.p.job_boards[0]['refresh_at']
            active = dict(g.p.dock_job)
            self.assertEqual(g.p.job_boards[0]['used'][2],1)
            g.p.system = 1
            board,_,_ = g.station_job_board()
            self.assertEqual(board['used'],[0,0,0])
            g.p.system = 0
        with patch.object(st.time,'time',return_value=deadline+86400*4):
            board,_,_ = g.station_job_board()
            self.assertEqual(board['used'],[0,0,0])
            self.assertEqual(g.p.dock_job,active)
            self.assertGreater(board['refresh_at'],st.time.time())

    def test_workshop_questions_and_answer_positions_vary(self):
        g = self.game
        prompts,patterns = set(),set()
        for seed in range(20):
            g.p.dock_job = dict(kind=2,step=0,seed=str(seed))
            sequence = []
            for step in range(5):
                g.p.dock_job['step'] = step
                g.job_question()
                prompts.add(g.p.dock_job['prompt'])
                sequence.append(g.p.dock_job['answer'])
            patterns.add(tuple(sequence))
        self.assertGreaterEqual(len(prompts),25)
        self.assertGreater(len(patterns),10)

    def test_contraband_rewards_reflect_planet_economy_and_government(self):
        self.assertGreater(st.quote(0,6,False)-st.quote(1,6),70)
        self.assertGreater(st.quote(0,7,False)-st.quote(1,7),27)
        # Frontier demand especially rewards arms runs from industrial sources.
        self.assertGreater(st.quote(4,7,False),st.quote(0,7,False))
        for system in range(len(st.SYSTEMS)):
            for good in st.ILLEGAL:
                self.assertLess(st.quote(system,good,False),st.quote(system,good))
        # Changing government alone affects arms demand at the same market.
        with patch.object(st,'PROFILES',[('Corporate state',1,1)]*8):
            peaceful = st.price(4,7)
        self.assertGreater(st.price(4,7),peaceful)

    def test_planet_profile_navigation_preserves_trip_and_safe_docked_session(self):
        g = self.game
        g.key(ord('g'))
        g.target = 1
        g.key(ord('i'))
        self.assertEqual(g.mode,'planet_profile')
        self.assertEqual(g.profile_system,1)
        self.assertEqual(g.session_mode(),'market')
        g.key(st.RIGHT)
        self.assertEqual(g.profile_system,2)
        self.assertEqual(g.target,1)
        g.mouse_back()
        self.assertEqual(g.mode,'map')
        g.cursor_mode = True
        g.map_cursor = [5.,5.]
        g.key(ord('i'))
        self.assertEqual(g.mode,'map')
        self.assertIn('No planet',g.message)

    def test_each_feedback_report_is_logged_as_its_own_entry(self):
        g = self.game
        for f in st.FEEDBACK_OUTBOX.glob('*'): f.unlink()
        g.key(ord('0'))
        self.assertEqual(g.mode,'feedback')
        self.assertEqual(g.session_mode(),'market')
        self.assertFalse(g.save_feedback())
        g.text_input('Buttons fail at 150% scaling. Café test.')
        self.assertTrue(g.save_feedback())
        self.assertEqual(g.feedback_text,'')
        self.assertIn('logged',g.message)
        g.feedback_type = 'suggestion'
        g.text_input('Please add escorts & convoys')
        self.assertTrue(g.save_feedback())
        entries = sorted((json.loads(p.read_text()) for p in st.FEEDBACK_OUTBOX.glob('*.json')),key=lambda e:e['created'])
        self.assertEqual([(e['kind'],e['text']) for e in entries],[('bug','Buttons fail at 150% scaling. Café test.'),('suggestion','Please add escorts & convoys')])
        self.assertEqual(entries[0]['version'],st.VERSION)
        self.assertNotIn(g.p.commander_id,json.dumps(entries))
        self.assertEqual(g.feedback_waiting(),2)
        g.mouse_back()
        self.assertEqual(g.mode,'market')

    def test_illicit_sale_pays_crymto_but_credit_purchases_remain_available(self):
        p = self.game.p
        p.cargo[6] = 1
        cash = p.credits
        p.trade(6,False)
        self.assertEqual(p.credits,cash)
        self.assertEqual(p.crymto,st.quote(0,6,False))
        p.credits = 1000
        dirty = p.crymto
        p.trade(6,True)
        self.assertEqual(p.crymto,dirty)
        self.assertEqual(p.credits,1000-st.quote(0,6))
        p.crymto = 1000
        cash = p.credits
        p.trade(6,True,use_crymto=True)
        self.assertEqual(p.credits,cash)
        self.assertEqual(p.crymto,1000-st.quote(0,6))

    def test_crymto_survives_destruction_reload_and_rescue_claims(self):
        g = self.game
        g.p.crymto = 500
        self.assertNotIn('crymto',g.salvage_terms(25))
        g.p.hull,g.mode = 0,'dead'
        g.checkpoint()
        restored = st.Game(None)
        self.assertEqual(restored.p.crymto,500)
        restored.recover_destroyed_pilot()
        self.assertEqual(restored.p.crymto,500)
        self.assertEqual(restored.p.credits,0)

    def test_crymto_exchange_is_restricted_and_charges_fees(self):
        g = self.game
        g.p.crymto = 100
        g.key(ord('e'))
        self.assertEqual(g.mode,'market')
        g.p.system = 6
        g.key(ord('e'))
        self.assertEqual(g.mode,'exchange')
        g.exchange_amount = 100
        cash = g.p.credits
        g.convert_crymto(True)
        self.assertEqual(g.p.crymto,0)
        self.assertEqual(g.p.credits,cash+80)
        g.exchange_amount = 80
        g.convert_crymto(False)
        self.assertEqual(g.p.crymto,72)
        self.assertEqual(g.p.credits,cash)

    def test_clean_payment_requires_explicit_deal_and_rewards_cover_fees(self):
        g = self.game
        g.p.cargo[6] = 1
        g.selected = 6
        g.key(ord('n'))
        self.assertEqual(g.mode,'trade_deal')
        cash = g.p.credits
        g.key(ord('y'))
        self.assertEqual(g.p.crymto,0)
        self.assertEqual(g.p.credits,cash+st.quote(0,6,False)*85//100)
        self.assertEqual(g.p.cargo[6],0)
        self.assertGreater(st.quote(0,6,False)*80//100-st.quote(1,6),70)
        self.assertGreater(st.quote(0,7,False)*80//100-st.quote(1,7),27)

    def test_matching_stocktake_has_positive_shortfall_and_surplus_options(self):
        g = self.game
        found_matching = False
        for seed in range(100):
            g.p.dock_job = dict(kind=1,step=0,seed=str(seed))
            g.job_question()
            j = g.p.dock_job
            for option in j['choices']:
                if option != 'Matches manifest':
                    self.assertGreater(int(option.split()[-1]),0)
            counts = [int(part) for part in j['prompt'].replace('.','').split() if part.isdigit()]
            if counts[0] == counts[1]:
                found_matching = True
                self.assertEqual(j['choices'][j['answer']],'Matches manifest')
        self.assertTrue(found_matching)

    def test_departure_warns_for_refused_destination_even_with_fuel(self):
        g = self.game
        g.p.system = 4  # Anarchy: fines do not hold the ship.
        g.p.fine,g.p.fuel = 1200,7
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.key(ord('l'))
        self.assertEqual(g.mode,'launch_warning')
        self.assertTrue(any('ARREST' in warning for warning in g.launch_warnings()))
        g.station_hostilities[6] = True
        g.p.waypoint = dict(name='Duskholt',position=st.coordinates(6),system=6)
        self.assertTrue(any('REFUSE' in warning for warning in g.launch_warnings()))
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.key(ord('f'))
        self.assertEqual(g.mode,'launch_warning')
        g.key(ord('g'))
        self.assertEqual(g.mode,'map')
        self.assertEqual(g.map_return,'market')

    def test_finite_police_reserves_persist_and_defeat_all_allows_docking(self):
        g = self.game
        g.mode = 'flight'
        g.station_hostilities[0] = True
        for _ in range(st.STATION_POLICE_CAPACITY):
            self.assertTrue(g.dispatch_station_police())
            g.destroy_enemy()
        self.assertFalse(g.dispatch_station_police())
        self.assertEqual(g.p.station_police_remaining[0],0)
        self.assertTrue(g.station_overwhelmed())
        self.assertTrue(g.station_allows())
        g.checkpoint()
        restored = st.Game(None)
        self.assertEqual(restored.p.station_police_remaining[0],0)
        self.assertTrue(restored.station_overwhelmed())
        self.assertEqual(restored.p.station_police_remaining[1],st.STATION_POLICE_CAPACITY)

    def test_exhausting_police_without_destroying_them_does_not_unlock_docking(self):
        g = self.game
        g.p.station_police_remaining[0] = 0
        g.station_hostilities[0] = True
        self.assertFalse(g.station_allows())

    def test_station_lasers_warn_then_fire_and_stop_outside_range(self):
        g = self.game
        g.mode = 'flight'
        g.p.station_police_defeated[0] = st.STATION_POLICE_CAPACITY
        g.station = [0.,0.,1500.]
        before = g.shield
        g.update_station_lasers(.1)
        self.assertIn('15 seconds',g.message)
        g.update_station_lasers(14)
        self.assertEqual(g.shield,before)
        g.update_station_lasers(1)
        self.assertLess(g.shield,before)
        self.assertEqual(g.enemy_shot['kind'],'station')
        g.station = [0.,0.,3000.]
        before = g.shield
        g.update_station_lasers(20)
        self.assertEqual(g.shield,before)

    def test_solar_radiation_drains_shields_then_hull(self):
        g = self.game
        g.mode = 'flight'
        g.speed = 0
        g.sun,g.heat = [0.,0.,400.],80.
        g.shield,g.p.hull = 100,100
        g.update(.1)
        self.assertLess(g.shield,100)
        self.assertEqual(g.p.hull,100)
        shielded_heat = g.heat
        g.shield,g.heat = 0,80.
        g.update(.1)
        self.assertGreater(g.heat,shielded_heat)
        self.assertLess(g.p.hull,100)

    def test_testing_credit_grant_preserves_snapshot_and_makes_backup(self):
        g = self.game
        g.p.fine = 1200
        g.checkpoint()
        before = json.loads(st.SAVE.read_text())
        st.grant_testing_credits(100000)
        after = json.loads(st.SAVE.read_text())
        self.assertEqual(after['credits'],before['credits']+100000)
        self.assertEqual(after['_session'],before['_session'])
        self.assertEqual(after['fine'],1200)
        backups = list(st.SAVE.parent.glob('save.before-test-grant-*.json'))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text()),before)

    def test_money_code_is_single_use_and_notes_persist(self):
        g = self.game
        g.key(ord('9'))
        self.assertEqual(g.mode,'money')
        g.key(ord('3'))
        g.text_input('star-test-100k')
        g.key(13)
        self.assertEqual(g.p.credits,100150)
        g.text_input('STAR-TEST-100K')
        g.key(13)
        self.assertEqual(g.p.credits,100150)
        self.assertIn('already redeemed',g.message)
        g.mouse_back()
        g.key(ord('-'))
        g.text_input('Buy medicine on Corvant.')
        g.key(13)
        g.text_input('Avoid hostile ports.')
        g.mouse_back()
        self.assertEqual(g.mode,'money')
        restored = st.Game(None)
        self.assertEqual(restored.p.notes,'Buy medicine on Corvant.\nAvoid hostile ports.')
        self.assertIn('STAR-TEST-100K',restored.p.redeemed_credit_codes)
        self.assertEqual(restored.p.credits,100150)

    def test_global_controls_open_without_triggering_context_actions(self):
        g = self.game
        g.mode = 'money'
        g.open_utility('help')
        self.assertEqual(g.mode,'help')
        self.assertEqual(g.help_return,'money')
        g.mouse_back()
        self.assertEqual(g.mode,'money')
        g.open_utility('menu')
        g.menu_selected = 1
        g.key(13)
        self.assertEqual(g.mode,'notes')
        self.assertEqual(g.notes_return,'money')
        g.mouse_back()
        self.assertEqual(g.mode,'money')

    def test_vms_docked_services_and_outfit_return_to_vms(self):
        g = self.game
        g.p.credits,g.p.fuel,g.p.hull = 1000,2,80
        g.open_hub('vms')
        self.assertEqual(g.session_mode(),'market')
        g.key(ord('f'))
        self.assertEqual(g.p.fuel,7)
        self.assertEqual(g.mode,'vms')
        g.key(ord('r'))
        self.assertEqual(g.p.hull,100)
        g.key(ord('u'))
        self.assertEqual(g.mode,'outfit')
        g.key(ord('u'))
        self.assertEqual(g.mode,'vms')
        g.key(ord('8'))
        self.assertEqual(g.engineering_location(),'market')
        g.mouse_back()
        self.assertEqual(g.mode,'vms')
        g.mouse_back()
        self.assertEqual(g.mode,'market')

    def test_inflight_hubs_preserve_flight_and_block_station_services(self):
        g = self.game
        g.mode = 'flight'
        g.p.fuel = 2
        g.open_hub('vms')
        self.assertEqual(g.session_mode(),'flight')
        g.key(ord('f'))
        self.assertEqual(g.p.fuel,2)
        g.key(ord('8'))
        self.assertEqual(g.engineering_location(),'flight')
        g.mouse_back()
        g.key(ord('9'))
        self.assertEqual(g.mode,'money')
        self.assertEqual(g.session_mode(),'flight')
        g.key(ord('3'))
        self.assertEqual(g.mode,'money')
        g.mouse_back()
        self.assertEqual(g.mode,'flight')
        g.open_hub('vms')
        g.open_navigation()
        self.assertEqual(g.mode,'map')
        self.assertEqual(g.map_return,'flight')

    def test_mine_purchase_explains_tech_block_and_works_at_eligible_port(self):
        p = self.game.p
        p.system,p.credits = 4,1000
        mine = next(i for i,item in enumerate(st.EQUIPMENT) if item[0] == 'mine')
        message = p.buy_equipment(mine)
        self.assertIn('Skarrow is tech 3',message)
        self.assertEqual((p.mines,p.credits),(0,1000))
        p.system = 0
        p.buy_equipment(mine)
        self.assertEqual((p.mines,p.credits),(1,925))
        for _ in range(3): p.buy_equipment(mine)
        cash = p.credits
        self.assertIn('full',p.buy_equipment(mine))
        self.assertEqual((p.mines,p.credits),(4,cash))

    def test_market_spread_and_stock(self):
        p = self.game.p
        cash, stock = p.credits, p.stock[0][0]
        p.trade(0,True)
        self.assertEqual(p.stock[0][0],stock-1)
        p.trade(0,False)
        self.assertEqual(p.stock[0][0],stock)
        self.assertEqual(p.credits,cash-st.quote(0,0)+st.quote(0,0,False))
        self.assertLess(p.credits,cash)

    def test_no_stock_no_money_no_cargo(self):
        p = self.game.p
        p.stock[0][0] = 0
        p.trade(0,True)
        self.assertEqual(p.credits,150)
        p.credits = 0
        p.trade(1,True)
        self.assertEqual(p.cargo,[0]*len(st.GOODS))
        p.trade(1,False)
        self.assertEqual(p.credits,0)

    def test_cargo_upgrade_and_capacity(self):
        p = self.game.p
        p.credits = 2000
        p.cargo[0] = 20
        p.trade(0,True)
        self.assertEqual(sum(p.cargo),20)
        p.buy_equipment(1)
        self.assertEqual(p.capacity,35)
        p.trade(0,True)
        self.assertEqual(sum(p.cargo),21)
        before = p.credits
        p.buy_equipment(1)
        self.assertEqual(p.credits,before)

    def test_tech_and_funds_restrictions(self):
        p = self.game.p
        p.credits = 10000
        p.buy_equipment(5)
        self.assertNotIn('docking',p.equipment)
        p.system = 1
        p.buy_equipment(5)
        self.assertIn('docking',p.equipment)
        p.credits = 0
        p.buy_equipment(7)
        self.assertNotIn('military',p.equipment)

    def test_fuel_is_paid_separately_from_repairs(self):
        p = self.game.p
        p.fuel,p.hull = 2,50
        p.repair()
        self.assertEqual((p.fuel,p.hull,p.credits),(2,100,132))
        p.refuel()
        self.assertEqual((p.fuel,p.credits),(7,117))
        p.fuel,p.credits = 0,0
        p.refuel()
        self.assertEqual(p.fuel,0)

    def test_jump_consumes_fuel_and_insufficient_jump_rejected(self):
        g = self.game
        g.launch(); g.key(ord('g')); g.target = 1
        fuel = g.p.fuel
        g.key(ord('h'))
        self.finish_jump(g)
        self.assertEqual(g.p.system,1)
        self.assertAlmostEqual(g.p.fuel,round(fuel-st.hyperspace_cost(st.distance(0,1)),5))
        g.p.fuel = 0
        g.key(ord('g')); g.target = 0; g.key(ord('h'))
        self.assertEqual(g.p.system,1)

    def test_docking_roll_tolerance_both_sides(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,66.]
        g.speed,g.dock_clearance = 15,120
        for angle in (-14,14):
            g.roll = g.station_angle + st.math.radians(angle)
            self.assertTrue(g.docking_safe())
        for angle in (-14.1,14.1):
            g.roll = g.station_angle + st.math.radians(angle)
            self.assertFalse(g.docking_safe())

    def test_slow_station_contact_is_gentle_but_fast_impact_is_dangerous(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,66.]
        g.speed,g.roll,g.shield,g.p.hull = 15,.7,0,100
        g.update(.1)
        self.assertEqual(g.mode,'flight')
        self.assertGreaterEqual(g.p.hull,90)
        g.station = [0.,0.,66.]
        g.speed = 150
        g.update(.1)
        self.assertEqual(g.mode,'dead')

    def test_manual_docking_requires_slot_alignment_and_slow_speed(self):
        g = self.game
        g.launch(); g.station = [0,0,66]; g.speed = 15; g.dock_clearance = 120
        g.update(.1)
        self.assertEqual(g.mode,'market')
        self.assertTrue(st.SAVE.exists())
        g.launch(); g.station = [0,0,66]; g.speed = 15; g.roll = 0.7
        g.update(.1)
        self.assertEqual(g.mode,'flight')
        self.assertLess(g.shield,100)
        self.assertEqual(g.speed,0)
        self.assertEqual(g.station[2],130)
        g.station = [0,0,66]; g.speed = 100; g.roll = g.station_angle
        g.update(.1)
        self.assertEqual(g.mode,'flight')

    def test_misaligned_centre_and_hostile_block_docking(self):
        g = self.game
        g.launch(); g.station = [25,0,66]; g.speed = 15
        g.update(.1)
        self.assertEqual(g.mode,'flight')
        g.station = [0,0,66]; g.speed = 15; g.roll = g.station_angle
        g.enemy = [0,0,500,6,0]
        g.update(.1)
        self.assertEqual(g.mode,'flight')

    def test_autodock_requires_purchase_and_completes_approach(self):
        g = self.game
        g.launch(); g.key(ord('c'))
        self.assertFalse(g.autodock)
        g.p.equipment = ['docking']
        g.station = [70,40,500]
        g.key(ord('c'))
        self.assertTrue(g.autodock)
        for _ in range(3000):
            g.update(.05)
            if g.mode == 'market': break
        self.assertEqual(g.mode,'market')
        self.assertEqual(g.p.hull,100)

    def test_autodock_cancels_on_manual_input(self):
        g = self.game
        g.launch(); g.p.equipment = ['docking']; g.key(ord('c'))
        g.key(ord('q'))
        self.assertFalse(g.autodock)

    def test_mining_requires_laser_and_scoops(self):
        g = self.game
        g.launch(); g.station = [400,0,1500]
        g.asteroids = [[0.,0.,240.,1]]; g.keys = {32}; g.speed = 0
        g.update(.01)
        self.assertEqual(len(g.asteroids),1)
        g.p.equipment = ['mining']; g.p.laser = 'mining'; g.cooldown = 0
        g.update(.01)
        self.assertEqual(len(g.asteroids),0)
        self.assertEqual(len(g.fragments),3)
        g.scoop()
        self.assertEqual(g.p.cargo[2],0)
        g.p.equipment.append('scoops'); g.scoop()
        self.assertEqual(g.p.cargo[2],1)
        self.assertEqual(len(g.fragments),2)
        g.p.save()
        p = st.Pilot(); self.assertTrue(p.load()); self.assertEqual(p.cargo[2],1)

    def test_full_hold_and_fast_ship_cannot_scoop(self):
        g = self.game
        g.p.equipment = ['scoops']; g.fragments = [[0,0,100]]
        g.p.cargo[0] = 20; g.scoop()
        self.assertEqual(len(g.fragments),1)
        g.p.cargo[0] = 0; g.speed = 70; g.scoop()
        self.assertEqual(len(g.fragments),1)

    def test_lasers_and_missiles(self):
        g = self.game
        g.launch(); g.speed = 0; g.station = [0.,0.,9000.]; g.enemy = [0,0,500,2,0]
        g.p.equipment = ['military']; g.p.laser = 'military'; g.keys = {32}
        g.update(.01)
        self.assertIsNone(g.enemy)
        self.assertEqual((g.p.kills,g.p.credits),(1,185))
        g.enemy = [0,0,500,6,0]; g.key(ord('m'))
        self.assertEqual(g.p.missiles,2)
        self.assertEqual(g.p.kills,2)
        g.p.missiles = 0; g.enemy = [0,0,500,6,0]; g.key(ord('m'))
        self.assertIsNotNone(g.enemy)
        g.p.credits = 1000; g.p.missiles = 4; g.p.buy_equipment(0)
        self.assertEqual(g.p.credits,1000)

    def test_solar_scooping_heat_and_retreat(self):
        g = self.game
        g.launch(); g.station = [1000,0,1500]; g.sun = [200,0,400]
        g.p.equipment = ['scoops']; g.p.fuel = 2; g.speed = 20
        g.update(1)
        self.assertGreater(g.p.fuel,2)
        self.assertGreater(g.heat,0)
        g.heat = 100; g.sun = [200,0,300]; g.update(.1)
        self.assertLess(g.shield,100)
        g.sun = [1000,0,1000]; heat = g.heat; g.update(.1)
        self.assertLess(g.heat,heat)

    def test_can_pass_station_at_safe_distance_and_reverse(self):
        g = self.game
        g.launch(); g.station = [500,0,66]; g.speed = 50
        g.update(1)
        self.assertEqual(g.station[2],16)
        self.assertEqual(g.shield,100)
        g.keys = {ord('s')}; g.update(1)
        self.assertLess(g.speed,0)

    def test_equipment_and_market_save_roundtrip(self):
        p = self.game.p
        p.equipment = ['cargo','mining','scoops']; p.laser = 'mining'
        p.cargo = [25]+[0]*(len(st.GOODS)-1); p.stock[0][1] = 2; p.missiles = 1
        p.save(); q = st.Pilot()
        self.assertTrue(q.load())
        self.assertEqual(vars(p),vars(q))

    def test_original_save_migrates_without_losing_progress(self):
        data = dict(credits=234,cargo=[1,2,0,0,0,0],system=1,fuel=3,hull=75,kills=4)
        st.SAVE.write_text(json.dumps(data))
        p = st.Pilot(); self.assertTrue(p.load())
        self.assertEqual(p.credits,234)
        self.assertEqual(p.equipment,[])
        self.assertEqual(p.cargo,data['cargo']+[0]*(len(st.GOODS)-6))

    def test_corrupt_save_does_not_partly_modify_pilot(self):
        st.SAVE.write_text(json.dumps(dict(credits=999,system=99)))
        p = st.Pilot(); self.assertFalse(p.load())
        self.assertEqual(p.credits,150)

    def test_search_and_coordinate_waypoints(self):
        g = self.game
        g.key(ord('g')); g.key(ord('/'))
        for c in 'corvant': g.key(ord(c))
        g.key(13)
        self.assertEqual(g.p.waypoint['system'],1)
        self.assertEqual(g.p.waypoint['position'],st.coordinates(1))
        g.key(ord('c'))
        for c in '5.2,5.6': g.key(ord(c))
        g.key(13)
        self.assertIsNone(g.p.waypoint['system'])
        self.assertEqual(g.p.waypoint['position'],[5.2,5.6])
        g.p.save(); p = st.Pilot(); self.assertTrue(p.load())
        self.assertEqual(p.waypoint,g.p.waypoint)

    def test_invalid_coordinates_do_not_change_lock(self):
        g = self.game
        g.key(ord('g')); g.key(13); original = g.p.waypoint.copy()
        g.key(ord('c'))
        for c in 'nan,22': g.key(ord(c))
        g.key(13)
        self.assertEqual(g.p.waypoint,original)
        self.assertEqual(g.map_input,'coordinates')
        g.mouse_back()
        self.assertIsNone(g.map_input)
        self.assertTrue(g.running)

    def test_cruise_costs_time_and_less_fuel_than_jump(self):
        g = self.game
        g.launch(); g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        dist = st.distance(0,1); initial = g.p.fuel
        g.begin_cruise()
        self.assertEqual(g.mode,'cruise')
        self.assertAlmostEqual(g.cruise['duration'],dist*st.CRUISE_SECONDS_PER_LY)
        g.update(1)
        self.assertEqual(g.mode,'cruise')
        self.assertGreater(g.p.position[0],st.coordinates(0)[0])
        g.update(10000)
        self.assertEqual(g.mode,'flight')
        self.assertEqual(g.p.system,1)
        self.assertAlmostEqual(initial-g.p.fuel,dist*.25)
        self.assertLess(dist*.25,st.hyperspace_cost(dist))

    def test_cancel_cruise_and_jump_from_deep_space(self):
        g = self.game
        g.launch(); g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.begin_cruise(); g.update(20); position = g.p.position[:]
        g.key(ord('t'))
        self.assertEqual(g.mode,'flight')
        self.assertTrue(g.p.deep_space)
        self.assertEqual(g.p.position,position)
        g.key(ord('c')); self.assertFalse(g.autodock)
        g.jump()
        self.finish_jump(g)
        self.assertFalse(g.p.deep_space)
        self.assertEqual(g.p.system,1)
        self.assertEqual(g.p.position,st.coordinates(1))

    def test_empty_coordinate_arrival_has_no_docking(self):
        g = self.game
        g.launch(); g.p.waypoint = dict(name='Marker',position=[2,4],system=None)
        g.jump()
        self.finish_jump(g)
        self.assertTrue(g.p.deep_space)
        g.dock()
        self.assertEqual(g.mode,'flight')
        g.key(ord('d'))
        self.assertIn('No station',g.message)

    def test_loaded_ship_handles_worse_and_cruise_takes_longer(self):
        light,heavy = self.game,st.Game(None)
        light.launch(); heavy.launch(); heavy.p.cargo[0] = 20
        for g in (light,heavy):
            g.station = [1000,0,5000]
            g.keys = {ord('w'),ord('e')}
            g.update(1)
        self.assertGreater(light.speed,heavy.speed)
        self.assertGreater(light.roll,heavy.roll)
        light.speed = heavy.speed = 80
        light.keys = heavy.keys = {ord('s')}
        light.update(.5); heavy.update(.5)
        self.assertGreater(heavy.speed,light.speed)
        for g in (light,heavy):
            g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
            g.begin_cruise()
        self.assertGreater(heavy.cruise['duration'],light.cruise['duration'])
        self.assertGreater(heavy.cruise['fuel'],light.cruise['fuel'])

    def test_fuel_exhaustion_stops_engine_and_jump_is_more_expensive(self):
        g = self.game
        g.launch(); g.p.fuel = .00001; g.keys = {ord('w')}
        g.update(1)
        self.assertEqual(g.p.fuel,0)
        g.update(1)
        self.assertEqual(g.speed,0)
        self.assertGreater(st.hyperspace_cost(2),2)

    def test_mines_arm_then_hit_enemy_and_can_hurt_owner(self):
        g = self.game
        g.launch(); g.speed = 0; g.p.mines = 1
        g.key(ord('b'))
        self.assertEqual(g.p.mines,0)
        g.enemy = [0,0,-90,6,0]
        g.update_mines(1)
        self.assertIsNotNone(g.enemy)
        g.update_mines(.6)
        self.assertIsNone(g.enemy)
        self.assertEqual(g.mine_objects,[])
        self.assertLess(g.shield,100)
        g.key(ord('b'))
        self.assertEqual(g.mine_objects,[])

    def test_jammer_and_cloak_require_purchase_and_have_cost(self):
        g = self.game
        g.launch(); g.key(ord('z')); g.key(ord('k'))
        self.assertFalse(g.cloaked); self.assertEqual(g.jamming,0)
        g.p.equipment = ['jammer','cloak']; fuel = g.p.fuel
        g.key(ord('z'))
        self.assertEqual(g.jamming,8)
        self.assertAlmostEqual(g.p.fuel,fuel-.05)
        fuel = g.p.fuel; g.key(ord('z'))
        self.assertEqual(g.p.fuel,fuel)
        g.key(ord('k')); g.speed = 0
        g.enemy = [0,0,500,6,1.99]
        g.update(.1)
        self.assertTrue(g.cloaked)
        self.assertEqual(g.shield,100)
        self.assertLess(g.p.fuel,fuel)
        g.keys = {32}; g.update(.1)
        self.assertFalse(g.cloaked)

    def test_customs_confiscates_and_police_kills_are_not_paid(self):
        g = self.game
        g.p.cargo[6] = 2
        with patch.object(st.random,'random',return_value=0):
            g.dock()
        self.assertEqual(g.p.cargo[6],0)
        self.assertEqual(g.p.fine,50)
        g.key(ord('p')); g.key(ord('4'))
        self.assertEqual((g.p.fine,g.p.credits),(0,100))
        g.enemy_kind = 'police'; g.enemy = [0,0,500,6,0]; g.destroy_enemy()
        self.assertEqual((g.p.fine,g.p.credits),(150,100))
        g.p.system = 4; g.p.cargo[6] = 2
        self.assertEqual(g.inspect_cargo(),'')
        self.assertEqual(g.p.cargo[6],2)

    def test_planet_size_changes_flyby_response_without_repeated_boost(self):
        g = self.game
        g.launch(); g.speed = 70; g.planet_radius = 150
        g.planet = [200,0,0]; g.update_planet(.1)
        g.planet = [700,0,0]; g.update_planet(.1)
        self.assertGreater(g.speed,70)
        speed = g.speed; g.update_planet(.1)
        self.assertEqual(g.speed,speed)
        g.speed = 70; g.planet_radius = 240; g.flyby_min = float('inf')
        g.planet = [250,0,0]; g.update_planet(.1)
        g.planet = [1000,0,0]; g.update_planet(.1)
        # Near-surface traversal must not be treated as a clean flyby.
        self.assertEqual(g.speed,70)

    def test_update_version_comparison_and_cached_notice(self):
        self.assertTrue(st.UpdateNotice.newer('v999.0.0'))
        self.assertFalse(st.UpdateNotice.newer(st.VERSION))
        self.assertFalse(st.UpdateNotice.newer('malicious-text'))
        cache = st.SAVE.parent/'update-check.json'
        cache.write_text(json.dumps(dict(checked=st.time.time(),version='v999.0.0')))
        notice = st.UpdateNotice()
        with patch.object(st.urllib.request,'urlopen',side_effect=AssertionError('should use cache')):
            notice.check()
        self.assertEqual(notice.latest,'v999.0.0')
        self.assertTrue(notice.checked)

    def test_update_failure_is_silent_and_does_not_change_save(self):
        self.game.p.save(); saved = st.SAVE.read_text()
        with patch.object(st.urllib.request,'urlopen',side_effect=OSError('offline')):
            notice = st.UpdateNotice(); notice.check()
        self.assertIsNone(notice.latest)
        self.assertEqual(st.SAVE.read_text(),saved)


    def test_fully_loaded_ship_autodocks_and_save_validates(self):
        g = self.game
        g.p.equipment = ['cargo','docking','jammer','cloak','mining']
        g.p.cargo[0] = 35
        g.launch(); g.station = [60,30,500]; g.key(ord('c'))
        for _ in range(4000):
            g.update(.05)
            if g.mode == 'market': break
        self.assertEqual(g.mode,'market')
        self.assertEqual(g.p.hull,100)
        p = st.Pilot(); self.assertTrue(p.load())
        self.assertEqual(p.cargo[0],35)

    def test_invalid_save_fields_and_migrated_stock(self):
        p = self.game.p
        p.save(); data = json.loads(st.SAVE.read_text())
        for value in ([],{},dict(data,position=[float('nan'),1]),dict(data,mines=7),dict(data,equipment=['unknown-module'])):
            st.SAVE.write_text(json.dumps(value))
            self.assertFalse(st.Pilot().load())
        legacy = {key:data[key] for key in ('credits','cargo','system','fuel','hull','kills')}
        legacy['cargo'] = [0]*6
        legacy['stock'] = [[12]*6 for _ in range(8)]
        st.SAVE.write_text(json.dumps(legacy))
        migrated = st.Pilot(); self.assertTrue(migrated.load())
        self.assertTrue(all(len(row) == len(st.GOODS) for row in migrated.stock))
        self.assertEqual(migrated.stock[0][:6],[12]*6)

    def test_number_row_controls_and_coordinate_input(self):
        g = self.game
        g.key(ord('1')); self.assertEqual(g.mode,'help')
        g.key(ord('1')); self.assertEqual(g.mode,'market')
        g.key(ord('2')); self.assertEqual(g.mode,'updates')
        g.key(ord('2')); self.assertEqual(g.mode,'market')
        g.key(ord('g')); g.key(ord('c'))
        for c in '1.2,3.4': g.key(ord(c))
        g.key(13)
        self.assertEqual(g.mode,'map')
        self.assertEqual(g.p.waypoint['position'],[1.2,3.4])
        g.key(ord('g')); g.launch(); g.key(ord('4'))
        self.assertTrue(g.rear_view)
        g.key(ord('4')); self.assertFalse(g.rear_view)

    def test_number_three_toggles_fullscreen(self):
        class FakeDisplay:
            is_fullscreen = False
            win = object()
            def fullscreen(self,window,flag): self.last_flag = flag
        g = self.game; g.d = FakeDisplay()
        g.key(ord('3'))
        self.assertTrue(g.d.is_fullscreen)
        self.assertEqual(g.d.last_flag,0x1001)
        g.key(ord('3'))
        self.assertFalse(g.d.is_fullscreen)
        self.assertEqual(g.d.last_flag,0)

    def test_rear_view_projects_only_objects_behind_ship(self):
        g = self.game
        self.assertIsNone(g.project([0,0,-500]))
        self.assertIsNotNone(g.project([0,0,500]))
        g.rear_view = True
        self.assertIsNotNone(g.project([0,0,-500]))
        self.assertIsNone(g.project([0,0,500]))
        self.assertLess(g.project([50,0,-500])[0],st.W/2)

    def test_rear_laser_purchase_save_and_firing_direction(self):
        g = self.game
        rear_index = next(i for i,e in enumerate(st.EQUIPMENT) if e[0] == 'rear')
        g.p.credits = 1000
        g.p.buy_equipment(rear_index)
        self.assertIn('rear',g.p.equipment)
        self.assertEqual(g.p.credits,400)
        g.p.save(); p = st.Pilot(); self.assertTrue(p.load())
        self.assertIn('rear',p.equipment)
        g.launch(); g.rear_view = True
        g.enemy = [0,0,-500,1,0]; g.fire_laser()
        self.assertIsNone(g.enemy)
        g.enemy = [0,0,500,1,0]; g.fire_laser()
        self.assertIsNotNone(g.enemy)
        g.rear_view = False; g.fire_laser()
        self.assertIsNone(g.enemy)

    def test_unfitted_rear_mount_cannot_fire_or_use_front_upgrade(self):
        g = self.game
        g.launch(); g.p.equipment = ['military']; g.p.laser = 'military'
        g.rear_view = True; g.enemy = [0,0,-500,6,0]
        g.fire_laser()
        self.assertEqual(g.enemy[3],6)
        self.assertEqual(g.laser_flash,0)
        self.assertIn('No rear laser',g.message)
        g.p.equipment.append('rear'); g.fire_laser()
        self.assertEqual(g.enemy[3],5)
        self.assertEqual(g.p.laser,'military')
        g.launch(); self.assertFalse(g.rear_view)

    def test_hyperspace_requires_continuous_hold_and_cancels_without_jump_fuel(self):
        g = self.game
        g.launch(); g.speed = 0
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        fuel = g.p.fuel
        g.keys = {ord('h')}; g.key(ord('h'))
        g.update(1.5)
        self.assertEqual(g.p.system,0)
        self.assertEqual(g.jump_charge['held'],1.5)
        self.assertEqual(g.p.fuel,fuel)
        g.keys.clear(); g.update(.01)
        self.assertIsNone(g.jump_charge)
        self.assertEqual(g.p.fuel,fuel)
        self.assertEqual(g.mode,'flight')
        g.keys = {ord('h')}; g.key(ord('h')); g.update(2.9)
        self.assertIsNotNone(g.jump_charge)
        g.update(.11)
        self.assertEqual(g.mode,'hyperspace')
        self.assertEqual(g.p.system,0)
        charged = g.p.fuel
        g.update(.5)
        self.assertEqual(g.p.fuel,charged)
        self.assertEqual(g.mode,'hyperspace')
        g.update(1.11)
        self.assertEqual(g.p.system,1)
        self.assertIsNotNone(g.arrival)
        self.assertEqual(g.arrival['name'],'Corvant')
        g.update(5.1)
        self.assertIsNone(g.arrival)

    def test_charge_rechecks_fuel_and_cannot_be_started_while_docked(self):
        g = self.game
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.jump(); self.assertIsNone(g.jump_charge)
        g.launch(); g.speed = 0; g.keys = {ord('h')}; g.jump()
        g.p.fuel = 0
        g.update(3)
        self.assertIsNone(g.jump_charge)
        self.assertEqual(g.mode,'flight')
        self.assertEqual(g.p.system,0)

    def test_hyperspace_snapshot_and_map_hold_then_warp_input_is_ignored(self):
        g = self.game
        g.launch(); g.speed = 0; g.key(ord('g')); g.target = 1
        g.keys = {ord('h')}; g.key(ord('h'))
        self.assertEqual(g.mode,'flight')
        g.p.waypoint = dict(name='Meridel',position=st.coordinates(2),system=2)
        self.finish_jump(g)
        self.assertEqual(g.p.system,1)
        self.assertIsNone(g.jump_charge)
        g.p.fuel = 7; g.speed = 0
        g.keys = {ord('h')}; g.key(ord('h')); g.update(3.1)
        self.assertEqual(g.mode,'hyperspace')
        g.key(ord('g')); g.key(ord('2'))
        self.assertEqual(g.mode,'hyperspace')

    def test_scanner_click_and_keyboard_select_and_clear_ship(self):
        g = self.game
        g.launch(); g.enemy = [350,0,-600,6,0]
        x,y = g.scanner_position(g.enemy)
        g.click(x,y)
        self.assertIs(g.ship_target,g.enemy)
        g.key(ord('5')); self.assertIsNone(g.ship_target)
        g.key(ord('5')); self.assertIs(g.ship_target,g.enemy)
        g.destroy_enemy(); self.assertIsNone(g.ship_target)
        g.click(0,0); self.assertIsNone(g.ship_target)

    def test_scanner_selects_navigation_and_remains_in_bounds(self):
        g = self.game
        g.launch(); g.station = [200,0,500]
        x,y = g.scanner_position(g.station)
        g.click(x,y)
        self.assertEqual(g.nav,'station')
        for obj in ([1e9,0,0],[0,0,1e9],[-1e9,0,-1e9]):
            x,y = g.scanner_position(obj)
            self.assertTrue(840 <= x <= 1070 and 110 <= y <= 220)

    def test_locked_course_and_local_navigation_resolve_correct_targets(self):
        g = self.game
        g.target = 1; g.lock_waypoint(); g.launch()
        obj,label = g.active_navigation()
        self.assertEqual(g.nav,'course')
        self.assertIn('Corvant',label)
        g.key(ord('d'))
        self.assertIs(g.active_navigation()[0],g.station)
        g.arrive(st.coordinates(1),1)
        g.nav = 'course'
        self.assertIs(g.active_navigation()[0],g.station)
        g.rear_view = False
        self.assertLess(g.camera_vector([0,0,-10])[2],0)
        g.rear_view = True
        self.assertGreater(g.camera_vector([0,0,-10])[2],0)

    def test_departure_fuel_warning_checks_locked_destination(self):
        g = self.game
        g.p.fuel = 0; g.key(ord('l'))
        self.assertEqual(g.mode,'launch_warning')
        g.mouse_back(); self.assertEqual(g.mode,'market')
        g.p.fuel = 2
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.key(ord('l')); self.assertEqual(g.mode,'launch_warning')
        g.key(ord('f')); self.assertEqual(g.p.fuel,7)
        self.assertEqual(g.mode,'market')
        g.key(ord('l')); self.assertEqual(g.mode,'departure')
        g.key(ord('l')); self.assertEqual(g.mode,'departure')
        g.update(2); g.key(ord('l')); self.assertEqual(g.mode,'flight')

    def test_docking_requires_requested_clearance_and_wanted_pilots_can_be_refused(self):
        g = self.game
        g.launch(); g.station = [0,0,200]; g.speed = 15
        self.assertFalse(g.docking_safe())
        g.key(ord('7')); self.assertEqual(g.docking_pending,2)
        g.speed = 0; g.update(2)
        self.assertGreater(g.dock_clearance,0)
        g.speed = 15; g.roll = g.station_angle
        self.assertTrue(g.docking_safe())
        g.p.fine = 200; self.assertTrue(g.docking_safe())  # lawful station: dock to surrender
        g.dock_clearance = 0; g.request_docking(); g.update(2)
        self.assertIn('ARRESTED',g.message)
        g.p.system = 4; g.station_hostilities[4] = True
        g.request_docking(); self.assertEqual(g.dock_clearance,0)
        self.assertIn('refused',g.message)

    def test_regulated_rescue_salvage_and_single_settlement(self):
        g = self.game
        g.p.cargo[0] = 20; g.p.credits = 200
        g.launch(); g.p.fuel = 0; g.open_distress()
        self.assertEqual(g.mode,'distress')
        self.assertTrue(g.rescue['covered'])
        terms = g.salvage_terms(25)
        self.assertEqual((terms['credits'],terms['tonnes']),(50,5))
        g.key(ord('a'))
        self.assertEqual(g.mode,'market')
        self.assertEqual((g.p.credits,g.p.cargo[0],g.p.fuel),(150,15,7))
        g.accept_rescue(); self.assertEqual(g.p.credits,150)
        p = st.Pilot(); self.assertTrue(p.load()); self.assertEqual(p.cargo[0],15)

    def test_deep_space_rescue_negotiation_and_refusal(self):
        g = self.game
        g.arrive([5,5],None); g.p.credits = 500
        g.open_distress(); self.assertFalse(g.rescue['covered'])
        self.assertEqual(len(g.rescue['offers']),3)
        offer = g.rescue['offers'][0]; initial = offer['percent']
        g.key(ord('n')); self.assertLess(offer['percent'],initial)
        g.key(ord('n')); final = offer['percent']; g.key(ord('n'))
        self.assertEqual(offer['percent'],final)
        self.assertEqual(offer['counters'],2)
        g.key(ord('r')); self.assertEqual(g.p.credits,500)
        self.assertEqual(g.mode,'flight')
        g.key(ord('6')); self.assertEqual(g.mode,'flight')
        g.rescue_cooldown = 0; g.key(ord('6'))
        self.assertEqual(g.mode,'distress')

    def test_rescue_zero_assets_and_criminal_destination(self):
        g = self.game
        g.arrive([4.1,2],None); g.p.credits = 0; g.p.fuel = 0; g.p.fine = 500
        g.open_distress(); target = g.rescue['destination']
        self.assertIn(st.PROFILES[target][0],('Anarchy','Feudal'))
        self.assertEqual(g.salvage_terms(65)['tonnes'],0)
        g.accept_rescue()
        self.assertEqual(g.mode,'market')
        self.assertEqual((g.p.fuel,g.p.credits),(7,0))
        self.assertEqual(g.p.system,target)

    def test_salvage_rounding_does_not_destroy_extra_cargo(self):
        g = self.game
        g.p.cargo = [1,1,1,0,0,0,0,0]
        for rate in (25,35,65):
            terms = g.salvage_terms(rate)
            self.assertEqual(sum(terms['cargo']),terms['tonnes'])
            self.assertEqual(terms['tonnes'],st.math.ceil(3*rate/100))
            self.assertTrue(all(a<=b for a,b in zip(terms['cargo'],g.p.cargo)))

    def test_maintenance_risk_increases_and_service_resets_it(self):
        g = self.game
        g.p.flights_since_service = 3; g.p.maintenance = 15; g.p.hull = 70
        first = g.breakdown_risk()
        g.p.flights_since_service += 1; g.p.maintenance += 2
        self.assertGreater(g.breakdown_risk(),first)
        g.p.credits = 1000; g.p.repair()
        self.assertEqual((g.p.hull,g.p.maintenance,g.p.flights_since_service),(100,0,0))
        self.assertEqual(g.breakdown_risk(),0)
        g.launch(); count = g.p.flights_since_service
        g.arrive(st.coordinates(1),1)
        self.assertEqual(g.p.flights_since_service,count)

    def test_breakdown_stops_drive_and_engineering_success_repairs(self):
        g = self.game
        g.launch(); g.breakdown_in = .1; g.keys = {ord('w')}
        g.update(.1)
        self.assertTrue(g.broken_down)
        self.assertEqual(g.speed,0)
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.jump(); self.assertIsNone(g.jump_charge)
        g.key(ord('8')); g.p.credits = 500
        with patch.object(st.random,'random',return_value=0): g.key(ord('r'))
        self.assertFalse(g.broken_down)
        self.assertEqual(g.p.credits,485)

    def test_engineering_failure_cooldown_persists_without_saving_flight_progress(self):
        g = self.game
        g.p.save(); g.launch(); g.p.hull = 50; g.p.credits = 500
        g.key(ord('8'))
        with patch.object(st.time,'time',return_value=10000),patch.object(st.random,'random',return_value=1):
            g.key(ord('r'))
            self.assertEqual(g.p.engineering_ready_at,11800)
            credits = g.p.credits; g.key(ord('r')); self.assertEqual(g.p.credits,credits)
        reloaded = st.Game(None)
        self.assertEqual(reloaded.p.engineering_ready_at,11800)
        self.assertEqual(reloaded.p.hull,100)
        with patch.object(st.time,'time',return_value=12000),patch.object(st.random,'random',return_value=1):
            g.key(ord('r'))
            self.assertEqual(g.p.engineering_ready_at,15600)

    def test_engineering_training_and_helping_disabled_ship(self):
        g = self.game
        g.p.credits = 1000; g.key(ord('8')); chance = g.engineering_chance()
        g.key(ord('t'))
        self.assertEqual(g.p.engineering_level,1)
        self.assertGreater(g.engineering_chance(),chance)
        g.key(ord('8')); g.launch(); g.speed = 0
        g.disabled_ship = dict(object=[0,0,200],hull=40)
        g.key(ord('5')); self.assertIs(g.ship_target,g.disabled_ship['object'])
        g.key(ord('8')); credits = g.p.credits
        with patch.object(st.random,'random',return_value=0): g.key(ord('h'))
        self.assertIsNone(g.disabled_ship)
        self.assertGreater(g.p.credits,credits)

    def test_mouse_clicks_rows_map_and_hold_release(self):
        g = self.game
        # Test public mouse dispatch independently of rendering.
        g.buttons = [(0,0,80,30,lambda:g.mouse_key(ord('l')))]
        g.click(20,15); self.assertEqual(g.mode,'departure')
        g.mouse_back(); g.key(ord('g')); g.buttons = []
        x,y = st.coordinates(1)
        g.click(60+x*60,155+y*39)
        self.assertEqual(g.p.waypoint['system'],1)
        g.launch(); g.speed = 0
        g.mouse_key(ord('h'),True)
        self.assertIn(ord('h'),g.keys)
        g.update(1); g.release_mouse(); g.update(.1)
        self.assertIsNone(g.jump_charge)
        self.assertNotIn(ord('h'),g.keys)


    def test_rescue_coverage_is_radial_and_does_not_change_equipment(self):
        g = self.game
        g.launch(); g.station = [4000,0,4000]; g.open_distress()
        self.assertFalse(g.rescue['covered'])
        g.key(ord('r')); g.rescue_cooldown = 0
        g.station = [3000,0,4000]; g.p.equipment = ['mining','rear']; g.p.hull = 10
        g.open_distress(); self.assertTrue(g.rescue['covered'])
        g.accept_rescue()
        self.assertEqual(g.p.equipment,['mining','rear'])
        self.assertEqual(g.p.hull,25)

    def test_insufficient_training_and_max_skill_do_not_take_credits(self):
        g = self.game
        g.key(ord('8')); g.p.credits = 0; g.key(ord('t'))
        self.assertEqual(g.p.engineering_level,0)
        g.p.engineering_level = 5; g.p.credits = 5000; g.key(ord('t'))
        self.assertEqual(g.p.credits,5000)
        g.key(ord('8')); g.launch(); g.key(ord('8')); g.key(ord('t'))
        self.assertEqual(g.p.credits,5000)

    def test_other_ship_repair_checks_target_range_and_parts(self):
        g = self.game
        g.launch(); g.speed = 0; g.disabled_ship = dict(object=[0,0,800],hull=20)
        g.ship_target = g.disabled_ship['object']; g.key(ord('8'))
        credits = g.p.credits; g.key(ord('h'))
        self.assertEqual(g.p.credits,credits)
        g.disabled_ship['object'][2] = 200; g.p.credits = 0; g.key(ord('h'))
        self.assertIsNotNone(g.disabled_ship)
        self.assertEqual(g.p.engineering_failures,0)

    def test_docking_clearance_expires_and_new_commander_has_no_old_repair_cooldown(self):
        g = self.game
        g.launch(); g.speed = 0; g.dock_clearance = .1; g.update(.2)
        self.assertEqual(g.dock_clearance,0)
        old_id = g.p.commander_id
        g.p.engineering_failures = 1; g.p.engineering_ready_at = st.time.time()+1800
        g.write_engineering_ledger(); g.mode = 'dead'; g.key(ord('n'))
        self.assertNotEqual(g.p.commander_id,old_id)
        self.assertEqual(g.p.engineering_ready_at,0)

    def test_fuel_warning_includes_approach_reserve_and_mouse_release_cancels_thrust(self):
        g = self.game
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.p.fuel = st.hyperspace_cost(st.distance(0,1))+.1
        g.request_launch(); self.assertEqual(g.mode,'launch_warning')
        g.mouse_back(); g.p.fuel = 7; g.launch(); g.speed = 0
        g.mouse_key(ord('w'),True); g.update(.1)
        self.assertGreater(g.speed,0)
        g.release_mouse(); self.assertNotIn(ord('w'),g.keys)


    def test_basic_trader_can_make_four_loaded_flights_before_neglect_risk(self):
        g = self.game
        g.p.cargo[0] = 20
        for flight in range(1,5):
            g.launch()
            self.assertEqual(g.p.flights_since_service,flight)
            self.assertEqual(g.breakdown_risk(),0)
            self.assertIsNone(g.breakdown_in)
        self.assertEqual(g.p.service_cost(),2)
        g.launch()
        self.assertGreater(g.breakdown_risk(),0)

    def test_service_quote_matches_discounted_charge_for_existing_wear(self):
        p = self.game.p
        p.hull,p.maintenance,p.credits = 50,20,100
        # 17.5 credits of hull work + 5 credits of maintenance, rounded once.
        self.assertEqual(p.service_cost(),23)
        p.repair()
        self.assertEqual((p.credits,p.hull,p.maintenance),(77,100,0))
        p.hull,p.maintenance,p.credits = 50,20,22
        p.repair()
        self.assertEqual((p.credits,p.hull,p.maintenance),(22,50,20))

    def test_swept_collision_catches_ship_crossed_between_frames(self):
        g = self.game
        g.launch(); g.station = [5000,0,5000]; g.asteroids=[]; g.speed=180
        g.disabled_ship = dict(object=[0,0,150.],hull=100)
        g.update(2)
        self.assertLess(g.shield,100)
        self.assertLess(g.disabled_ship['hull'],100)
        self.assertLess(g.speed,0)
        self.assertIn('COLLISION',g.message)
        self.assertIsNotNone(g.alert)
        shield = g.shield; g.update(.01)
        self.assertGreaterEqual(g.shield,shield)

    def test_ship_near_miss_does_not_count_as_collision(self):
        g=self.game
        g.launch(); g.station=[5000,0,5000];g.asteroids=[];g.speed=180
        g.disabled_ship=dict(object=[80,0,150.],hull=100)
        g.update(2)
        self.assertEqual(g.shield,100)
        self.assertEqual(g.disabled_ship['hull'],100)

    def test_clean_exit_restores_exact_danger_instead_of_station(self):
        g=self.game
        with patch.object(st.time,'time',return_value=10000):
            g.launch();g.speed=42;g.station=[300,20,4200.]
            g.enemy=[20,5,700.,4,1.2];g.shield=37;g.p.hull=65
            g.request_exit()
            resumed=st.Game(None)
        self.assertEqual(resumed.mode,'flight')
        self.assertEqual(resumed.speed,42)
        self.assertEqual(resumed.station,[300,20,4200.])
        self.assertEqual(resumed.enemy,[20,5,700.,4,1.2])
        self.assertEqual((resumed.shield,resumed.p.hull),(37,65))

    def test_unattended_enemy_can_destroy_ship_and_death_stays_saved(self):
        g=self.game
        with patch.object(st.time,'time',return_value=10000):
            g.launch();g.speed=0;g.shield=0;g.p.hull=20;g.station=[0.,0.,9000.]
            g.p.bank_balance=200;g.enemy=[0,0,500.,6,1.9]
            g.request_exit()
        with patch.object(st.time,'time',return_value=10010): resumed=st.Game(None)
        self.assertEqual(resumed.mode,'dead')
        self.assertEqual(resumed.p.hull,0)
        self.assertEqual(resumed.p.bank_balance,200)
        with patch.object(st.time,'time',return_value=10011): again=st.Game(None)
        self.assertEqual(again.mode,'dead')
        again.key(ord('r'))
        self.assertEqual(again.mode,'market')
        self.assertEqual(again.p.bank_balance,100)
        self.assertEqual(again.p.cargo,[0]*len(st.GOODS))

    def test_autosave_includes_current_simulation(self):
        g=self.game
        g.launch();g.speed=0;g.shield=30;g.update(2.1)
        data=json.loads(st.SAVE.read_text())
        self.assertIn('_session',data)
        self.assertAlmostEqual(data['_session']['state']['shield'],g.shield)
        self.assertEqual(data['_session']['mode'],'flight')

    def test_bank_money_and_station_cargo_survive_salvage(self):
        g=self.game
        g.p.credits=1000;g.key(ord('9'));g.key(ord('1'))
        self.assertEqual(g.mode,'bank')
        g.bank_amount=500;g.key(ord('d'))
        self.assertEqual((g.p.credits,g.p.bank_balance),(500,500))
        g.key(ord('r'));self.assertEqual(g.p.credits,450)
        g.p.cargo[0]=10;g.key(ord('s'))
        self.assertEqual(g.p.storage[0]['cargo'][0],1)
        g.key(ord('9'));g.launch();g.open_distress();g.accept_rescue()
        self.assertEqual(g.p.bank_balance,500)
        self.assertEqual(g.p.storage[0]['cargo'][0],1)
        self.assertLess(g.p.credits,450)

    def test_station_storage_is_local_and_expired_rent_preserves_retrieval(self):
        g=self.game
        g.p.credits=200;g.mode='bank';g.buy_storage(True)
        g.p.cargo[0]=2;g.transfer_storage(True)
        g.p.storage[0]['rented_until']=1
        self.assertEqual(g.storage_capacity(),0)
        g.transfer_storage(True)
        self.assertEqual(g.p.storage[0]['cargo'][0],1)
        g.transfer_storage(False)
        self.assertEqual(g.p.storage[0]['cargo'][0],0)
        g.p.system=1
        self.assertEqual(g.p.storage[1]['cargo'][0],0)
        g.p.credits=1000;g.buy_storage(False)
        self.assertEqual(g.storage_capacity(),100)
        cash=g.p.credits;g.buy_storage(False)
        self.assertEqual(g.p.credits,cash)

    def test_important_alert_expires_and_repeated_text_does_not_restart_it(self):
        g=self.game
        g.message='Fuel exhausted. Press 6 for help.'
        self.assertIsNotNone(g.alert)
        g.update(1)
        remaining=g.alert['remaining']
        g.message='Fuel exhausted. Press 6 for help.'
        self.assertEqual(g.alert['remaining'],remaining)
        g.update(5)
        self.assertIsNone(g.alert)


    def test_nested_station_menus_save_as_docked(self):
        g=self.game
        g.key(ord('1'));g.key(ord('2'))
        self.assertEqual(g.mode,'updates')
        self.assertEqual(g.session_mode(),'market')
        g.request_exit()
        with patch.object(st.time,'time',return_value=st.time.time()+500): resumed=st.Game(None)
        self.assertEqual(resumed.mode,'market')

    def test_bank_and_owned_bays_roundtrip_with_original_pilot_fields(self):
        p=self.game.p
        p.bank_balance=1234;p.storage[2]['owned']=True;p.storage[2]['cargo'][3]=50
        p.save();q=st.Pilot();self.assertTrue(q.load())
        self.assertEqual(q.bank_balance,1234)
        self.assertEqual(q.storage[2]['cargo'][3],50)
        self.assertTrue(q.storage[2]['owned'])

    def test_unattended_autodock_completes_legitimately(self):
        g=self.game
        with patch.object(st.time,'time',return_value=10000):
            g.p.equipment=['docking'];g.launch();g.station=[20,5,500.]
            g.key(ord('c'));g.request_exit()
        with patch.object(st.time,'time',return_value=10090): resumed=st.Game(None)
        self.assertEqual(resumed.mode,'market')
        self.assertEqual(resumed.p.hull,100)


    def test_handbook_keyboard_tabs_preserve_underlying_flight(self):
        g=self.game
        g.launch();g.key(ord('1'))
        self.assertEqual(g.mode,'help')
        g.key(st.RIGHT);self.assertEqual(g.help_page,1)
        g.key(st.LEFT);self.assertEqual(g.help_page,0)
        self.assertEqual(g.session_mode(),'flight')
        g.key(ord('1'));self.assertEqual(g.mode,'flight')

    def test_prolonged_unattended_safe_drift_uses_salvage_not_free_rollback(self):
        g=self.game
        with patch.object(st.time,'time',return_value=10000):
            g.launch();g.station=[0,0,300.];g.speed=0
            g.p.credits=200;g.p.bank_balance=100;g.request_exit()
        with patch.object(st.time,'time',return_value=13000): resumed=st.Game(None)
        self.assertEqual(resumed.mode,'market')
        self.assertEqual(resumed.p.credits,150)
        self.assertEqual(resumed.p.bank_balance,100)


class CommanderStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name) / 'save.json'
        self.game = st.Game(None)

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def test_rank_ladder_counts_kills_trade_and_jumps(self):
        p = self.game.p
        self.assertEqual(p.rank,'Newbie')
        self.assertEqual(p.next_rank,(50,'Greenhorn'))
        p.kills = 2
        self.assertEqual(p.rank,'Greenhorn')
        p.kills, p.trade_profit, p.jumps = 0, 2500, 0
        self.assertEqual(p.rank,'Operator')
        p.trade_profit, p.jumps = 0, 150
        self.assertEqual(p.rank,'Hand')
        p.kills = 2000
        self.assertEqual((p.rank,p.next_rank),('Legend',None))

    def test_trade_profit_uses_purchase_price_and_ignores_losses(self):
        p = self.game.p
        p.credits = 1000
        p.system = min(range(8),key=lambda i:st.quote(i,3,True))
        p.trade(3,True); p.trade(3,True)
        paid = st.quote(p.system,3,True)
        self.assertEqual(p.cargo_paid[3],paid*2)
        p.trade(3,False)
        self.assertEqual(p.trade_profit,0)
        p.system = next(i for i in range(8) if st.quote(i,3,False) > paid)
        p.trade(3,False)
        self.assertEqual(p.trade_profit,st.quote(p.system,3,False)-paid)
        self.assertEqual(p.cargo_paid[3],0)

    def test_cargo_without_purchase_price_counts_as_full_profit(self):
        p = self.game.p
        p.cargo[2] = 1
        p.trade(2,False)
        self.assertEqual(p.trade_profit,st.quote(p.system,2,False))

    def test_hyperspace_arrival_counts_a_jump(self):
        g = self.game
        g.mode = 'hyperspace'
        g.jump_warp = dict(destination=dict(name='Test',position=st.coordinates(1),system=1),elapsed=1.6)
        g.update(.01)
        self.assertEqual(g.p.jumps,1)

    def test_wanted_level_from_fines_and_hostile_stations(self):
        g = self.game
        self.assertEqual(g.wanted_level(),0)
        g.p.fine = 150
        self.assertEqual(g.wanted_level(),2)
        g.p.fine = 5000
        self.assertEqual(g.wanted_level(),5)
        g.p.fine = 300
        g.station_hostilities[1] = True
        g.station_hostile_until[1] = st.time.time()+600
        self.assertEqual(g.wanted_level(),4)

    def test_commander_name_entry_saves_and_prefers_server_account(self):
        g = self.game
        g.open_utility('rename')
        g.text_input('  Kestrel\nOne')
        g.key(13)
        self.assertEqual(g.p.name,'KestrelOne')
        self.assertEqual(json.loads(st.SAVE.read_text())['name'],'KestrelOne')
        self.assertEqual(g.commander_name(),'KestrelOne')
        g.remote_save = type('Remote',(),dict(player_name='iMacPilot'))()
        self.assertEqual(g.commander_name(),'KestrelOne')
        g.p.name = ''
        self.assertEqual(g.commander_name(),'iMacPilot')

    def test_older_saves_load_with_new_career_fields(self):
        g = self.game
        g.p.kills = 3
        g.p.save()
        data = json.loads(st.SAVE.read_text())
        for key in ('name','trade_profit','cargo_paid','jumps'): del data[key]
        st.SAVE.write_text(json.dumps(data))
        pilot = st.Pilot()
        self.assertTrue(pilot.load())
        self.assertEqual((pilot.kills,pilot.trade_profit,pilot.jumps,pilot.name,pilot.rank),(3,0,0,'','Greenhorn'))

    def test_saved_waypoints_and_courses_use_renamed_systems(self):
        g = self.game
        g.p.waypoint = dict(name='Corvant',position=st.coordinates(1),system=1)
        g.mode = 'hyperspace'
        g.jump_warp = dict(destination=dict(name='Corvant',position=st.coordinates(1),system=1),elapsed=0.)
        g.checkpoint()
        raw = st.SAVE.read_text().replace('Corvant','Zaonce')
        st.SAVE.write_text(raw)
        restored = st.Game(None)
        self.assertEqual(restored.p.waypoint['name'],'Corvant')
        self.assertEqual(restored.jump_warp['destination']['name'],'Corvant')

    def test_invalid_career_fields_are_rejected(self):
        for key,value in (('name','x'*25),('trade_profit',-1),('jumps',1.5),('cargo_paid',[0])):
            with self.subTest(key=key):
                pilot = st.Pilot()
                setattr(pilot,key,value)
                with self.assertRaises(ValueError): pilot.validate()


class LawAndPrisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name) / 'save.json'
        self.game = st.Game(None)
        self.game.spawn = 10000

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

    def test_stray_hits_warn_and_fine_before_police(self):
        g = self.game
        g.launch()
        for hit in range(1,st.STRAY_SHOT_LIMIT+1):
            g.station_struck()
            self.assertFalse(g.station_hostilities[0])
            self.assertIn('STATION CONTROL',g.message)
            self.assertEqual(g.p.fine,hit*st.STRAY_SHOT_FINE)
        self.assertIsNone(g.enemy)
        g.station_struck()
        self.assertTrue(g.station_hostilities[0])
        self.assertEqual(g.enemy_kind,'police')

    def test_stray_hit_count_resets_after_quiet_period(self):
        g = self.game
        g.launch()
        for _ in range(st.STRAY_SHOT_LIMIT): g.station_struck()
        g.station_strike_at -= st.STRAY_SHOT_RESET+1
        g.station_struck()
        self.assertFalse(g.station_hostilities[0])
        self.assertEqual(g.station_strikes,1)

    def test_lawful_station_holds_launch_until_fines_paid(self):
        g = self.game
        g.p.fine, g.p.credits = 50, 500
        g.key(ord('l'))
        self.assertEqual(g.mode,'market')
        self.assertIn('withheld',g.message)
        g.key(ord('9')); g.key(ord('4')); g.key(ord('9'))
        self.assertEqual((g.mode,g.p.fine),('market',0))
        g.key(ord('l'))
        self.assertIn(g.mode,('departure','launch_warning'))

    def test_anarchy_station_does_not_hold_launch(self):
        g = self.game
        g.p.system, g.p.fine = 4, 50
        g.request_launch()
        self.assertIn(g.mode,('departure','launch_warning'))

    def test_minor_fines_are_collected_on_arrest_without_prison(self):
        g = self.game
        g.launch()
        g.p.fine, g.p.credits = 150, 400
        g.p.cargo[6] = 2
        g.dock()
        self.assertEqual(g.mode,'market')
        self.assertIsNone(g.p.prison)
        self.assertEqual((g.p.fine,g.p.credits,g.p.cargo[6]),(0,250,0))
        self.assertIn('ARRESTED',g.message)

    def test_destroying_police_brings_a_sentence(self):
        g = self.game
        g.launch()
        g.station_hostilities[0] = True
        for _ in range(st.STATION_POLICE_CAPACITY):
            g.dispatch_station_police(); g.destroy_enemy()
        g.p.credits = 100000
        g.dock()
        self.assertEqual(g.mode,'prison')
        self.assertEqual(g.p.prison['days'],st.PRISON_MAX_DAYS)
        self.assertEqual(g.p.fine,0)
        self.assertFalse(g.station_hostilities[0])
        self.assertEqual(g.p.station_police_remaining[0],st.STATION_POLICE_CAPACITY)

    def test_unpaid_fines_add_prison_days(self):
        g = self.game
        g.launch()
        g.p.fine, g.p.credits, g.p.bank_balance = 600, 50, 50
        g.dock()
        self.assertEqual(g.p.prison['days'],2)
        self.assertEqual((g.p.credits,g.p.bank_balance),(0,0))

    def test_prison_survives_reload_and_releases_when_time_is_served(self):
        g = self.game
        g.launch(); g.p.fine = 400; g.dock()
        self.assertEqual(g.mode,'prison')
        g.key(ord('l'))
        self.assertEqual(g.mode,'prison')
        g.checkpoint()
        restored = st.Game(None)
        self.assertEqual(restored.mode,'prison')
        restored.p.prison['release_at'] = st.time.time()-1
        restored.update(.01)
        self.assertEqual(restored.mode,'market')
        self.assertIsNone(restored.p.prison)

    def test_prison_work_once_per_day_shortens_sentence(self):
        g = self.game
        g.launch(); g.p.fine = 400; g.dock()
        before = g.p.prison['release_at']
        g.key(ord('w'))
        self.assertAlmostEqual(g.p.prison['release_at'],before-st.PRISON_WORK_SECONDS)
        g.key(ord('w'))
        self.assertAlmostEqual(g.p.prison['release_at'],before-st.PRISON_WORK_SECONDS)

    def test_bribe_costs_money_and_sometimes_escapes(self):
        g = self.game
        g.launch(); g.p.fine = 400; g.dock()
        g.p.credits, g.p.crymto = 0, 300
        with patch('star_trader.random.random',return_value=.5): g.key(ord('b'))
        self.assertEqual((g.mode,g.p.crymto),('prison',100))
        g.key(ord('b'))
        self.assertEqual(g.p.crymto,100)  # one attempt per day
        g.p.prison['bribe_day'] = -1
        g.p.credits = 250
        with patch('star_trader.random.random',return_value=.05): g.key(ord('b'))
        self.assertIsNone(g.p.prison)
        self.assertEqual(g.p.credits,50)
        self.assertTrue(g.station_hostilities[0])
        self.assertGreaterEqual(g.p.fine,500)
        self.assertEqual(g.mode,'departure')

    def test_bribe_needs_money(self):
        g = self.game
        g.launch(); g.p.fine = 400; g.dock()
        g.p.credits = g.p.crymto = 0
        g.key(ord('b'))
        self.assertEqual(g.p.prison['bribe_day'],-1)

    def test_surrender_stands_police_down_until_docked(self):
        g = self.game
        g.launch()
        g.station_struck(); g.station_strikes = st.STRAY_SHOT_LIMIT; g.station_struck()
        self.assertEqual(g.enemy_kind,'police')
        g.dispatch_station_police() if g.enemy is None else None
        g.destroy_enemy()
        g.dispatch_station_police()
        reserve = g.p.station_police_remaining[0]
        g.key(ord('7'))
        self.assertTrue(g.surrendering)
        self.assertIsNone(g.enemy)
        self.assertEqual(g.p.station_police_remaining[0],reserve+1)
        g.p.credits = 10000  # fines paid in full, so only the police kill and hostility count
        g.security_dispatch = 0
        g.update_station_security(1)
        self.assertIsNone(g.enemy)
        g.dock()
        self.assertEqual(g.mode,'prison')
        self.assertEqual(g.p.prison['days'],2)  # one police kill plus hostility
        self.assertFalse(g.surrendering)

    def test_firing_or_leaving_voids_surrender(self):
        g = self.game
        g.launch()
        g.station_hostilities[0] = True
        g.request_docking()
        self.assertTrue(g.surrendering)
        g.station = [0.,0.,5000.]
        g.fire_laser()
        self.assertFalse(g.surrendering)
        self.assertIn('VOID',g.message)
        g.enemy = None
        g.update_station_security(.1)
        self.assertEqual(g.enemy_kind,'police')
        g.enemy = None; g.request_docking()
        self.assertTrue(g.surrendering)
        g.station = [0.,0.,20000.]
        g.update_station_security(.1)
        self.assertFalse(g.surrendering)

    def test_anarchy_station_will_not_take_surrender(self):
        g = self.game
        g.p.system = 4
        g.launch()
        g.station_hostilities[4] = True
        g.request_docking()
        self.assertFalse(g.surrendering)
        self.assertIn('refused',g.message)

    def test_bank_presets_and_custom_amount(self):
        g = self.game
        g.mode = 'bank'
        g.p.credits = 5000
        g.choose_bank_amount(1000); g.key(ord('d'))
        self.assertEqual((g.p.credits,g.p.bank_balance),(4000,1000))
        g.bank_custom = ''
        for c in '2a5x0': g.text_input(c)
        g.key(ord('9')); g.key(ord('2'))  # shortcuts are paused while typing
        self.assertEqual((g.mode,g.bank_custom),('bank','250'))
        g.key(8); g.text_input('7'); g.key(13)
        self.assertEqual((g.bank_amount,g.bank_custom),(257,None))
        g.key(ord('w'))
        self.assertEqual((g.p.credits,g.p.bank_balance),(4257,743))
        g.bank_custom = ''; g.key(13)
        self.assertEqual(g.bank_amount,257)

    def test_no_pirates_inside_a_lawful_station_patrol_zone(self):
        g = self.game
        g.launch(); g.speed = 0
        g.station = [0.,0.,3000.]
        self.assertTrue(g.in_patrol_zone())
        g.spawn = 0
        g.update(.01)
        self.assertIsNone(g.enemy)
        g.enemy_kind = 'pirate'; g.enemy = [0.,0.,800.,6,0.]
        g.update(.01)
        self.assertIsNone(g.enemy)
        self.assertIn('patrol zone',g.message)
        g.station = [0.,0.,st.PATROL_RADIUS+500.]
        self.assertFalse(g.in_patrol_zone())
        g.spawn = 0; g.update(.01)
        self.assertEqual(g.enemy_kind,'pirate')
        self.assertIsNotNone(g.enemy)

    def test_lawless_or_hostile_stations_offer_no_patrol_zone(self):
        g = self.game
        g.launch(); g.station = [0.,0.,2000.]
        g.station_hostilities[0] = True
        self.assertFalse(g.in_patrol_zone())
        g.station_hostilities[0] = False
        g.p.system = 4
        self.assertFalse(g.in_patrol_zone())

    def test_invalid_prison_record_is_rejected(self):
        pilot = st.Pilot()
        pilot.prison = dict(system=0,days=9,start=0.,release_at=1.,bribe_day=-1,work_day=-1)
        with self.assertRaises(ValueError): pilot.validate()


if __name__ == '__main__':
    unittest.main()
