"""Offline regression checks. Run with python3 -m unittest -v test_game."""
import json
import os
os.environ["STAR_TRADER_NO_UPDATE_CHECK"] = "1"
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
import star_trader as st


class GameplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name) / 'save.json'
        self.game = st.Game(None)
        self.game.spawn = 10000

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
        g.p.waypoint = dict(position=st.coordinates(1),system=1,name='Zaonce')
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

    def test_station_fire_immediately_hostile_once_and_survives_reload(self):
        g = self.game
        g.mode = 'flight'
        g.station = [0.,0.,600.]
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
        g.key(27)
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
        self.assertTrue(g.station_hostilities[0])
        self.assertEqual(g.enemy[3],6)
        g.station_hostilities[0] = False
        g.station = [0.,0.,1500.]
        g.enemy = [0.,0.,1000.,6,0]
        g.asteroids = [[0.,0.,300.,3]]
        g.fire_laser()
        self.assertFalse(g.station_hostilities[0])
        self.assertEqual(g.enemy[3],6)

    def test_incoming_enemy_fire_has_visible_timed_beam(self):
        g = self.game
        g.mode = 'flight'
        g.speed = 0
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
        g.key(27)
        self.assertEqual(g.mode,'map')
        g.cursor_mode = True
        g.map_cursor = [5.,5.]
        g.key(ord('i'))
        self.assertEqual(g.mode,'map')
        self.assertIn('No planet',g.message)

    def test_feedback_draft_saves_offline_without_attaching_save(self):
        g = self.game
        g.key(ord('0'))
        self.assertEqual(g.mode,'feedback')
        self.assertEqual(g.session_mode(),'market')
        self.assertFalse(g.save_feedback())
        g.text_input('Buttons fail at 150% scaling. Café test.')
        self.assertTrue(g.save_feedback())
        body = Path(g.feedback_path).read_text()
        self.assertIn(st.VERSION,body)
        self.assertIn('Café',body)
        self.assertNotIn(g.p.commander_id,body)
        g.key(27)
        self.assertEqual(g.mode,'market')

    def test_feedback_browser_opens_prefilled_issue_and_preserves_local_copy(self):
        g = self.game
        g.key(ord('0'))
        g.feedback_type = 'suggestion'
        g.text_input('Please add escorts & convoys')
        with patch.object(st.webbrowser,'open',return_value=True) as browser:
            g.open_feedback_issue()
        url = browser.call_args.args[0]
        self.assertTrue(url.startswith('https://github.com/womb4t/star-trader/issues/new?'))
        fields = st.urllib.parse.parse_qs(st.urllib.parse.urlsplit(url).query)
        self.assertTrue(fields['title'][0].startswith('Suggestion:'))
        self.assertIn('escorts & convoys',fields['body'][0])
        self.assertTrue(Path(g.feedback_path).exists())
        with patch.object(st.webbrowser,'open',return_value=False): g.open_feedback_issue()
        self.assertIn('saved locally',g.message)

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
        g.launch(); g.speed = 0; g.enemy = [0,0,500,2,0]
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
        for c in 'zaonce': g.key(ord(c))
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
        g.key(27)
        self.assertIsNone(g.map_input)
        self.assertTrue(g.running)

    def test_cruise_costs_time_and_less_fuel_than_jump(self):
        g = self.game
        g.launch(); g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        g.launch(); g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
            g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        g.key(ord('p'))
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
        g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        self.assertEqual(g.arrival['name'],'Zaonce')
        g.update(5.1)
        self.assertIsNone(g.arrival)

    def test_charge_rechecks_fuel_and_cannot_be_started_while_docked(self):
        g = self.game
        g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        g.p.waypoint = dict(name='Diso',position=st.coordinates(2),system=2)
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
        self.assertIn('Zaonce',label)
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
        g.key(27); self.assertEqual(g.mode,'market')
        g.p.fuel = 2
        g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        g.p.fine = 200; self.assertFalse(g.docking_safe())
        g.request_docking(); self.assertEqual(g.dock_clearance,0)
        self.assertIn('refused',g.message)
        g.p.system = 4; g.request_docking(); self.assertEqual(g.docking_pending,2)

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
        g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
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
        g.key(27); g.key(ord('g')); g.buttons = []
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
        g.p.waypoint = dict(name='Zaonce',position=st.coordinates(1),system=1)
        g.p.fuel = st.hyperspace_cost(st.distance(0,1))+.1
        g.request_launch(); self.assertEqual(g.mode,'launch_warning')
        g.key(27); g.p.fuel = 7; g.launch(); g.speed = 0
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
            g.launch();g.speed=0;g.shield=0;g.p.hull=20
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
        g.p.credits=1000;g.key(ord('9'))
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



if __name__ == '__main__':
    unittest.main()
