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

    def tearDown(self):
        st.SAVE = self.original_save
        self.tmp.cleanup()

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
        self.assertEqual((p.fuel,p.hull,p.credits),(2,100,125))
        p.refuel()
        self.assertEqual((p.fuel,p.credits),(7,110))
        p.fuel,p.credits = 0,0
        p.refuel()
        self.assertEqual(p.fuel,0)

    def test_jump_consumes_fuel_and_insufficient_jump_rejected(self):
        g = self.game
        g.launch(); g.key(ord('g')); g.target = 1
        fuel = g.p.fuel
        g.key(ord('h'))
        self.assertEqual(g.p.system,1)
        self.assertAlmostEqual(g.p.fuel,round(fuel-st.hyperspace_cost(st.distance(0,1)),5))
        g.p.fuel = 0
        g.key(ord('g')); g.target = 0; g.key(ord('h'))
        self.assertEqual(g.p.system,1)

    def test_manual_docking_requires_slot_alignment_and_slow_speed(self):
        g = self.game
        g.launch(); g.station = [0,0,66]; g.speed = 15
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
        self.assertFalse(g.p.deep_space)
        self.assertEqual(g.p.system,1)
        self.assertEqual(g.p.position,st.coordinates(1))

    def test_empty_coordinate_arrival_has_no_docking(self):
        g = self.game
        g.launch(); g.p.waypoint = dict(name='Marker',position=[2,4],system=None)
        g.jump()
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


if __name__ == '__main__':
    unittest.main()
