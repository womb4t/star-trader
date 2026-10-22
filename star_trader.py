#!/usr/bin/env python3
"""STAR TRADER — an original Elite-inspired game. Python 3 + system SDL2/SDL2_ttf.
Run: python3 star_trader.py   Test: python3 star_trader.py --self-test
"""
import argparse
import ctypes as C
import ctypes.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import threading
import urllib.request
import urllib.parse
import uuid
import tempfile
import fcntl
import shutil
import subprocess
import textwrap

VERSION = '0.8.2'
HOSTILITY_COOLDOWN_SECONDS = 30*60
STATION_POLICE_CAPACITY = 6
# Career points needed for each commander rank: kills, trade profit and hyperspace jumps all count.
RANKS = [(0,'Newbie'),(50,'Greenhorn'),(250,'Operator'),(750,'Hand'),(2000,'Veteran'),(5000,'Ace'),(12000,'Vanguard'),(30000,'Legend')]
# Outstanding fines (cr) at which the wanted level reaches 1..5; each hostile station adds one more.
WANTED_FINES = [1,100,300,600,1000]
# Stray fire: the first few hits on a station bring a comms warning and a fine, not police.
STRAY_SHOT_LIMIT, STRAY_SHOT_FINE, STRAY_SHOT_RESET = 3, 50, 300
# Prison: one sentence day lasts one real hour and keeps passing while the game is closed.
PRISON_DAY_SECONDS, PRISON_MAX_DAYS, PRISON_BRIBE, PRISON_WORK_SECONDS = 3600, 7, 200, 1800
# Lawful stations patrol this radius (m): pirates do not attack inside it.
PATROL_RADIUS = 5000
# The sun's visible radius (m) and the altitude band above it where fitted scoops collect fuel.
SUN_RADIUS, SCOOP_ALTITUDE, SCOOP_SPEEDS = 220, 280, (10, 60)
TRADE_LOG_SIZE = 60
DOCK_ROLL_TOLERANCE = math.radians(14)
CRUISE_SECONDS_PER_LY = 45
W, H = 1100, 760
GOODS = ['Food', 'Textiles', 'Ore', 'Machinery', 'Medicine', 'Computers', 'Narcotics', 'Unlicensed Arms', 'Gold', 'Silver']
BASE = [8, 15, 24, 48, 65, 90, 150, 110, 260, 95]
ILLEGAL = (6, 7)
# Precious metals: scarce at stations, and found in the occasional rich asteroid.
METALS = (8, 9)
TECH = [5, 10, 4, 8, 3, 12, 2, 7]
# key, label, cost, minimum technology, effect
EQUIPMENT = [
    ('missile', 'Homing missile', 30, 1, 'Single-use weapon; maximum four aboard'),
    ('cargo', 'Large cargo bay', 400, 2, 'Increases capacity from 20 to 35 tonnes'),
    ('beam', 'Beam laser', 1000, 4, 'Faster combat laser'),
    ('scoops', 'Fuel / cargo scoops', 525, 5, 'Collect ore fragments and skim the sun'),
    ('mining', 'Mining laser', 800, 5, 'Break asteroids into collectible ore'),
    ('docking', 'Docking computer', 1500, 8, 'C engages automatic approach and docking'),
    ('energy', 'Extra energy unit', 1500, 8, 'Doubles shield regeneration'),
    ('military', 'Military laser', 6000, 10, 'High damage, rapid fire'),
    ('mine', 'Proximity mine', 75, 4, 'B deploys; 1.5 second arming delay; keep clear'),
    ('jammer', 'Signal jammer', 600, 3, 'Z disrupts targeting for 8s; 20s cooldown'),
    ('cloak', 'Phase cloak', 3000, 11, 'K toggles concealment; consumes fuel'),
    ('rear', 'Rear pulse laser', 600, 4, '4 rear view; SPACE fires the rear-mounted laser'),
]
LASERS = {'pulse': (0.30, 1), 'beam': (0.14, 1), 'military': (0.12, 2), 'mining': (0.65, 1)}
# Full strength of NPC ships; the first half of it is shields, the rest hull.
ENEMY_STRENGTH = {'pirate': 6, 'police': 10}
MISSILE_SPEED = 1200
# Fees a pilot can ask a disabled ship for restarting its drive (one unit of your fuel).
HAIL_ASKS = (50, 120, 250)
# Ship systems that start failing below these hull levels (%), worse the lower it goes.
DAMAGE_FAULTS = {'scanner': 60, 'bearing': 45, 'laser': 30}
FAULT_LABELS = {'scanner': 'SCANNER FAULT', 'bearing': 'BEARING OFFLINE', 'laser': 'LASER MALFUNCTIONING'}
UP, DOWN, LEFT, RIGHT = 1073741906, 1073741905, 1073741904, 1073741903
GREEN, GOLD, RED = (68, 227, 182), (255, 206, 113), (255, 112, 100)
SYSTEMS = [
    ('Halvora', 'Agricultural', 0.15, 0.40), ('Corvant', 'Industrial', 0.40, 0.20),
    ('Meridel', 'Agricultural', 0.34, 0.64), ('Brennix', 'Industrial', 0.60, 0.46),
    ('Skarrow', 'Frontier', 0.76, 0.76), ('Velmora', 'Industrial', 0.72, 0.16),
    ('Duskholt', 'Frontier', 0.14, 0.84), ('Ambrell', 'Agricultural', 0.90, 0.43)]
# Earlier releases used other names; saved waypoints and courses are renamed on load.
RENAMED_SYSTEMS = {'Lave':'Halvora','Zaonce':'Corvant','Diso':'Meridel','Leesti':'Brennix','Riedquat':'Skarrow','Tionisla':'Velmora','Orerve':'Duskholt','Reorte':'Ambrell'}
PROFILES = [
    ('Dictatorship', 4.2, 6400), ('Corporate state', 5.8, 9100),
    ('Democracy', 3.1, 5800), ('Confederacy', 4.9, 7600),
    ('Anarchy', 1.2, 11500), ('Democracy', 6.4, 12800),
    ('Feudal', 0.8, 4200), ('Communist', 3.6, 8100)]

SAVE = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'star-trader' / 'save.json'
# Bug reports and suggestions wait here, one file each, until an online session sends them.
FEEDBACK_OUTBOX = SAVE.parent / 'feedback-outbox'


def price(system, good):
    rng = random.Random(system * 97 + good * 13)
    economy = SYSTEMS[system][1]
    factor = (0.65 if good < 3 else 1.25) if economy == 'Agricultural' else (1.3 if good < 3 else 0.7)
    if economy == 'Frontier':
        factor = 1.0
    if good in METALS: factor = {'Industrial': 1.15, 'Agricultural': .95, 'Frontier': .9}[economy]
    if good in ILLEGAL:
        # Contraband prices reflect supply and demand rather than a flat bonus.
        demand = {6: {'Industrial': .65, 'Agricultural': 1.65, 'Frontier': 1.40},
                  7: {'Industrial': .65, 'Agricultural': 1.65, 'Frontier': 1.60}}
        factor = demand[good][economy]
        government = PROFILES[system][0]
        if good == 7 and government in ('Anarchy','Feudal'): factor *= 1.10
        if good == 6 and government == 'Corporate state': factor *= 1.05
    return round(BASE[good] * factor * rng.uniform(0.9, 1.1))


def distance(a, b):
    return math.hypot(SYSTEMS[a][2] - SYSTEMS[b][2], SYSTEMS[a][3] - SYSTEMS[b][3]) * 10


def quote(system, good, buy=True):
    """Player buy price includes a spread; selling immediately costs money."""
    base = price(system, good)
    return base + max(1, math.ceil(base * 0.08)) if buy else max(1, base - math.ceil(base * 0.08))


def initial_stock():
    return [[random.Random(i * 113 + j).randint(*((1, 6) if j in METALS else (12, 35))) for j in range(len(GOODS))] for i in range(8)]


def fuel_price(system):
    """Credits per fuel unit: refining and demand make fuel dear in some systems."""
    return round(7 + random.Random(system * 31).uniform(0, 7))


def random_asteroid(position):
    # Most rocks hold ore; rare rich ones hold silver or gold and take more cutting.
    roll = random.random()
    good,health = (8,5) if roll < .08 else (9,4) if roll < .25 else (2,3)
    return list(position)+[health,good]


def coordinates(system):
    return [round(SYSTEMS[system][2]*10,2), round(SYSTEMS[system][3]*10,2)]


def valid_coordinates(position):
    return isinstance(position,list) and len(position) == 2 and all(type(n) in (int,float) and math.isfinite(n) and 0 <= n <= 10 for n in position)


def galactic_distance(a,b):
    return math.hypot(a[0]-b[0],a[1]-b[1])


def hyperspace_cost(distance):
    return round(distance*1.2 + .2, 3) if distance > .001 else 0


class Pilot:
    def __init__(self):
        self.credits = 150
        self.crymto = 0
        self.redeemed_credit_codes = []
        self.notes = ""
        self.station_police_remaining = [STATION_POLICE_CAPACITY]*len(SYSTEMS)
        self.station_police_defeated = [0]*len(SYSTEMS)
        self.cargo = [0] * len(GOODS)
        self.system = 0
        self.fuel = 7.0
        self.hull = 100
        self.kills = 0
        self.name = ''
        self.trade_profit = 0
        self.cargo_paid = [0] * len(GOODS)
        self.jumps = 0
        self.equipment = []
        self.missiles = 3
        self.laser = 'pulse'
        self.stock = initial_stock()
        self.mines = 0
        self.fine = 0
        self.position = coordinates(0)
        self.deep_space = False
        self.waypoint = None
        self.commander_id = uuid.uuid4().hex
        self.maintenance = 0.
        self.flights_since_service = 0
        self.engineering_level = self.engineering_failures = 0
        self.engineering_ready_at = 0.
        self.workshop_xp = 0
        self.dock_job = None
        self.job_boards = [dict(refresh_at=0.,used=[0,0,0]) for _ in SYSTEMS]
        self.bank_balance = 0
        self.storage = [dict(owned=False,rented_until=0.,cargo=[0]*len(GOODS)) for _ in SYSTEMS]
        self.prison = None
        self.intro_seen = False
        self.trade_log = []

    @property
    def career_points(self):
        return self.kills*25 + self.trade_profit//10 + self.jumps*5

    @property
    def rank(self):
        return [name for points,name in RANKS if self.career_points >= points][-1]

    @property
    def next_rank(self):
        return next(((points,name) for points,name in RANKS if self.career_points < points),None)

    @property
    def capacity(self):
        return 35 if 'cargo' in self.equipment else 20

    def trade(self, good, buy, clean_deal=False, use_crymto=False):
        value = quote(self.system, good, buy)
        if clean_deal and not buy and good in ILLEGAL: value = value*85//100
        stock = self.stock[self.system]
        if buy:
            if stock[good] <= 0: return 'Station has no stock.'
            if sum(self.cargo) >= self.capacity: return 'Cargo hold full.'
            dirty = min(self.crymto,value) if good in ILLEGAL and use_crymto else 0
            if self.credits < value-dirty: return 'Insufficient funds (Crymto is only accepted for contraband).'
            self.crymto -= dirty
            self.credits -= value-dirty
            if self.cargo[good] == 0: self.cargo_paid[good] = 0
            self.cargo_paid[good] += value
            self.cargo[good] += 1
            stock[good] -= 1
            self.log_trade('buy',good,value,'CYM' if dirty == value else 'cr')
        else:
            if self.cargo[good] <= 0: return 'None aboard to sell.'
            if good in ILLEGAL and not clean_deal: self.crymto += value
            else: self.credits += value
            basis = self.cargo_paid[good]//self.cargo[good]
            self.trade_profit += max(0,value-basis)
            self.log_trade('sell',good,value,'CYM' if good in ILLEGAL and not clean_deal else 'cr',value-basis)
            self.cargo_paid[good] = 0 if self.cargo[good] == 1 else self.cargo_paid[good]-basis
            self.cargo[good] -= 1
            stock[good] += 1
        unit = ('Crymto / credits' if use_crymto and good in ILLEGAL else 'cr') if buy else ('Crymto' if good in ILLEGAL and not clean_deal else 'cr')
        return f'{"Bought" if buy else "Sold"} 1 t {GOODS[good]} for {value} {unit}.'

    def log_trade(self, side, good, price, unit, profit=0):
        self.trade_log.append(dict(time=time.time(),system=self.system,side=side,good=good,price=price,unit=unit,profit=profit))
        del self.trade_log[:-TRADE_LOG_SIZE]

    def buy_equipment(self, index):
        key, label, cost, tech, _ = EQUIPMENT[index]
        if TECH[self.system] < tech: return f'Outfitting unavailable: {label} requires tech {tech}; {SYSTEMS[self.system][0]} is tech {TECH[self.system]}.'
        if key in self.equipment: return 'Already installed.'
        if key == 'mine' and self.mines >= 4: return 'Mine rack full (4).'
        if key == 'missile' and self.missiles >= 4: return 'Missile rack full (4).'
        if self.credits < cost: return 'Insufficient credits.'
        self.credits -= cost
        if key == 'missile': self.missiles += 1
        elif key == 'mine': self.mines += 1
        else: self.equipment.append(key)
        if key in LASERS: self.laser = key
        return label + ' fitted.'

    @property
    def mass_factor(self):
        return 1 + sum(self.cargo) * 0.025

    def fuel_cost(self):
        return math.ceil(round(7 - self.fuel, 3) * fuel_price(self.system))

    def sell_fuel(self):
        # Stations buy fuel back at three quarters of their price, so sun-skimmed fuel can be sold.
        if self.fuel < 1: return 'Less than one unit of fuel aboard to sell.'
        value = fuel_price(self.system)*3//4
        self.fuel = round(self.fuel-1,5)
        self.credits += value
        return f'Sold 1 unit of fuel for {value} cr. Tank {self.fuel:.2f}/7.'

    def refuel(self):
        cost = self.fuel_cost()
        if self.credits >= cost:
            self.credits -= cost
            self.fuel = 7.0
            return f'Fuel purchased: {cost} cr. Tank full.'
        # A short wallet still buys whole units, so a broke pilot can always limp to the next job.
        price = fuel_price(self.system)
        units = min(int(7-self.fuel),int(self.credits)//price)
        if units <= 0: return f'Fuel costs {price} cr per unit here. Sell cargo or take a station job.'
        self.credits -= units*price
        self.fuel = round(self.fuel+units,5)
        return f'Bought {units} fuel unit{"s" if units > 1 else ""} for {units*price} cr (all you can afford). Tank {self.fuel:.2f}/7.'

    def departure_wear(self):
        return 1+sum(self.cargo)*.025

    def service_cost(self):
        return math.ceil((100-self.hull)*.35+self.maintenance*.25)

    def repair(self):
        cost = self.service_cost()
        if self.credits < cost: return f'Repairs cost {cost} cr.'
        self.credits -= cost
        self.hull = 100
        self.maintenance = 0.
        self.flights_since_service = 0
        return f'Hull and maintenance serviced: {cost} cr. Fuel sold separately (F).'

    def save(self):
        SAVE.parent.mkdir(parents=True, exist_ok=True)
        temp = SAVE.with_suffix('.tmp')
        temp.write_text(json.dumps(vars(self)), encoding='utf-8')
        temp.replace(SAVE)

    def load(self):
        try:
            data = json.loads(SAVE.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not {'credits','cargo','system','fuel','hull','kills'} <= data.keys():
                raise ValueError('Invalid save structure')
            candidate = Pilot()
            # New fields keep their defaults when loading an original save.
            for key in vars(candidate):
                if key in data: setattr(candidate, key, data[key])
            if 'position' not in data: candidate.position = coordinates(candidate.system)
            if isinstance(candidate.waypoint,dict) and candidate.waypoint.get('name') in RENAMED_SYSTEMS:
                candidate.waypoint['name'] = RENAMED_SYSTEMS[candidate.waypoint['name']]
            candidate.add_new_commodities()
            candidate.validate()
            self.__dict__.update(vars(candidate))
            if 'commander_id' not in data:
                try: self.save()
                except OSError: pass
            return True
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def add_new_commodities(self):
        # Saves from before new commodities were added get empty slots for them.
        def pad(row, filler): return row+filler[len(row):] if isinstance(row,list) and len(row) in (6,8) else row
        self.cargo = pad(self.cargo,[0]*len(GOODS))
        self.cargo_paid = pad(self.cargo_paid,[0]*len(GOODS))
        if isinstance(self.stock,list):
            self.stock = [pad(row,initial_stock()[i]) if i < 8 else row for i,row in enumerate(self.stock)]
        if isinstance(self.storage,list):
            for bay in self.storage:
                if isinstance(bay,dict): bay['cargo'] = pad(bay.get('cargo'),[0]*len(GOODS))

    def validate(self):
        def integer(n): return type(n) is int and n >= 0
        if not isinstance(self.station_police_remaining,list) or len(self.station_police_remaining) != len(SYSTEMS) or not all(integer(n) and n <= STATION_POLICE_CAPACITY for n in self.station_police_remaining): raise ValueError('police reserve')
        if not isinstance(self.station_police_defeated,list) or len(self.station_police_defeated) != len(SYSTEMS) or not all(integer(n) and n <= STATION_POLICE_CAPACITY for n in self.station_police_defeated): raise ValueError('police defeats')
        if type(self.notes) is not str or len(self.notes)>4000: raise ValueError('notes')
        if type(self.name) is not str or len(self.name)>24 or not all(c.isprintable() for c in self.name): raise ValueError('name')
        if not integer(self.trade_profit) or not integer(self.jumps): raise ValueError('career')
        if type(self.intro_seen) is not bool: raise ValueError('introduction')
        if not isinstance(self.trade_log,list) or len(self.trade_log) > TRADE_LOG_SIZE: raise ValueError('trade log')
        for entry in self.trade_log:
            if not isinstance(entry,dict) or entry.get('side') not in ('buy','sell') or not integer(entry.get('good')) or entry['good'] >= len(GOODS): raise ValueError('trade entry')
            if not integer(entry.get('system')) or entry['system'] >= len(SYSTEMS) or not integer(entry.get('price')) or type(entry.get('profit',0)) is not int: raise ValueError('trade entry')
            if entry.get('unit') not in ('cr','CYM') or type(entry.get('time')) not in (int,float) or not math.isfinite(entry['time']): raise ValueError('trade entry')
        if self.prison is not None:
            j = self.prison
            if not isinstance(j,dict) or not integer(j.get('system')) or j['system'] >= len(SYSTEMS): raise ValueError('prison')
            if not integer(j.get('days')) or not 1 <= j['days'] <= PRISON_MAX_DAYS: raise ValueError('sentence')
            for key in ('start','release_at'):
                if type(j.get(key)) not in (int,float) or not math.isfinite(j[key]) or j[key] < 0: raise ValueError('sentence time')
            if any(type(j.get(key)) is not int or j[key] < -1 for key in ('bribe_day','work_day')): raise ValueError('prison actions')
        if not isinstance(self.cargo_paid,list) or len(self.cargo_paid) != len(GOODS) or not all(integer(n) for n in self.cargo_paid): raise ValueError('cargo basis')
        if not isinstance(self.redeemed_credit_codes,list) or len(self.redeemed_credit_codes)>100 or any(type(code) is not str or len(code)>80 for code in self.redeemed_credit_codes) or len(set(self.redeemed_credit_codes)) != len(self.redeemed_credit_codes): raise ValueError('credit codes')
        if not integer(self.crymto): raise ValueError('Crymto balance')
        if not integer(self.workshop_xp): raise ValueError('workshop experience')
        if not isinstance(self.job_boards,list) or len(self.job_boards) != len(SYSTEMS): raise ValueError('job boards')
        for board in self.job_boards:
            if not isinstance(board,dict) or type(board.get('refresh_at')) not in (int,float) or not math.isfinite(board['refresh_at']) or board['refresh_at'] < 0: raise ValueError('job refresh')
            if not isinstance(board.get('used'),list) or len(board['used']) != 3 or not all(integer(n) and n <= 3 for n in board['used']): raise ValueError('job limits')
        if self.dock_job is not None:
            j = self.dock_job
            if not isinstance(j,dict) or j.get('kind') not in (0,1,2): raise ValueError('job')
            if not all(integer(j.get(k)) for k in ('step','correct','answer')) or not 0 <= j['correct'] <= j['step'] <= 5 or j['answer'] > 2: raise ValueError('job progress')
            if type(j.get('elapsed')) not in (int,float) or not math.isfinite(j['elapsed']) or not 0 <= j['elapsed'] <= 90: raise ValueError('job time')
            if type(j.get('prompt')) is not str or len(j['prompt']) > 160 or not isinstance(j.get('choices'),list) or len(j['choices']) != 3 or any(type(v) is not str or len(v)>60 for v in j['choices']): raise ValueError('job task')
        if not integer(self.system) or self.system >= 8: raise ValueError('system')
        if not isinstance(self.equipment, list) or any(type(k) is not str for k in self.equipment): raise ValueError('equipment')
        allowed = {e[0] for e in EQUIPMENT if e[0] not in ('missile','mine')}
        if len(set(self.equipment)) != len(self.equipment) or not set(self.equipment) <= allowed: raise ValueError('equipment')
        if not isinstance(self.cargo, list) or len(self.cargo) != len(GOODS) or not all(integer(n) for n in self.cargo): raise ValueError('cargo')
        if sum(self.cargo) > self.capacity: raise ValueError('capacity')
        if type(self.commander_id) is not str or len(self.commander_id) != 32 or any(c not in '0123456789abcdef' for c in self.commander_id): raise ValueError('commander')
        for key in ('maintenance','engineering_ready_at'):
            value = getattr(self,key)
            if type(value) not in (int,float) or not math.isfinite(value) or value < 0: raise ValueError(key)
        if type(self.bank_balance) not in (int,float) or not math.isfinite(self.bank_balance) or self.bank_balance < 0: raise ValueError('bank')
        if not isinstance(self.storage,list) or len(self.storage) != len(SYSTEMS): raise ValueError('storage')
        for bay in self.storage:
            if not isinstance(bay,dict) or type(bay.get('owned')) is not bool: raise ValueError('bay')
            until = bay.get('rented_until')
            if type(until) not in (int,float) or not math.isfinite(until) or until < 0: raise ValueError('rent')
            cargo = bay.get('cargo')
            if not isinstance(cargo,list) or len(cargo) != len(GOODS) or not all(integer(n) for n in cargo) or sum(cargo)>100: raise ValueError('stored cargo')
        if self.maintenance > 100 or not integer(self.flights_since_service): raise ValueError('maintenance')
        if not integer(self.engineering_level) or self.engineering_level > 5 or not integer(self.engineering_failures) or self.engineering_failures > 20: raise ValueError('engineering')
        if not integer(self.mines) or self.mines > 4 or not integer(self.fine): raise ValueError('mines/fine')
        if type(self.deep_space) is not bool: raise ValueError('location')
        if not valid_coordinates(self.position): raise ValueError('position')
        if self.waypoint is not None:
            w = self.waypoint
            if not isinstance(w,dict) or not valid_coordinates(w.get('position')): raise ValueError('waypoint')
            if type(w.get('name')) is not str or len(w['name']) > 60: raise ValueError('name')
            if w.get('system') is not None and (not integer(w['system']) or w['system'] >= 8): raise ValueError('system')
        if not integer(self.missiles) or self.missiles > 4 or not integer(self.kills): raise ValueError('missiles/kills')
        for key in ('credits', 'fuel', 'hull'):
            n = getattr(self, key)
            if type(n) not in (int, float) or not math.isfinite(n) or n < 0: raise ValueError(key)
        if self.fuel > 7 or self.hull > 100: raise ValueError('ship')
        if self.laser not in LASERS or (self.laser != 'pulse' and self.laser not in self.equipment): raise ValueError('laser')
        if not isinstance(self.stock, list) or len(self.stock) != 8: raise ValueError('stock')
        for row in self.stock:
            if not isinstance(row, list) or len(row) != len(GOODS) or not all(integer(n) for n in row): raise ValueError('stock')


def find_sdl_library(name):
    # The macOS app carries its own SDL frameworks; Homebrew installs outside the default dyld path.
    bundled = Path(os.environ.get('STAR_TRADER_FRAMEWORKS','/nonexistent'))/f'{name}.framework'/name
    if bundled.exists(): return str(bundled)
    found = ctypes.util.find_library(name)
    if found: return found
    for folder in ('/opt/homebrew/lib', '/usr/local/lib'):
        candidate = Path(folder) / f'lib{name}.dylib'
        if candidate.exists(): return str(candidate)
    return f'lib{name}.so'


def bind(lib, name, restype, args):
    f = getattr(lib, name)
    f.restype, f.argtypes = restype, args
    return f


class Display:
    def __init__(self):
        self.sdl = C.CDLL(find_sdl_library('SDL2'))
        self.ttf = C.CDLL(find_sdl_library('SDL2_ttf'))
        ptr, i = C.c_void_p, C.c_int
        self.init = bind(self.sdl, 'SDL_Init', i, [C.c_uint32])
        self.quit = bind(self.sdl, 'SDL_Quit', None, [])
        self.window = bind(self.sdl, 'SDL_CreateWindow', ptr, [C.c_char_p, i, i, i, i, C.c_uint32])
        self.renderer = bind(self.sdl, 'SDL_CreateRenderer', ptr, [ptr, i, C.c_uint32])
        self.color = bind(self.sdl, 'SDL_SetRenderDrawColor', i, [ptr, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8])
        self.clear = bind(self.sdl, 'SDL_RenderClear', i, [ptr])
        self.present = bind(self.sdl, 'SDL_RenderPresent', None, [ptr])
        self.drawline = bind(self.sdl, 'SDL_RenderDrawLine', i, [ptr, i, i, i, i])
        self.poll = bind(self.sdl, 'SDL_PollEvent', i, [ptr])
        self.texture = bind(self.sdl, 'SDL_CreateTextureFromSurface', ptr, [ptr, ptr])
        self.copy = bind(self.sdl, 'SDL_RenderCopy', i, [ptr, ptr, ptr, ptr])
        self.free = bind(self.sdl, 'SDL_FreeSurface', None, [ptr])
        self.destroy = bind(self.sdl, 'SDL_DestroyTexture', None, [ptr])
        self.fill_rect = bind(self.sdl,'SDL_RenderFillRect',i,[ptr,ptr])
        self.query = bind(self.sdl, 'SDL_QueryTexture', i, [ptr, ptr, ptr, C.POINTER(i), C.POINTER(i)])
        bind(self.ttf, 'TTF_Init', i, [])()
        self.openfont = bind(self.ttf, 'TTF_OpenFont', ptr, [C.c_char_p, i])
        class Color(C.Structure):
            _fields_ = [('r', C.c_uint8), ('g', C.c_uint8), ('b', C.c_uint8), ('a', C.c_uint8)]
        self.Color = Color
        self.rendertext = bind(self.ttf, 'TTF_RenderUTF8_Blended', ptr, [ptr, C.c_char_p, Color])
        if self.init(32) != 0:
            raise RuntimeError('SDL could not open the display.')
        bind(self.sdl, 'SDL_SetHint', C.c_int, [C.c_char_p, C.c_char_p])(b'SDL_VIDEO_X11_WMCLASS', b'star-trader')
        self.win = self.window(b'Star Trader', 0x2FFF0000, 0x2FFF0000, W, H, 0x2024)
        self.r = self.renderer(self.win, -1, 2) or self.renderer(self.win, -1, 0)
        bind(self.sdl, 'SDL_RenderSetLogicalSize', C.c_int, [ptr, i, i])(self.r, W, H)
        bind(self.sdl,'SDL_StartTextInput',None,[])()
        self.fullscreen = bind(self.sdl, 'SDL_SetWindowFullscreen', i, [ptr, C.c_uint32])
        self.is_fullscreen = False
        if not self.win or not self.r:
            raise RuntimeError('Could not create game window.')
        fonts = ['/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf', '/usr/share/fonts/TTF/DejaVuSansMono.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
                 '/System/Library/Fonts/Menlo.ttc', '/System/Library/Fonts/Monaco.ttf', '/Library/Fonts/Andale Mono.ttf', '/System/Library/Fonts/Supplemental/Andale Mono.ttf']
        fontpath = next((p for p in fonts if Path(p).exists()), None)
        if not fontpath:
            raise RuntimeError('A monospace font is required. Install DejaVu Sans Mono.')
        self.font = self.openfont(fontpath.encode(), 18)
        if not self.font:
            raise RuntimeError('Could not load font.')
        self.cache = {}

    def line(self, x1, y1, x2, y2, color=(68, 227, 182)):
        self.color(self.r, *color, 255)
        self.drawline(self.r, int(x1), int(y1), int(x2), int(y2))

    def fill(self,x,y,w,h,color):
        self.color(self.r,*color,255)
        rect = (C.c_int*4)(int(x),int(y),int(w),int(h))
        self.fill_rect(self.r,rect)

    def rect(self, x, y, w, h, color=(68, 227, 182)):
        for a,b,c,d in [(x,y,x+w,y), (x+w,y,x+w,y+h), (x+w,y+h,x,y+h), (x,y+h,x,y)]:
            self.line(a,b,c,d,color)

    def text(self, x, y, text, color=(160, 225, 213)):
        key = (str(text), color)
        if key not in self.cache:
            if len(self.cache) > 500:
                for t, _, _ in self.cache.values():
                    self.destroy(t)
                self.cache.clear()
            surf = self.rendertext(self.font, str(text).encode(), self.Color(*color, 255))
            if not surf:
                return
            tex = self.texture(self.r, surf)
            self.free(surf)
            w,h = C.c_int(),C.c_int()
            self.query(tex,None,None,C.byref(w),C.byref(h))
            self.cache[key] = tex,w.value,h.value
        tex,w,h = self.cache[key]
        rect = (C.c_int * 4)(int(x),int(y),w,h)
        self.copy(self.r,tex,None,rect)

    def clipboard_text(self):
        pointer = bind(self.sdl,'SDL_GetClipboardText',C.c_void_p,[])()
        if not pointer: return ''
        try: return C.string_at(pointer).decode('utf-8',errors='replace')
        finally: bind(self.sdl,'SDL_free',None,[C.c_void_p])(pointer)

    def set_clipboard_text(self, text):
        result = bind(self.sdl,'SDL_SetClipboardText',C.c_int,[C.c_char_p])(text.encode('utf-8'))
        if result < 0: raise RuntimeError('Clipboard is unavailable.')

    def events(self):
        event = (C.c_uint64 * 7)()
        while self.poll(C.byref(event)):
            raw = bytes(event)
            typ = int.from_bytes(raw[:4], sys.byteorder)
            if typ == 256:
                yield 'quit',0
            elif typ == 512 and raw[12] == 13:
                yield 'blur', 0
            elif typ in (1025,1026) and raw[16] == 1:
                x = int.from_bytes(raw[20:24],sys.byteorder,signed=True)
                y = int.from_bytes(raw[24:28],sys.byteorder,signed=True)
                # SDL_RenderSetLogicalSize already scales mouse events into
                # game coordinates. Converting again breaks scaled windows.
                yield 'click' if typ == 1025 else 'mouse_up',(x,y)
            elif typ == 771:
                yield 'text',raw[12:44].split(b'\0',1)[0].decode('utf-8',errors='replace')
            elif typ in (768,769):
                key = int.from_bytes(raw[20:24], sys.byteorder, signed=True)
                modifiers = int.from_bytes(raw[24:26],sys.byteorder)
                if typ == 768 and raw[13] == 0 and modifiers & 0x00c0 and key in (ord('a'),ord('c'),ord('v'),ord('x')):
                    yield 'clipboard',{ord('a'):'select_all',ord('c'):'copy',ord('v'):'paste',ord('x'):'cut'}[key]
                elif typ == 769 or raw[13] == 0:
                    yield 'down' if typ == 768 else 'up', key


class UpdateNotice:
    """Best-effort daily release check. Failure never prevents offline play."""
    def __init__(self):
        self.latest = None
        self.checked = False

    @staticmethod
    def newer(version):
        try:
            parts = tuple(int(v) for v in version.removeprefix('v').split('.'))
            return len(parts) == 3 and parts > tuple(map(int,VERSION.split('.')))
        except (ValueError,AttributeError): return False

    @staticmethod
    def fetch_latest():
        try:
            req = urllib.request.Request('https://api.github.com/repos/womb4t/star-trader/releases/latest',headers={'User-Agent':f'StarTrader/{VERSION}','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(req,timeout=2) as response:
                return json.loads(response.read(65536)).get('tag_name')
        except (OSError,ValueError,TypeError,AttributeError): return None

    def start(self):
        if os.environ.get('STAR_TRADER_NO_UPDATE_CHECK') == '1' or '--no-update-check' in sys.argv or '--self-test' in sys.argv or '--smoke-test' in sys.argv:
            return
        threading.Thread(target=self.check,daemon=True).start()

    def check(self):
        cache = SAVE.parent/'update-check.json'
        try:
            data = json.loads(cache.read_text())
            if time.time()-data.get('checked',0) < 86400:
                latest = data.get('version')
                if self.newer(latest): self.latest = latest
                self.checked = True
                return
        except (OSError,ValueError,TypeError,AttributeError): pass
        latest = self.fetch_latest()
        if self.newer(latest): self.latest = latest
        self.checked = True
        try:
            cache.parent.mkdir(parents=True,exist_ok=True)
            temp = cache.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(checked=time.time(),version=latest)))
            temp.replace(cache)
        except OSError: pass


class Game:
    def __init__(self, display):
        self.alert = None
        self._save_elapsed = 0.
        self._restoring = False
        self.ship_collision_cooldown = 0.
        self.bank_amount = 50
        self.bank_custom = None
        self.help_page = self.action_tab = 0
        self.d = display
        self.p = Pilot()
        loaded = self.p.load()
        self.read_engineering_ledger()
        self.mode = 'market'
        self.updates = UpdateNotice()
        self.updates.start()
        self.map_input = None
        self.map_text = ''
        self.map_cursor = coordinates((self.p.system+1)%8)
        self.cursor_mode = False
        self.selected = self.shop_selected = 0
        self.target = (self.p.system + 1) % 8
        self.keys = set()
        self.shield = 100
        self.speed = 0
        self.world_basis = [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        self.world_epoch = uuid.uuid4().hex
        self.other_players = {}
        self.station = [0., 0., 1500.]
        self.roll = self.station_angle = 0.
        self.autodock = False
        self.station_hostilities = [False]*len(SYSTEMS)
        self.station_hostile_until = [0.]*len(SYSTEMS)
        self.security_elapsed = 0.
        self.security_warning = 0
        self.security_dispatch = 0.
        self.station_strikes = 0
        self.station_strike_at = 0.
        self.surrendering = False
        self.station_laser_warning = False
        self.station_laser_timer = 15.
        self.enemy_police_system = None
        self.course_assist = False
        self.fine_control = False
        self.enemy = None
        self.ship_target = None
        self.asteroids = []
        self.fragments = []
        self.sun = [1200., -500., 3500.]
        self.heat = 0.
        self.nav = 'station'
        self.nav_target = None
        self.rear_view = False
        self.planet = [-600.,240.,2400.]
        self.planet_radius = 70 + PROFILES[self.p.system][2]/100
        self.flyby_min = float('inf')
        self.assist_speed = 0.
        self.mine_objects = []
        self.jamming = self.jammer_cooldown = 0.
        self.cloaked = False
        self.enemy_kind = 'pirate'
        self.enemy_shot = None
        self.customs_checked = False
        self.cruise = None
        self.jump_charge = self.jump_warp = self.arrival = None
        self.npc_mine_timer = 25.
        self.spawn = 12
        self.cooldown = self.flash = self.laser_flash = 0.
        self.enemy_shot = None
        self.message = 'Welcome back, Commander.' if loaded else 'Welcome, Commander. 1 manual; U ship outfitting.'
        self.stars = [[random.uniform(-1000,1000),random.uniform(-650,650),random.uniform(-1800,1800)] for _ in range(180)]
        self.broken_down = False
        self.breakdown_in = None
        self.disabled_ship = self.hail = None
        self.explosions,self.missiles_in_flight = [],[]
        self.faults,self.fault_timer = set(),3.
        self.assist_spawn_timer = 35.
        self.dock_clearance = self.docking_pending = 0.
        self.rescue = None
        self.rescue_cooldown = 0.
        self.money_return = self.vms_return = 'market'
        self.outfit_return = 'market'
        self.menu_selected = 0
        self.notes_scroll = 0
        self.rename_return = 'market'
        self.intro_return = 'market'
        self.intro_page = 0
        self.intro_name_skipped = False
        self.trades_page = 0
        self.text_selection_all = False
        self.text_selection_mode = None
        self.credit_code_text = ""
        self.exchange_amount = 50
        self.feedback_text = ''
        self.feedback_type = 'bug'
        self.feedback_path = None
        self.job_selected = 0
        self.mouse_controls = False
        self.mouse_held = set()
        self.buttons = []
        self.running = True
        if self.p.hull <= 0: self.mode = 'dead'
        self.resume_saved_session()
        if self.p.prison:
            self.mode = 'prison'
            self.update_prison()
        elif not self.p.intro_seen and self.mode == 'market' and display is not None:
            self.open_utility('intro')

    def save(self):
        self.checkpoint()

    def launch(self, departure=True):
        if departure:
            self.p.flights_since_service += 1
            self.p.maintenance = min(100,self.p.maintenance+self.p.departure_wear())
        self.breakdown_in = random.uniform(8,25) if departure and random.random() < self.breakdown_risk() else None
        self.broken_down = False
        self.disabled_ship = self.hail = None
        self.explosions,self.missiles_in_flight = [],[]
        self.faults,self.fault_timer = set(),3.
        self.assist_spawn_timer = 35.
        self.dock_clearance = self.docking_pending = 0.
        self.world_basis = [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        self.world_epoch = uuid.uuid4().hex
        self.other_players.clear()
        self.mode = 'flight'
        self.release_mouse()
        self.mouse_controls = False
        self.rear_view = False
        self.station = [0.,0.,1500.] if not self.p.deep_space else [0.,0.,1e9]
        self.planet = [-600.,240.,2400.]
        self.planet_radius = 70 + PROFILES[self.p.system][2]/100
        self.flyby_min = float('inf')
        self.assist_speed = 0.
        self.mine_objects = []
        self.cloaked = False
        self.jamming = self.jammer_cooldown = 0.
        self.enemy_kind = 'pirate'
        self.enemy_shot = None
        self.customs_checked = False
        self.cruise = None
        self.jump_charge = self.jump_warp = self.arrival = None
        self.speed = 30
        self.enemy = None
        self.ship_target = None
        self.npc_mine_timer = 25.
        self.spawn = 18
        self.roll = self.station_angle = 0.
        self.autodock = False
        self.course_assist = False
        self.nav_target = None
        self.nav = 'course' if self.p.waypoint and galactic_distance(self.p.position,self.p.waypoint['position']) > .001 else 'station'
        self.heat = 0
        self.asteroids = [random_asteroid(position) for position in ([150.,-70.,1000.],[-250.,100.,1700.],[320.,180.,2300.])]
        self.fragments = []
        self.sun = [1200.,-500.,3500.]
        self.ship_collision_cooldown = 0.
        self.message = 'Approach slowly. Q/E roll to match the rotating slot. 1 manual.'
        self.checkpoint()

    @property
    def message(self):
        return getattr(self,'_message','')

    @message.setter
    def message(self,text):
        old = getattr(self,'_message','')
        self._message = text
        critical = ('outfitting unavailable','thermal warning','station warning','station defence','station police','collision','breakdown','fuel exhausted','refused','seized','repair failed','mine detected','hostile contact','clearance granted','destroyed','rescued')
        if text != old and any(word in text.lower() for word in critical):
            self.alert = dict(text=text,remaining=5.,elapsed=0.)

    def session_mode(self):
        mode = self.mode
        for _ in range(6):
            if mode in ('market','outfit','departure','launch_warning','bank','jobs','exchange','trade_deal','redeem','prison'): return 'market'
            if mode == 'trades': mode = 'money'; continue
            if mode in ('flight','cruise','hyperspace','dead'): return mode
            if mode == 'hail': return 'flight'
            attr = {'money':'money_return','vms':'vms_return','help':'help_return','updates':'update_return','map':'map_return','menu':'menu_return','notes':'notes_return','rename':'rename_return','intro':'intro_return','feedback':'feedback_return','planet_profile':'map_return','engineering':'engineering_return'}.get(mode)
            if not attr: return 'flight'
            mode = getattr(self,attr,'flight')
        return 'flight'

    def checkpoint(self):
        if getattr(self,'_restoring',False): return
        fields = ('world_basis','world_epoch','shield','speed','station','roll','station_angle','station_hostilities','station_hostile_until','security_elapsed','security_warning','security_dispatch','station_laser_warning','station_laser_timer','enemy_police_system','surrendering','autodock','course_assist','fine_control','enemy','enemy_kind',
                  'asteroids','fragments','sun','heat','nav','rear_view','planet','planet_radius',
                  'assist_speed','mine_objects','jamming','jammer_cooldown','cloaked','customs_checked',
                  'cruise','jump_warp','npc_mine_timer','spawn','cooldown','enemy_shot','broken_down','breakdown_in',
                  'disabled_ship','assist_spawn_timer','dock_clearance','docking_pending','rescue_cooldown','ship_collision_cooldown')
        state = {key:getattr(self,key) for key in fields}
        if state['nav'] == 'object': state['nav'] = 'station'
        data = dict(vars(self.p))
        data['_session'] = dict(schema=1,commander=self.p.commander_id,saved_at=time.time(),mode=self.session_mode(),state=state)
        try:
            self.p.validate()
            SAVE.parent.mkdir(parents=True,exist_ok=True)
            temp = SAVE.with_suffix('.tmp')
            temp.write_text(json.dumps(data,allow_nan=False),encoding='utf-8')
            temp.replace(SAVE)
            self._save_elapsed = 0.
            if getattr(self,'remote_save',None): self.remote_save.offer(data)
        except (OSError,ValueError,TypeError) as error:
            self.message = 'Could not save current ship state: '+str(error)

    def request_exit(self):
        self.release_mouse()
        self.checkpoint()
        self.running = False

    def resume_saved_session(self):
        try:
            session = json.loads(SAVE.read_text()).get('_session')
            if session is None: return
            if session['schema'] != 1 or session['commander'] != self.p.commander_id: raise ValueError('session identity')
            mode,state = session['mode'],session['state']
            if mode not in ('market','flight','cruise','hyperspace','dead') or not isinstance(state,dict): raise ValueError('session mode')
            def finite_tree(value,depth=0):
                if depth > 10: return False
                if value is None or type(value) in (str,bool): return True
                if type(value) in (int,float): return math.isfinite(value)
                if isinstance(value,list): return len(value) <= 300 and all(finite_tree(v,depth+1) for v in value)
                if isinstance(value,dict): return len(value) <= 70 and all(finite_tree(v,depth+1) for v in value.values())
                return False
            if not finite_tree(state): raise ValueError('invalid simulation data')
            basis = state.get('world_basis',self.world_basis)
            if type(basis) is not list or len(basis) != 3 or any(type(row) is not list or len(row) != 3 or any(type(v) not in (int,float) for v in row) or abs(sum(v*v for v in row)-1) > .001 for row in basis): raise ValueError('world frame')
            for key in ('station','planet','sun'):
                if not isinstance(state.get(key),list) or len(state[key]) != 3 or not all(type(n) in (int,float) for n in state[key]): raise ValueError('geometry')
            for key in ('shield','speed','roll','station_angle','planet_radius','spawn','rescue_cooldown'):
                if type(state.get(key)) not in (int,float): raise ValueError('simulation scalar')
            if not 0 <= state['shield'] <= 100 or not -200 <= state['speed'] <= 400: raise ValueError('ship state')
            if state.get('enemy') is not None and (not isinstance(state['enemy'],list) or len(state['enemy']) != 5): raise ValueError('contact')
            if mode == 'cruise' and (not isinstance(state.get('cruise'),dict) or state['cruise'].get('duration',0) <= 0): raise ValueError('cruise')
            if mode == 'hyperspace' and not isinstance(state.get('jump_warp'),dict): raise ValueError('warp')
            for key in ('cruise','jump_warp'):
                destination = state.get(key,{}).get('destination') if isinstance(state.get(key),dict) else None
                if isinstance(destination,dict) and destination.get('name') in RENAMED_SYSTEMS:
                    destination['name'] = RENAMED_SYSTEMS[destination['name']]
            # Only restore fields already belonging to the simulation; never arbitrary attributes.
            allowed = set(vars(self)) - {'d','p','keys','buttons','updates','running','_message','alert','_restoring'}
            for key,value in state.items():
                if key in allowed: setattr(self,key,value)
            self.mode = 'dead' if self.p.hull <= 0 else mode
            self.ship_target = None
            self.jump_charge = None
            self.keys.clear()
            self._restoring = True
            elapsed = max(0,time.time()-float(session['saved_at']))
            remaining = min(elapsed,2400.)
            while remaining > .001 and self.mode in ('flight','cruise','hyperspace'):
                step = min(.5,remaining)
                self.ship_collision_cooldown = max(0,self.ship_collision_cooldown-step)
                self._update_simulation(step)
                remaining -= step
            if elapsed > 2400 and self.mode in ('flight','cruise','hyperspace'):
                # Bounded offline catch-up, then rescue rather than resetting the danger away.
                self.mode = 'flight'
                self.rescue_cooldown = 0
                self.open_distress()
                if self.rescue:
                    if not self.rescue['covered']:
                        self.rescue['offers'] = [dict(name='Unattended recovery',percent=50,counters=2)]
                        self.rescue['selected'] = 0
                    self.accept_rescue()
                    self.message = 'Prolonged unattended drift: emergency salvage recovery applied.'
            elif self.mode == 'dead': self.message = 'Your ship was destroyed while unattended. Bank and stored cargo remain.'
            elif elapsed >= 1 and mode != 'market': self.message = f'Rejoined your ship after {int(elapsed)} unattended seconds.'
            self._restoring = False
            self.checkpoint()
        except FileNotFoundError: pass
        except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError) as error:
            self._restoring = False
            self.mode = 'dead' if self.p.hull <= 0 else 'flight'
            self.broken_down = True
            self.speed = 0
            self.message = 'Session recovery needs assistance. Progress retained; use 6 distress. '+str(error)[:45]

    def update(self,dt):
        before = self.mode
        if self.alert:
            self.alert['remaining'] -= dt
            self.alert['elapsed'] += dt
            if self.alert['remaining'] <= 0: self.alert = None
        self.ship_collision_cooldown = max(0,self.ship_collision_cooldown-dt)
        self.update_job(dt)
        if self.enemy_shot:
            self.enemy_shot['remaining'] -= dt
            if self.enemy_shot['remaining'] <= 0: self.enemy_shot = None
        self.refresh_station_hostility()
        self.update_prison()
        self._update_simulation(dt)
        self.update_shared_presence()
        self._save_elapsed += dt
        if self._save_elapsed >= 2 or before != self.mode:
            self.checkpoint()

    def presence_state(self):
        mode = self.session_mode()
        status = {'market':'docked','dead':'destroyed','cruise':'transit','hyperspace':'transit'}.get(mode,'flight')
        if self.p.deep_space and status == 'flight': status = 'deep-space'
        position = [-sum(axis[j]*self.station[j] for j in range(3)) for axis in self.world_basis]
        velocity = [axis[2]*self.speed for axis in self.world_basis]
        return dict(system=self.p.system,mode=status,position=position if status == 'flight' else [0.,0.,0.],
                    velocity=velocity if status == 'flight' else [0.,0.,0.],epoch=self.world_epoch)

    def update_shared_presence(self):
        presence = getattr(self,'presence',None)
        if presence is None: return
        presence.offer(self.presence_state())
        snapshot = presence.snapshot
        nearby = {}
        if not self.p.deep_space:
            for player in snapshot['players']:
                if player['id'] == snapshot['you'] or player['system'] != self.p.system or player['mode'] != 'flight': continue
                if type(player.get('position')) is not list or len(player['position']) != 3: continue
                obj = self.other_players.get(player['id'],{}).get('object',[0.,0.,0.])
                obj[:] = [self.station[j]+sum(player['position'][axis]*self.world_basis[axis][j] for axis in range(3)) for j in range(3)]
                nearby[player['id']] = dict(name=player['name'],object=obj)
        self.other_players = nearby

    def player_label(self, obj):
        return next(('PLAYER '+p['name'] for p in self.other_players.values() if p['object'] is obj),None)

    @staticmethod
    def swept_ship_distance(start,end):
        direction = [b-a for a,b in zip(start,end)]
        length = sum(v*v for v in direction)
        fraction = max(0,min(1,-sum(a*b for a,b in zip(start,direction))/length)) if length else 0
        return math.sqrt(sum((a+fraction*b)**2 for a,b in zip(start,direction)))

    def ship_collisions(self,previous):
        if self.ship_collision_cooldown > 0: return
        for kind,obj,start in previous:
            if kind == 'enemy' and self.enemy is not obj: continue
            if kind == 'disabled' and (not self.disabled_ship or self.disabled_ship['object'] is not obj): continue
            if self.swept_ship_distance(start,obj[:3]) > 52: continue
            impact = min(85,max(10,abs(self.speed)*.45+10))
            self.damage(impact)
            normal = start if math.sqrt(sum(v*v for v in start)) > 1 else [0,0,1]
            length = math.sqrt(sum(v*v for v in normal))
            obj[:3] = [v/length*75 for v in normal]
            self.speed = -min(20,abs(self.speed)*.2)
            self.autodock = False
            self.ship_collision_cooldown = 1.5
            if kind == 'enemy':
                obj[3] -= impact/20
                if obj[3] <= 0: self.destroy_enemy()
            else:
                self.disabled_ship['hull'] -= impact
                if self.disabled_ship['hull'] <= 0:
                    if self.ship_target is obj: self.ship_target = None
                    self.disabled_ship = None
            self.message = 'SHIP COLLISION! Both ships damaged; reverse and clear the hull.'
            return

    def draw_alert(self):
        if not self.alert: return
        d = self.d
        bright = int(self.alert['elapsed']*4)%2 == 0
        color = GOLD if bright else (155,100,65)
        x,y,w = (210,110,610) if self.mode == 'flight' else (180,465,740)
        d.fill(x,y,w,100,(12,13,23))
        d.rect(x,y,w,100,color)
        d.text(x+15,y+7,'SHIP ANNOUNCEMENT',color)
        lines = textwrap.wrap(self.alert['text'],width=52 if self.mode == 'flight' else 64)
        for i,line in enumerate(lines[:3]): d.text(x+15,y+33+i*21,line,GREEN)

    def bank_transfer(self,deposit):
        amount = self.p.credits if deposit else self.p.bank_balance
        if self.bank_amount is not None: amount = min(amount,self.bank_amount)
        if amount <= 0: self.message = 'No credits available for that transfer.'; return
        self.p.credits += -amount if deposit else amount
        self.p.bank_balance += amount if deposit else -amount
        self.message = f'{amount:.2f} credits '+('deposited. Bank funds are off-ship.' if deposit else 'withdrawn to ship wallet.')
        self.save()

    def choose_bank_amount(self, amount):
        self.bank_amount,self.bank_custom = amount,None

    def set_custom_bank_amount(self):
        amount = int(self.bank_custom or 0)
        self.bank_custom = None
        if amount <= 0: self.message = 'Enter an amount of at least 1 credit.'; return
        self.bank_amount = amount
        self.message = f'Transfer amount set to {amount} cr. D deposits, W withdraws.'

    def storage_capacity(self):
        bay = self.p.storage[self.p.system]
        return 100 if bay['owned'] else 40 if bay['rented_until'] > time.time() else 0

    def buy_storage(self,rent):
        bay = self.p.storage[self.p.system]
        if bay['owned']: self.message = 'You already own this station bay.'; return
        cost = 50 if rent else 750
        if self.p.credits < cost: self.message = f'Bay {"rental" if rent else "purchase"} costs {cost} cr.'; return
        self.p.credits -= cost
        if rent: bay['rented_until'] = max(time.time(),bay['rented_until'])+7*86400
        else: bay['owned'] = True
        self.message = '40-tonne bay rented for seven real days.' if rent else '100-tonne station bay purchased.'
        self.save()

    def transfer_storage(self,store):
        bay = self.p.storage[self.p.system]
        index = self.selected
        if store:
            if sum(bay['cargo']) >= self.storage_capacity(): self.message = 'Bay unavailable/full. Rent, renew or buy capacity.'; return
            if self.p.cargo[index] <= 0: self.message = 'None aboard to store.'; return
            self.p.cargo[index] -= 1
            bay['cargo'][index] += 1
        else:
            if bay['cargo'][index] <= 0: self.message = 'None in this station bay.'; return
            if sum(self.p.cargo) >= self.p.capacity: self.message = 'Ship hold full.'; return
            bay['cargo'][index] -= 1
            self.p.cargo[index] += 1
        self.message = f'1 tonne {GOODS[index]} '+('stored at '+SYSTEMS[self.p.system][0]+'.' if store else 'retrieved to ship.')
        self.save()

    def recover_destroyed_pilot(self):
        fee = min(100,self.p.bank_balance)
        self.p.bank_balance -= fee
        self.p.credits = 0
        self.p.cargo = [0]*len(GOODS)
        self.p.equipment = []
        self.p.laser = 'pulse'
        self.p.missiles = self.p.mines = 0
        self.p.fuel,self.p.hull,self.p.maintenance,self.p.flights_since_service = 7.,100,0.,0
        destination = min((i for i in range(8) if self.station_allows(i)),key=lambda i:galactic_distance(self.p.position,coordinates(i)))
        self.arrive(coordinates(destination),destination)
        self.dock_clearance = 120
        self.dock()
        self.message = f'Replacement starter ship recovered. Bank fee {fee:.2f} cr; station cargo preserved.'

    def draw_bank(self):
        d,p = self.d,self.p
        bay = p.storage[p.system]
        d.text(35,85,'BANK / '+SYSTEMS[p.system][0].upper()+' STORAGE',GOLD)
        d.text(35,130,'COMMODITY                SHIP   STATION BAY')
        for i,name in enumerate(GOODS):
            d.text(35,172+i*30,('> ' if i == self.selected else '  ')+name,GOLD if i == self.selected else GREEN)
            d.text(320,172+i*30,str(p.cargo[i]))
            d.text(440,172+i*30,str(bay['cargo'][i]))
        d.text(720,135,f'Wallet {p.credits:.2f} cr')
        d.text(720,175,f'Bank   {p.bank_balance:.2f} cr',GOLD)
        if self.bank_custom is not None:
            d.text(720,215,'Amount: '+self.bank_custom+('_' if int(time.monotonic()*2)%2 == 0 else '')+' cr',GOLD)
            d.text(720,420,'Type an amount, then ENTER.')
        else: d.text(720,215,'Transfer: '+('ALL' if self.bank_amount is None else str(self.bank_amount))+' cr')
        d.text(35,490,'Bay: '+('OWNED' if bay['owned'] else 'RENTED' if self.storage_capacity() else 'NONE / RENT EXPIRED'))
        d.text(35,530,f'Stored {sum(bay["cargo"])}/{self.storage_capacity()} t. Rent 40t: 50 cr / 7 real days. Buy 100t: 750 cr.')
        d.text(35,570,'Expired rentals retain cargo; retrieval is allowed, new deposits require renewal.')
        d.text(35,608,'Bank money and station cargo stay off-ship during salvage or ship destruction.')

    def launch_warnings(self):
        warnings = []
        w = self.p.waypoint
        distance = galactic_distance(self.p.position,w['position']) if w else 0
        required = hyperspace_cost(distance)+(.4*self.p.mass_factor if distance > .001 else 0) if w else 0
        if self.p.fuel < 1 or required > self.p.fuel:
            warnings.append(f'Insufficient fuel reserve: aboard {self.p.fuel:.2f}; planned trip {required:.2f}.')
        if w:
            system = w['system']
            if system is None: warnings.append('Destination is deep space: no station, landing or services.')
            elif self.station_hostilities[system] and self.station_overwhelmed(system):
                warnings.append(f'{SYSTEMS[system][0]} is hostile: docking possible, but station lasers may attack.')
            elif self.arrest_pending(system):
                reason = 'station hostility' if self.station_hostilities[system] else f'wanted status / {self.p.fine} cr fines'
                warnings.append(f'{SYSTEMS[system][0]} will ARREST you on docking: {reason}.')
            elif not self.station_allows(system):
                reason = 'station hostility' if self.station_hostilities[system] else f'wanted status / {self.p.fine} cr fines'
                warnings.append(f'{SYSTEMS[system][0]} will REFUSE docking: {reason}.')
        return warnings

    def request_launch(self):
        if self.p.fine and PROFILES[self.p.system][0] not in ('Anarchy','Feudal'):
            self.message = f'STATION CONTROL: launch clearance withheld until your {self.p.fine} cr fine is paid: 9 Money, then 4 Pay fines.'
            return
        if self.launch_warnings():
            self.launch_return = self.mode
            self.mode = 'launch_warning'
            self.keys.clear()
            self.alert = None
            self.message = 'Departure warning. Check destination access and fuel; Cancel stays docked.'
        else: self.request_departure()

    def salvage_terms(self, percent):
        """A percentage of cash AND cargo units; round up, never take more aboard."""
        rate = percent/100
        cash = min(self.p.credits,math.ceil(self.p.credits*rate))
        total = min(sum(self.p.cargo),math.ceil(sum(self.p.cargo)*rate))
        amounts = [math.floor(n*rate) for n in self.p.cargo]
        left = total-sum(amounts)
        order = sorted(range(len(GOODS)),key=lambda i:(-(self.p.cargo[i]*rate-amounts[i]),i))
        for i in order:
            if left and amounts[i] < self.p.cargo[i]:
                amounts[i] += 1
                left -= 1
        return dict(credits=cash,cargo=amounts,tonnes=total)

    def open_distress(self):
        if self.mode not in ('flight','cruise'): return
        if self.rescue_cooldown > 0:
            self.message = f'Rescue channel cooling down: {math.ceil(self.rescue_cooldown)}s. Try 6 again shortly.'
            return
        if self.mode == 'cruise':
            self.arrive(self.p.position,None)
            self.message = 'Cruise stopped for distress transmission.'
        covered = not self.p.deep_space and self.station_allows() and math.sqrt(sum(v*v for v in self.station)) <= 5000
        destination = self.p.system if covered else min((i for i in range(8) if self.station_allows(i)),key=lambda i:galactic_distance(self.p.position,coordinates(i)))
        if covered:
            offers = [dict(name='Galactic Recovery Accord',percent=25,counters=0)]
        else:
            offers = [dict(name=name,percent=random.randint(low,high),counters=0) for name,low,high in
                      [('Hullbridge Haulage',45,60),('Drift Crow Salvage',50,65),('Freewake Guild',35,55)]]
        self.rescue = dict(covered=covered,destination=destination,offers=offers,selected=0)
        self.rescue_cooldown = 60
        self.cloaked = False
        self.autodock = False
        self.jump_charge = None
        self.keys.clear()
        self.mode = 'distress'
        self.message = 'Distress call answered. Review the salvage claim before accepting.'

    def negotiate_rescue(self):
        if not self.rescue or self.rescue['covered']:
            self.message = 'The Recovery Accord rate is fixed at 25%.'
            return
        offer = self.rescue['offers'][self.rescue['selected']]
        if offer['counters'] >= 2:
            self.message = offer['name']+': these are our final terms.'
            return
        offer['counters'] += 1
        offer['percent'] = max(25,offer['percent']-random.randint(4,10))
        self.message = f'{offer["name"]} revised claim: {offer["percent"]}%. A accepts; N counters; R refuses.'

    def accept_rescue(self):
        if self.mode != 'distress' or not self.rescue: return
        contract = self.rescue
        offer = contract['offers'][contract['selected']]
        fee = self.salvage_terms(offer['percent'])
        # One settlement, before changing location; further keypresses cannot pay twice.
        self.rescue = None
        self.p.credits -= fee['credits']
        self.p.cargo = [n-fee_n for n,fee_n in zip(self.p.cargo,fee['cargo'])]
        self.arrive(coordinates(contract['destination']),contract['destination'])
        self.p.fuel = 7.
        self.p.hull = max(25,self.p.hull)
        self.dock_clearance = 120
        self.dock()
        self.message = f'Rescued to {SYSTEMS[self.p.system][0]}. Salvage: {fee["credits"]:.2f} cr + {fee["tonnes"]}t. Fuel full; saved.'

    def draw_launch_warning(self):
        d,p = self.d,self.p
        d.text(45,100,'CHECK BEFORE DEPARTURE',RED)
        lines = []
        for warning in self.launch_warnings(): lines.extend(textwrap.wrap(warning,85))
        lines += ['',f'Full fuel refill: {p.fuel_cost()} cr. Wallet: {p.credits:.2f} cr.',
                  'A docking refusal remains even if you have enough fuel.',
                  'Cancel to pay fines, choose an accepting port, or change your course.',
                  '', 'F buys fuel. L requests launch despite these warnings.',
                  'Cancel stays docked. G opens the map. ESC saves and closes.']
        for i,line in enumerate(lines): d.text(45,155+i*35,line,RED if i < len(self.launch_warnings()) else GREEN)

    def draw_distress(self):
        d,p = self.d,self.p
        contract = self.rescue
        d.text(40,85,'DISTRESS / RECOVERY OFFERS',GOLD)
        d.text(40,125,'Station coverage: '+('YES / regulated 25% claim' if contract['covered'] else 'NO / independent salvagers'))
        for i,offer in enumerate(contract['offers']):
            d.text(40,175+i*38,f'{">" if i == contract["selected"] else " "} {offer["name"]}: {offer["percent"]}% of credits AND cargo',GOLD if i == contract['selected'] else GREEN)
        offer = contract['offers'][contract['selected']]
        fee = self.salvage_terms(offer['percent'])
        d.text(40,315,f'Exact claim: {fee["credits"]:.2f} cr + {fee["tonnes"]} tonnes.',GOLD)
        goods = ', '.join(f'{n}t {GOODS[i]}' for i,n in enumerate(fee['cargo']) if n)
        if goods:
            for i in range(0,len(goods),86): d.text(40,355+(i//86)*27,goods[i:i+86])
        else: d.text(40,355,'No cargo to claim. Zero assets do not prevent rescue.')
        d.text(40,440,'Tow destination: '+SYSTEMS[contract['destination']][0])
        d.text(40,478,'Includes full fuel refill and emergency hull stabilisation to 25%.')
        d.text(40,516,'Equipment is preserved. Customs still apply on station arrival.')
        d.text(40,570,'UP/DOWN choose rescuer. A accepts the displayed claim.')
        d.text(40,608,'N counters (twice per private offer). R refuses with no payment. ESC saves and closes.')
        d.text(40,650,'Settlement and docking save progress. Calls have a 60s cooldown.')

    def station_overwhelmed(self, system=None):
        system = self.p.system if system is None else system
        return self.p.station_police_defeated[system] >= STATION_POLICE_CAPACITY

    def refresh_station_hostility(self):
        now = time.time()
        near = None if self.p.deep_space or math.sqrt(sum(v*v for v in self.station)) > 10000 else self.p.system
        for system,hostile in enumerate(self.station_hostilities):
            if not hostile: continue
            if not self.station_hostile_until[system] or system == near:
                self.station_hostile_until[system] = now+HOSTILITY_COOLDOWN_SECONDS
            elif now >= self.station_hostile_until[system]:
                self.station_hostilities[system] = False
                self.station_hostile_until[system] = 0.
                if system == self.p.system and self.enemy_kind == 'police' and self.enemy_police_system == system:
                    self.enemy,self.ship_target,self.enemy_police_system = None,None,None
                self.message = SYSTEMS[system][0]+': station hostility has cooled. Outstanding fines still apply.'

    def hostility_label(self, system):
        self.refresh_station_hostility()
        if not self.station_hostilities[system]: return ''
        if not self.p.deep_space and self.p.system == system and math.sqrt(sum(v*v for v in self.station)) <= 10000:
            return 'hostile: leave area'
        return f'hostile: {max(0,math.ceil((self.station_hostile_until[system]-time.time())/60))}m'

    def wanted_level(self):
        self.refresh_station_hostility()
        return min(5,sum(self.p.fine >= n for n in WANTED_FINES)+sum(map(bool,self.station_hostilities)))

    def commander_name(self):
        # The name you chose wins; online accounts fall back to their server name.
        remote = getattr(self,'remote_save',None)
        return self.p.name or (remote and remote.player_name) or 'Unnamed'

    def station_allows(self, system=None):
        self.refresh_station_hostility()
        system = self.p.system if system is None else system
        return self.station_overwhelmed(system) or not self.station_hostilities[system] and (self.p.fine < 100 or PROFILES[system][0] in ('Anarchy','Feudal'))

    def arrest_pending(self, system=None):
        # Lawful stations let a wanted pilot dock, but only to surrender.
        system = self.p.system if system is None else system
        self.refresh_station_hostility()
        return PROFILES[system][0] not in ('Anarchy','Feudal') and (self.station_hostilities[system] or self.p.fine >= 100)

    def docking_permitted(self, system=None):
        return self.station_allows(system) or self.arrest_pending(system)

    def arrest(self):
        system,now = self.p.system,time.time()
        police = self.p.station_police_defeated[system]
        days = police+int(self.station_hostilities[system])
        seized = sum(self.p.cargo[i] for i in ILLEGAL)
        for i in ILLEGAL: self.p.cargo[i] = 0
        fine = self.p.fine
        paid = min(fine,int(self.p.credits))
        self.p.credits -= paid
        from_bank = min(fine-paid,int(self.p.bank_balance))
        self.p.bank_balance -= from_bank
        unpaid = fine-paid-from_bank
        days = min(PRISON_MAX_DAYS,days+math.ceil(unpaid/250))
        self.p.fine = 0
        self.station_hostilities[system] = False
        self.station_hostile_until[system] = 0.
        self.p.station_police_remaining[system] = STATION_POLICE_CAPACITY
        self.p.station_police_defeated[system] = 0
        self.enemy = self.ship_target = self.enemy_police_system = None
        self.surrendering = False
        settled = f'{paid+from_bank} cr fines collected'+(f', {unpaid} cr unpaid' if unpaid else '')+(f', {seized}t contraband seized' if seized else '')
        if not days:
            self.mode = 'market'
            self.message = f'ARRESTED on docking: {settled}. Released with a caution.'
        else:
            self.p.prison = dict(system=system,days=days,start=now,release_at=now+days*PRISON_DAY_SECONDS,bribe_day=-1,work_day=-1)
            self.mode = 'prison'
            self.message = f'ARRESTED: {settled}. Sentenced to {days} day{"s" if days > 1 else ""} in the station cells.'
        self.checkpoint()

    def prison_day(self):
        return int((time.time()-self.p.prison['start'])//PRISON_DAY_SECONDS)

    def update_prison(self):
        if self.p.prison and time.time() >= self.p.prison['release_at']:
            self.p.prison = None
            self.mode = 'market'
            self.message = 'Sentence served. Released with a clean record at this station.'
            self.checkpoint()

    def prison_work(self):
        j = self.p.prison
        if j['work_day'] == self.prison_day():
            self.message = 'You have already worked a shift today. Next shift tomorrow.'
            return
        j['work_day'] = self.prison_day()
        j['release_at'] = max(time.time(),j['release_at']-PRISON_WORK_SECONDS)
        self.message = 'Work shift done in the station foundry: 30 minutes off your sentence.'
        self.checkpoint()
        self.update_prison()

    def prison_bribe(self):
        j = self.p.prison
        if j['bribe_day'] == self.prison_day():
            self.message = 'The guards will not risk another deal today.'
            return
        if self.p.credits >= PRISON_BRIBE: self.p.credits -= PRISON_BRIBE; paid = f'{PRISON_BRIBE} cr'
        elif self.p.crymto >= PRISON_BRIBE: self.p.crymto -= PRISON_BRIBE; paid = f'{PRISON_BRIBE} Crymto'
        else:
            self.message = f'A bribe needs {PRISON_BRIBE} credits or {PRISON_BRIBE} Crymto.'
            return
        j['bribe_day'] = self.prison_day()
        if random.random() >= .1:
            self.message = f'The guard pocketed {paid} and looked the other way... from the wrong door. Still locked up.'
            self.checkpoint()
            return
        self.p.prison = None
        self.mode = 'market'
        self.p.fine += 500
        self.request_departure()
        self.station_hostile('Prisoner escape in progress.')
        self.message = f'ESCAPE! {paid} bought an open hangar door. Launch now: the station is hostile and your fine is {self.p.fine} cr.'

    def draw_prison(self):
        d,j = self.d,self.p.prison
        left = max(0,j['release_at']-time.time())
        d.text(35,85,'STATION CELLS / '+SYSTEMS[j['system']][0].upper(),RED)
        d.text(45,150,f'Sentence: {j["days"]} day{"s" if j["days"] > 1 else ""} (1 day = 1 hour; time passes while the game is closed).')
        d.text(45,190,f'Release in {int(left//3600)}h {int(left%3600//60):02d}m {int(left%60):02d}s.',GOLD)
        today = self.prison_day()
        d.text(45,260,'W  Work a shift: 30 minutes off, once per day.'+('  (done today)' if j['work_day'] == today else ''))
        d.text(45,300,f'B  Bribe a guard: {PRISON_BRIBE} cr or {PRISON_BRIBE} Crymto, 1 in 10 chance, once per day.'+('  (tried today)' if j['bribe_day'] == today else ''))
        d.text(45,340,'An escape makes the station hostile and adds a 500 cr fine.')
        d.text(45,410,'Your ship, bank and stored cargo are held safely until release.')

    def request_departure(self):
        self.departure_remaining = 2.
        self.mode = 'departure'
        self.keys.clear()
        self.message = 'Requesting departure clearance. Please wait for station control.'

    def request_docking(self):
        if self.p.deep_space or math.sqrt(sum(v*v for v in self.station)) > 10000:
            self.message = 'No station traffic control in radio range (10,000m).'
        elif not self.docking_permitted():
            self.dock_clearance = 0
            self.docking_pending = 0
            self.message = 'Docking refused: hostile or wanted status. Seek another accepting port.'
        elif self.station_hostilities[self.p.system] and not self.surrendering:
            self.surrender()
        elif self.dock_clearance > 0:
            self.message = f'Docking clearance remains valid for {math.ceil(self.dock_clearance)}s.'
        else:
            self.docking_pending = 2.
            self.message = 'Docking clearance requested. Await station response.'

    def station_hostile(self, reason):
        if self.p.deep_space: return
        if not self.station_hostilities[self.p.system]:
            self.p.fine += 150
        self.station_hostilities[self.p.system] = True
        self.station_hostile_until[self.p.system] = time.time()+HOSTILITY_COOLDOWN_SECONDS
        self.dock_clearance = self.docking_pending = 0.
        self.autodock = self.course_assist = False
        self.message = 'STATION DEFENCE: '+reason+' Docking revoked; police response authorised!'
        self.checkpoint()

    def surrender(self):
        self.surrendering = True
        if self.enemy_kind == 'police' and self.enemy is not None:
            # The police ship returns to the station reserve; it was not defeated.
            if self.enemy_police_system is not None:
                system = self.enemy_police_system
                self.p.station_police_remaining[system] = min(STATION_POLICE_CAPACITY,self.p.station_police_remaining[system]+1)
            self.enemy = self.ship_target = self.enemy_police_system = None
        self.station_laser_warning,self.station_laser_timer = False,15.
        self.dock_clearance,self.docking_pending = 120,0
        self.message = 'SURRENDER ACCEPTED: police stand down. Fly straight in and dock to be arrested. Firing or leaving cancels it.'
        self.checkpoint()

    def cancel_surrender(self, reason):
        if not self.surrendering: return
        self.surrendering = False
        self.dock_clearance = 0
        self.security_dispatch = 0
        self.message = f'SURRENDER VOID: {reason} Police response resumes!'
        self.alert = dict(text=self.message,remaining=5.,elapsed=0.)

    def systems_in_range(self):
        return [j for j in range(len(SYSTEMS)) if j != self.p.system and hyperspace_cost(galactic_distance(self.p.position,coordinates(j))) <= self.p.fuel]

    def best_sale_in_range(self, good):
        """Highest sale price for a commodity among systems reachable on the fuel aboard."""
        offers = [(quote(j,good,False),j) for j in self.systems_in_range()]
        return max(offers) if offers else None

    def in_patrol_zone(self):
        if self.p.deep_space or PROFILES[self.p.system][0] in ('Anarchy','Feudal') or self.station_hostilities[self.p.system]: return False
        return math.sqrt(sum(v*v for v in self.station)) <= PATROL_RADIUS

    def station_struck(self):
        if self.station_hostilities[self.p.system]: return
        now = time.time()
        if now-self.station_strike_at > STRAY_SHOT_RESET: self.station_strikes = 0
        self.station_strikes += 1
        self.station_strike_at = now
        if self.station_strikes > STRAY_SHOT_LIMIT:
            self.station_hostile('Repeated weapons fire on station after warnings.')
            self.update_station_security(0)
            return
        self.p.fine += STRAY_SHOT_FINE
        left = STRAY_SHOT_LIMIT-self.station_strikes
        self.message = (f'STATION CONTROL: stray fire hit our hull! {STRAY_SHOT_FINE} cr fine. Cease fire'
                        +(f' - {left} more hit{"s" if left > 1 else ""} and police launch.' if left else ' NOW - next hit launches police.')
                        +' Pay fines before your next launch.')
        self.alert = dict(text=self.message,remaining=5.,elapsed=0.)
        self.checkpoint()

    def dispatch_station_police(self):
        if self.p.deep_space or self.enemy is not None or self.p.station_police_remaining[self.p.system] <= 0: return False
        self.p.station_police_remaining[self.p.system] -= 1
        self.enemy_kind = 'police'
        self.enemy_police_system = self.p.system
        self.enemy = [self.station[0]+90,self.station[1]+50,max(300.,self.station[2]-150),10,0.]
        self.security_dispatch = 15.
        remaining = self.p.station_police_remaining[self.p.system]
        self.message = f'STATION POLICE launched. Station reserve: {remaining}/{STATION_POLICE_CAPACITY}.'
        self.checkpoint()
        return True

    def update_station_security(self, dt):
        if self.p.deep_space: return
        self.security_dispatch = max(0,self.security_dispatch-dt)
        if self.surrendering and math.sqrt(sum(v*v for v in self.station)) > 10000:
            self.cancel_surrender('you left the station area.')
        if self.station_hostilities[self.p.system]:
            if self.surrendering: return
            self.update_station_lasers(dt)
            if self.enemy is None and self.security_dispatch <= 0:
                self.dispatch_station_police()
            return
        x,y,z = self.station
        restricted = -100 < z < 800 and math.hypot(x,y) < 200 and (self.speed > 0 or z < 150)
        if self.dock_clearance > 0 or not restricted:
            self.security_elapsed = 0.
            self.security_warning = 0
            return
        self.security_elapsed += dt
        if not self.security_warning:
            self.security_warning = 1
            self.message = 'STATION WARNING: no clearance! Stop and request docking with 7, or withdraw. Police in 12 seconds.'
        if self.security_elapsed >= 6 and self.security_warning == 1:
            self.security_warning = 2
            self.message = 'FINAL STATION WARNING: withdraw or obtain clearance! Police in 6 seconds.'
        if self.security_elapsed >= 12:
            self.station_hostile('Unauthorised docking approach.')

    def update_station_lasers(self, dt):
        if not self.station_overwhelmed() or math.sqrt(sum(v*v for v in self.station)) > 2500:
            self.station_laser_warning = False
            self.station_laser_timer = 15.
            return
        if not self.station_laser_warning:
            self.station_laser_warning = True
            self.station_laser_timer = 15.
            self.message = 'STATION WARNING: police defeated. Dock or withdraw beyond 2500m within 15 seconds; station lasers will fire!'
            return
        self.station_laser_timer -= dt
        if self.station_laser_timer <= 0:
            self.station_laser_timer += 2.
            self.enemy_shot = dict(position=self.station[:],kind='station',remaining=.35)
            self.damage(12)
            self.message = 'STATION DEFENCE: station lasers firing. Dock or withdraw!'

    def breakdown_risk(self, next_flight=False):
        flights = self.p.flights_since_service + int(next_flight)
        wear = self.p.maintenance + (self.p.departure_wear() if next_flight else 0)
        if flights < 5 and self.p.hull >= 80: return 0.
        return min(.65,flights*.003+wear*.002+(100-self.p.hull)*.003)

    def read_engineering_ledger(self):
        path = SAVE.parent/f'engineering-{self.p.commander_id}.json'
        try:
            data = json.loads(path.read_text())
            failures,ready = data['failures'],data['ready_at']
            if type(failures) is not int or not 0 <= failures <= 20: return
            if type(ready) not in (int,float) or not math.isfinite(ready) or ready < 0: return
            self.p.engineering_failures,self.p.engineering_ready_at = failures,ready
        except (OSError,ValueError,KeyError,TypeError): pass

    def write_engineering_ledger(self):
        path = SAVE.parent/f'engineering-{self.p.commander_id}.json'
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(failures=self.p.engineering_failures,ready_at=self.p.engineering_ready_at)))
            temp.replace(path)
            return True
        except OSError as error:
            self.message = 'Could not persist repair cooldown: '+str(error)
            return False

    def engineering_chance(self, other=False):
        condition = self.disabled_ship['hull'] if other and self.disabled_ship else self.p.hull
        return max(.05,min(.85,.2+self.p.engineering_level*.12+min(.05,self.p.workshop_xp*.0005)-(100-condition)*.001))

    def train_engineering(self):
        if self.engineering_location() not in ('market','outfit'):
            self.message = 'Engineering training is available while docked.'
            return
        if self.p.engineering_level >= 5:
            self.message = 'Engineering level 5: training complete.'
            return
        cost = [200,400,800,1600,3200][self.p.engineering_level]
        if self.p.credits < cost:
            self.message = f'Next engineering course costs {cost} cr.'
            return
        self.p.credits -= cost
        self.p.engineering_level += 1
        self.message = f'Engineering trained to level {self.p.engineering_level}.'
        self.save()

    def attempt_engineering(self, other=False):
        if self.engineering_location() != 'flight':
            self.message = 'Use station repairs while docked; field repairs are for flight.'
            return
        if self.p.engineering_ready_at > time.time():
            self.message = f'Repair cooldown: {math.ceil((self.p.engineering_ready_at-time.time())/60)} minutes remaining.'
            return
        if self.enemy:
            self.message = 'Cannot send a repair party while a hostile is present.'
            return
        if other:
            if not self.disabled_ship or self.ship_target is not self.disabled_ship['object']:
                self.message = 'Select a disabled ship on the scanner first.'
                return
            if math.sqrt(sum(v*v for v in self.disabled_ship['object'])) > 350 or abs(self.speed) > 30:
                self.message = 'Helping another ship requires range <=350m and speed <=30.'
                return
        elif not self.broken_down and self.p.hull >= 100 and self.p.maintenance <= 0:
            self.message = 'Your ship needs no field repair.'
            return
        if self.p.credits < 15:
            self.message = 'A repair attempt needs 15 credits of parts. Distress rescue remains available.'
            return
        self.p.credits -= 15
        if random.random() < self.engineering_chance(other):
            self.p.engineering_failures = 0
            self.p.engineering_ready_at = 0
            if other:
                reward = 60+self.p.engineering_level*15
                self.p.credits += reward
                self.disabled_ship = None
                self.ship_target = None
                self.assist_spawn_timer = 90
                self.message = f'Repair successful. The rescued crew paid {reward} credits.'
            else:
                self.broken_down = False
                self.breakdown_in = None
                self.p.hull = min(100,self.p.hull+20+self.p.engineering_level*8)
                self.p.maintenance = max(0,self.p.maintenance-15-self.p.engineering_level*5)
                self.message = 'Field repair successful. Station service is still recommended.'
            self.write_engineering_ledger()
        else:
            self.p.engineering_failures = min(20,self.p.engineering_failures+1)
            minutes = 30*2**(self.p.engineering_failures-1)
            self.p.engineering_ready_at = time.time()+minutes*60
            if self.write_engineering_ledger():
                self.message = f'Repair failed. Next attempt in {minutes} real minutes. Distress: 6.'

    def draw_engineering(self):
        d,p = self.d,self.p
        cost = [200,400,800,1600,3200][p.engineering_level] if p.engineering_level < 5 else None
        cooldown = max(0,math.ceil((p.engineering_ready_at-time.time())/60))
        lines = ['ENGINEERING / LEVEL '+str(p.engineering_level),
                 f'Credits {p.credits:.2f}. Next course: {str(cost)+" cr" if cost is not None else "maximum level"}.',
                 f'Hull {p.hull:.0f}%. Maintenance wear {p.maintenance:.1f}/100.',
                 f'Flights since service: {p.flights_since_service}. Next departure risk: {self.breakdown_risk(True)*100:.1f}%.',
                 'Engine state: '+('BROKEN DOWN' if self.broken_down else 'operational'),
                 f'Own-ship field repair chance: {self.engineering_chance()*100:.0f}%. Parts: 15 cr.',
                 f'Failed-attempt cooldown: {cooldown} real minutes remaining.',
                 'Failures wait 30, 60, 120... real minutes; cooldown survives restart.',
                 (f'Selected disabled ship: {self.engineering_chance(True)*100:.0f}% repair chance.' if self.disabled_ship and self.ship_target is self.disabled_ship['object'] else 'Select a disabled ship on the scanner to assess assistance.'), 'T buys training while docked. R attempts a field repair in flight.',
                 'H helps the selected disabled ship: range <=350m, speed <=30.',
                 'Successful assistance earns credits; failures share your cooldown.',
                 'Station R repairs hull AND resets maintenance and flight count.',
                 'Field repair progress saves at your next station; cooldown saves now.',
                 '', 'BACKSPACE returns. Distress 6 is available from the cockpit.']
        for i,line in enumerate(lines): d.text(35,85+i*34,line,GOLD if i==0 else GREEN)

    def inspect_cargo(self):
        self.customs_checked = True
        if PROFILES[self.p.system][0] in ('Anarchy','Feudal'): return ''
        count = sum(self.p.cargo[i] for i in ILLEGAL)
        if count and random.random() < .55:
            for i in ILLEGAL: self.p.cargo[i] = 0
            self.p.fine += count*25
            return f' Customs seized {count}t contraband; fine {count*25} cr.'
        return ''

    def dock(self):
        if self.p.deep_space: return
        if not self.docking_permitted():
            self.message = 'Docking refused: wanted status.'
            return
        arrest = self.arrest_pending()
        inspection = self.inspect_cargo() if not self.customs_checked and not arrest else ''
        self.mode = 'market'
        self.shield = 100
        self.speed = 0
        self.autodock = False
        self.keys.clear()
        self.cloaked = False
        self.message = ('Docked.' + inspection) if inspection else 'Docked. X VMS for ship services; 9 Money; G Nav.'
        if arrest: self.arrest()
        self.save()

    def slot_error(self):
        # A rectangular slot has the same orientation after half a turn.
        return (self.station_angle - self.roll + math.pi/2) % math.pi - math.pi/2

    def docking_safe(self):
        x,y,_ = self.station
        c,s = math.cos(self.station_angle),math.sin(self.station_angle)
        x,y = x*c+y*s,-x*s+y*c
        return abs(x) <= 14 and abs(y) <= 6 and 0 < self.speed <= 25 and abs(self.slot_error()) <= DOCK_ROLL_TOLERANCE + 1e-12 and not self.enemy and self.dock_clearance > 0 and self.docking_permitted()

    def damage(self, amount):
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        self.p.hull = max(0, self.p.hull - (amount-absorbed))
        self.flash = 0.15
        if self.p.hull <= 0:
            self.mode = 'dead'
            self.autodock = False
        if amount >= 1: self.checkpoint()

    def hail_disabled_ship(self):
        ship = self.disabled_ship
        if not ship: self.message = 'No disabled ship to hail. They appear as gold DISABLED SHIP contacts.'; return
        if math.sqrt(sum(v*v for v in ship['object'])) > 1500: self.message = 'Close within 1,500 m to hail the disabled ship.'; return
        if ship.get('refused') or ship.get('hostile'): self.message = 'The crew will not talk to you'+(' after you fired on them.' if ship.get('hostile') else ' again. They are waiting for the station service.'); return
        # How much the stranded crew will really pay: more when their hull is failing.
        budget = ship.setdefault('budget',random.randint(70,200)+(60 if ship['hull'] < 20 else 0))
        self.hail = dict(budget=budget,counter=None,rounds=0)
        self.mode = 'hail'
        self.keys.clear()
        self.message = 'Channel open to the disabled ship.'

    def hail_ask(self, ask):
        h = self.hail
        if ask <= h['budget']: return self.hail_settle(ask)
        h['rounds'] += 1
        if h['rounds'] > 2:
            self.disabled_ship['refused'] = True
            self.hail = None
            self.mode = 'flight'
            self.message = 'Captain: "You are a pirate in all but name. We will wait for the station service." Channel closed.'
            return
        h['counter'] = h['budget']//10*10
        self.message = f'Captain: "{ask} is robbery. We can pay {h["counter"]} credits." (4 accepts)'

    def hail_settle(self, fee):
        if self.p.fuel < 1: self.message = 'You need at least 1 unit of fuel to restart their drive.'; return
        self.p.fuel = round(self.p.fuel-1,5)
        self.p.credits += fee
        self.end_hail(f'Drive restarted with 1 unit of your fuel. The crew paid {fee} credits and jumped clear.')

    def hail_cargo(self):
        if self.p.fuel < 1: self.message = 'You need at least 1 unit of fuel to restart their drive.'; return
        space = self.p.capacity-sum(self.p.cargo)
        if space <= 0: self.message = 'Your hold is full, so they cannot pay in cargo.'; return
        good = random.choice((0,1,3,4,5))
        tonnes = min(space,max(1,self.hail['budget']//max(1,quote(self.p.system,good,False))),6)
        self.p.fuel = round(self.p.fuel-1,5)
        self.p.cargo[good] += tonnes
        self.end_hail(f'Drive restarted. The crew paid in cargo: {tonnes} t of {GOODS[good].lower()}.')

    def end_hail(self, message):
        self.explode(self.disabled_ship['object'],.4)
        self.disabled_ship = self.ship_target = self.hail = None
        self.assist_spawn_timer = 90
        self.mode = 'flight'
        self.message = message
        self.checkpoint()

    def draw_hail(self):
        d,h = self.d,self.hail
        d.text(35,85,'COMMS / DISABLED SHIP',GOLD)
        d.text(45,140,'Captain: "Our drive is dead and we are a sitting target out here.')
        d.text(45,168,'Can you restart us? It takes one unit of your fuel. Name your price."')
        for i,ask in enumerate(HAIL_ASKS): d.text(45,230+i*36,f'{i+1}  Ask {ask} credits')
        d.text(45,338,f'4  Accept their offer of {h["counter"]} credits' if h['counter'] else '4  (no counter-offer yet)',GREEN if h['counter'] else (120,140,150))
        d.text(45,374,'5  Ask to be paid in cargo instead')
        d.text(45,440,f'Asks rejected so far: {h["rounds"]} of 2. Push too hard and they stop talking.',(135,175,185))
        d.text(45,476,'Or fire on them: a destroyed ship spills cargo you can scoop, but lawful stations fine you.',(135,175,185))
        d.text(45,540,'BACKSPACE closes the channel.',(135,175,185))

    def handling(self):
        # A battered hull answers the controls slowly: 100% at full hull, 40% at zero.
        return .4+.6*max(0,min(100,self.p.hull))/100

    def update_faults(self, dt):
        self.fault_timer -= dt
        if self.fault_timer > 0: return
        self.fault_timer = 3.
        before = set(self.faults)
        self.faults = {name for name,limit in DAMAGE_FAULTS.items() if self.p.hull < limit and random.random() < .2+.6*(limit-self.p.hull)/limit}
        new = self.faults-before
        if new: self.message = 'DAMAGE: '+', '.join(FAULT_LABELS[name] for name in sorted(new))+'. Repairs at a station fix it.'

    def disabled_ship_struck(self):
        # Like stations, a stranded crew allows for stray fire from a fight nearby before shooting back.
        ship,now = self.disabled_ship,time.time()
        if ship.get('hostile'):
            self.message = f'Disabled ship hit: hull {ship["hull"]/40*100:.0f}%.'
            return
        if now-ship.get('strike_at',0) > STRAY_SHOT_RESET: ship['strikes'] = 0
        ship['strikes'] = ship.get('strikes',0)+1
        ship['strike_at'] = now
        if ship['strikes'] > STRAY_SHOT_LIMIT:
            ship['hostile'] = True
            self.message = f'Disabled ship hit: hull {ship["hull"]/40*100:.0f}%. "That was no accident!" They are turning to fight.'
            return
        left = STRAY_SHOT_LIMIT-ship['strikes']
        self.message = (f'RADIO, disabled ship: "Cease fire! You hit us, we are a stranded vessel." Hull {ship["hull"]/40*100:.0f}%. '
                        +(f'{left} more hit{"s" if left > 1 else ""} and they fire back.' if left else 'One more hit and they fire back.'))
        self.alert = dict(text=self.message,remaining=5.,elapsed=0.)

    def update_disabled_ship(self, dt):
        # A crew under attack swings what little thrust they have to aim back at you.
        ship = self.disabled_ship
        if not ship or not ship.get('hostile'): return
        if math.sqrt(sum(v*v for v in ship['object'])) > 1200: return
        ship['shot_timer'] = ship.get('shot_timer',1.5)-dt
        if ship['shot_timer'] > 0: return
        ship['shot_timer'] = 2.8
        self.enemy_shot = dict(position=ship['object'][:3],kind='disabled',remaining=.25)
        if random.random() < .3+.5*max(0,ship['hull'])/40:
            self.damage(5)
            self.message = 'The disabled ship is returning fire!'

    def explode(self, position, size=1.):
        self.explosions.append(dict(position=list(position[:3]),remaining=.8,size=size))

    def update_explosions_and_missiles(self, dt):
        for e in self.explosions: e['remaining'] -= dt
        self.explosions = [e for e in self.explosions if e['remaining'] > 0]
        for m in self.missiles_in_flight[:]:
            if self.enemy is None:
                self.missiles_in_flight.remove(m)
                self.explode(m['position'],.3)
                continue
            delta = [t-p for t,p in zip(self.enemy[:3],m['position'])]
            distance = math.sqrt(sum(v*v for v in delta))
            if distance <= MISSILE_SPEED*dt+60:
                self.missiles_in_flight.remove(m)
                self.destroy_enemy()
                continue
            for i in range(3): m['position'][i] += delta[i]/distance*MISSILE_SPEED*dt

    def target_status(self):
        """Name, shield % and hull % of the ship under attack, for the cockpit readout."""
        if self.enemy is not None and (self.ship_target is None or self.ship_target is self.enemy):
            full = ENEMY_STRENGTH.get(self.enemy_kind,6)
            half = full/2
            strength = max(0,min(full,self.enemy[3]))
            return self.enemy_kind.upper(),max(0,strength-half)/half*100,min(strength,half)/half*100
        if self.disabled_ship and self.ship_target is self.disabled_ship['object']:
            return 'DISABLED SHIP',0.,max(0,self.disabled_ship['hull'])/40*100
        return None

    def destroy_enemy(self):
        if self.enemy is not None: self.explode(self.enemy)
        self.enemy = None
        self.ship_target = None
        if self.enemy_kind == 'police':
            self.p.fine += 150
            if self.enemy_police_system is not None:
                system = self.enemy_police_system
                self.station_hostilities[system] = True
                self.station_hostile_until[system] = time.time()+HOSTILITY_COOLDOWN_SECONDS
                self.p.station_police_defeated[system] = min(STATION_POLICE_CAPACITY,self.p.station_police_defeated[system]+1)
            self.enemy_police_system = None
        else: self.p.credits += 35
        self.p.kills += 1
        self.spawn = 24
        self.message = 'Police ship destroyed. Fine increased by 150 cr.' if self.enemy_kind == 'police' else 'Hostile destroyed. Bounty: 35 credits.'
        self.checkpoint()

    def station_job_board(self):
        board = self.p.job_boards[self.p.system]
        now = time.time()
        if not board['refresh_at']:
            board.update(refresh_at=now+86400,used=[0,0,0])
        elif now >= board['refresh_at']:
            periods = int((now-board['refresh_at'])//86400)+1
            board.update(refresh_at=board['refresh_at']+periods*86400,used=[0,0,0])
        rng = random.Random(f"{self.p.system}:{board['refresh_at']}")
        limits = [rng.randint(2,3),rng.randint(1,2),1]
        titles = [rng.choice(['Food loading','Medical cargo loading','Machinery loading']),
                  rng.choice(['Supply manifest audit','Warehouse stocktake','Inbound freight audit']),
                  rng.choice(['Power-panel service','Airlock service','Coolant-system service'])]
        return board,limits,titles

    def start_job(self, kind):
        if self.mode != 'jobs' or self.p.dock_job is not None: return
        board,limits,titles = self.station_job_board()
        if board['used'][kind] >= limits[kind]:
            self.message = 'No shifts left for this job. Choose another or wait for the 24-hour refresh.'
            return
        board['used'][kind] += 1
        seed = f"{self.p.system}:{board['refresh_at']}:{kind}:{board['used'][kind]}"
        self.p.dock_job = dict(seed=seed,title=titles[kind],kind=kind,step=0,correct=0,elapsed=0.,answer=0,prompt='',choices=['','',''])
        self.job_question()
        self.message = 'Shift started. No fuel, equipment or payment required.'
        self.checkpoint()

    def job_question(self):
        j = self.p.dock_job
        rng = random.Random(str(j.get('seed','legacy'))+':'+str(j['step']))
        if j['kind'] == 0:
            labels = rng.sample(['FOOD','MEDICINE','MACHINERY','TEXTILES','COMPUTERS','ORE'],3)
            label = rng.choice(labels)
            choices = [name+' bay' for name in labels]
            prompt,answer = 'Crate label: '+label+'. Select its loading bay.',choices.index(label+' bay')
        elif j['kind'] == 1:
            expected = rng.randint(12,60)
            actual = expected+rng.choice([-5,-3,-2,0,2,3,5])
            prompt = f'Manifest: {expected} crates. Counted: {actual}. Report the stock.'
            discrepancy = abs(actual-expected) or rng.randint(1,5)
            choices = ['Short by '+str(discrepancy),'Matches manifest','Surplus of '+str(discrepancy)]
            answer = 0 if actual < expected else 2 if actual > expected else 1
        else:
            tasks = [('Before opening a live panel?', ['Isolate power','Remove cover','Touch wiring'],0),
                     ('Power isolated. Before replacing a part?', ['Restart power','Verify zero voltage','Skip checks'],1),
                     ('New part installed. Before restoring power?', ['Leave tools inside','Remove safety labels','Secure covers and clear tools'],2),
                     ('Covers secured. Next step?', ['Run diagnostic test','Open fuel valve','Discard service log'],0),
                     ('Diagnostic passed. Finish with?', ['Bypass safeguards','Record the repair','Remove covers'],1)]
            tasks += [('A coolant leak is reported. First action?', ['Isolate the affected circuit','Increase pressure','Ignore the alarm'],0),
                      ('Airlock seal inspection finds a crack. What next?', ['Approve departure','Replace the seal','Disable the indicator'],1),
                      ('A replacement part has the wrong rating. What next?', ['Force it to fit','Remove its label','Request the correct part'],2)]
            tasks += [
                ('Battery casing is swollen. What should you do?', ['Disconnect and quarantine it','Recharge it harder','Flatten the casing'],0),
                ('A fuse keeps blowing. Next action?', ['Fit a larger fuse','Find the underlying fault','Bridge the contacts'],1),
                ('A pump runs dry. What should you do first?', ['Increase pump speed','Silence the alarm','Stop the pump and inspect supply'],2),
                ('A cable has damaged insulation. Best action?', ['Replace the damaged cable','Wrap it in paper','Leave it exposed'],0),
                ('A bearing overheats on the test stand. Next action?', ['Ignore the temperature','Stop and inspect lubrication','Increase the load'],1),
                ('A panel smells burnt. First action?', ['Open it while powered','Spray coolant inside','Isolate power and report it'],2),
                ('Pressure rises beyond the safe limit. What next?', ['Stop and isolate the pressure source','Override the limit','Increase supply'],0),
                ('A tool is missing after a repair. What next?', ['Launch immediately','Account for tools before energising','Close the service log'],1),
                ('A sensor gives inconsistent readings. Best check?', ['Tape over the display','Declare it normal','Compare with a calibrated reference'],2),
                ('A connector is corroded. What should you do?', ['Replace or service it to specification','Force it together','Paint over the corrosion'],0),
                ('A seal fails its leak test. What next?', ['Approve it anyway','Replace and retest the seal','Raise operating pressure'],1),
                ('A replacement motor spins backwards. What next?', ['Run it at full speed','Remove the guards','Isolate and check the wiring'],2),
                ('A load exceeds the hoist rating. Best action?', ['Use correctly rated lifting gear','Lift it quickly','Disable the load sensor'],0),
                ('A service hatch will not latch. What next?', ['Hold it with a loose tool','Repair the latch before release','Ignore it in vacuum'],1),
                ('A diagnostic reports a ground fault. What next?', ['Bypass the ground','Clear the fault log','Isolate and trace the fault'],2),
                ('A fire alarm sounds during service. First action?', ['Stop work and follow evacuation procedure','Finish the shift first','Mute all alarms'],0),
                ('Two containers have unreadable labels. Best action?', ['Guess their contents','Quarantine and identify them','Mix them together'],1),
                ('A torque setting is unknown. What next?', ['Tighten as hard as possible','Use the last tool setting','Check the service specification'],2),
                ('A fuel coupling leaks during testing. First action?', ['Stop and isolate the fuel supply','Keep testing','Add more fuel'],0),
                ('A safety interlock fails. What next?', ['Bypass it permanently','Replace and verify it','Hide the fault'],1),
                ('A repaired unit passes only once in five tests. What next?', ['Mark it reliable','Skip further tests','Find the intermittent fault'],2),
                ('A maintenance record has no part serial number. What next?', ['Record the verified serial number','Invent a number','Leave the record blank'],0)]
            order = random.Random(str(j.get('seed','legacy'))).sample(range(len(tasks)),5)
            prompt,choices,answer = tasks[order[j['step']]]
        correct = choices[answer]
        rng.shuffle(choices)
        j.update(prompt=prompt,choices=choices,answer=choices.index(correct))

    def answer_job(self, choice):
        j = self.p.dock_job
        if self.mode != 'jobs' or j is None or j['step'] >= 5: return
        correct = choice == j['answer']
        j['correct'] += int(correct)
        j['step'] += 1
        self.message = 'Correct. Task recorded.' if correct else 'Supervisor corrected it. Base pay is safe; bonus reduced.'
        if j['step'] < 5: self.job_question()
        self.checkpoint()

    def update_job(self, dt):
        j = self.p.dock_job
        if self.mode != 'jobs' or j is None: return
        duration = (60,75,90)[j['kind']]
        j['elapsed'] = min(duration,j['elapsed']+dt)
        if j['elapsed'] < duration or j['step'] < 5: return
        base,bonus = ((15,2),(20,3),(25,3))[j['kind']]
        pay = base+bonus*j['correct']
        self.p.credits += pay
        if j['kind'] == 2: self.p.workshop_xp += 10
        self.p.dock_job = None
        self.message = f'Shift complete: {pay} cr paid.'+(' Workshop experience +10.' if j['kind'] == 2 else '')
        self.checkpoint()

    def draw_jobs(self):
        d,j = self.d,self.p.dock_job
        d.text(35,85,'STATION JOBS / NO FUEL OR EQUIPMENT REQUIRED',GOLD)
        if j is None:
            board,limits,titles = self.station_job_board()
            hours,minutes = divmod(max(0,math.ceil((board['refresh_at']-time.time())/60)),60)
            d.text(45,115,f'Refresh in {hours}h {minutes:02}m / availability is local to this station.')
            for i in range(3):
                remaining = limits[i]-board['used'][i]
                pay = ('15-25','20-35','25-40')[i]
                line = f'{titles[i]} / {remaining} left / {pay} cr'

                d.rect(35,150+i*75,1020,60,GOLD if i == self.job_selected else (45,105,115))
                d.text(45,170+i*75,('> ' if i == self.job_selected else '  ')+line,GOLD if i == self.job_selected else GREEN)
            d.text(45,440,'Limited shifts per station per 24 hours. Accepting reserves one shift.')
            d.text(45,480,'Workshop shifts earn 10 XP; practice adds up to 5% repair chance.')
            d.text(45,520,'Click a job, use 1/2/3, or select with arrows and press ENTER.')
        else:
            duration = (60,75,90)[j['kind']]
            d.text(45,155,j.get('title',['CARGO HANDLING','INVENTORY CHECKS','WORKSHOP ASSISTANT'][j['kind']]),GOLD)
            d.text(45,205,f'Tasks {j["step"]}/5   Correct {j["correct"]}   Shift time remaining {math.ceil(duration-j["elapsed"])}s')
            if j['step'] < 5:
                d.text(45,280,j['prompt'],GOLD)
                for i,choice in enumerate(j['choices']): d.text(60,350+i*55,f'{i+1}. {choice}')
            else: d.text(45,290,'Tasks finished. Waiting for the shift to end; payment follows automatically.')
            d.text(45,555,'You may return to the market. Shift progress pauses and is saved.')
        d.text(45,610,f'Workshop experience: {self.p.workshop_xp} XP. BACKSPACE returns to Money.')

    def exchange_available(self):
        return not self.p.deep_space and PROFILES[self.p.system][0] in ('Anarchy','Feudal')

    def convert_crymto(self, launder=True):
        if self.mode != 'exchange' or not self.exchange_available(): return
        balance = self.p.crymto if launder else self.p.credits
        amount = math.floor(balance if self.exchange_amount is None else min(balance,self.exchange_amount))
        rate = 80 if launder else 90
        received = amount*rate//100
        if received < 1:
            self.message = 'Amount too small after the exchange fee. No funds taken.'
            return
        if launder:
            self.p.crymto -= amount
            self.p.credits += received
        else:
            self.p.credits -= amount
            self.p.crymto += received
        self.message = f'Exchanged {amount} '+('Crymto' if launder else 'credits')+f' for {received} '+('credits' if launder else 'Crymto')+'. Fee included.'
        self.checkpoint()

    def draw_exchange(self):
        d = self.d
        d.text(35,85,'CRYMTO EXCHANGE / '+SYSTEMS[self.p.system][0].upper(),GOLD)
        d.text(45,145,f'Credits: {self.p.credits:.2f}    Crymto: {self.p.crymto}')
        d.text(45,205,'Contraband sales pay Crymto. Crymto survives ship loss; banks hold credits.')
        d.text(45,250,'B buys with credits. C at the market buys contraband using Crymto first.')
        d.text(45,310,'Crymto to credits: 20% fee. Credits to Crymto: 10% fee.',GOLD)
        d.text(45,355,'Exchange proceeds are rounded down to whole units; no fee-free loop.')
        for i,launder in enumerate((True,False)):
            balance = self.p.crymto if launder else self.p.credits
            amount = math.floor(balance if self.exchange_amount is None else min(balance,self.exchange_amount))
            net = amount*(80 if launder else 90)//100
            d.text(45,425+i*45,f'{amount} '+('Crymto -> ' if launder else 'credits -> ')+str(net)+(' credits' if launder else ' Crymto'))
        d.text(45,550,'Select an amount, then choose a conversion. BACKSPACE returns to Money.')

    def active_text_field(self):
        if self.mode == 'redeem': return self,'credit_code_text',80
        if self.mode == 'notes': return self.p,'notes',4000
        if self.mode == 'rename' or (self.mode == 'intro' and self.intro_page == 0): return self.p,'name',24
        if self.mode == 'feedback': return self,'feedback_text',1500
        if self.mode == 'bank' and self.bank_custom is not None: return self,'bank_custom',9
        return None

    def text_input(self, text):
        field = self.active_text_field()
        if field is None: return
        owner,name,limit = field
        before = '' if self.text_selection_all and self.text_selection_mode == self.mode else getattr(owner,name)
        self.text_selection_all = False
        text = text.replace('\r\n','\n').replace('\r','\n')
        text = ''.join(c for c in text if c.isprintable() or c == '\n' and self.mode not in ('redeem','rename','intro'))
        if name == 'bank_custom': text = ''.join(c for c in text if c.isdigit())
        setattr(owner,name,(before+text)[:limit])
        if self.mode == 'notes': self.notes_scroll = 0

    def handle_clipboard(self, action):
        field = self.active_text_field()
        if field is None: return
        owner,name,_ = field
        if action == 'select_all':
            self.text_selection_all = True
            self.text_selection_mode = self.mode
            return
        try:
            if action == 'paste':
                text = self.d.clipboard_text()
                if not text: self.message = 'Clipboard has no text.'; return
                self.text_input(text.strip() if self.mode in ('redeem','rename') else text)
            elif action in ('copy','cut'):
                self.d.set_clipboard_text(getattr(owner,name))
                if action == 'cut': setattr(owner,name,''); self.text_selection_all = False
                self.message = 'Text copied to clipboard.'
        except (OSError,RuntimeError) as error:
            self.message = 'Clipboard unavailable: '+str(error)

    def feedback_entry(self):
        return dict(id=uuid.uuid4().hex,kind=self.feedback_type,text=self.feedback_text.strip(),created=time.time(),
                    version=VERSION,platform=sys.platform,screen=self.feedback_return,
                    system='Deep space' if self.p.deep_space else SYSTEMS[self.p.system][0])

    def save_feedback(self):
        if not self.feedback_text.strip():
            self.message = 'Write a description first.'
            return False
        try:
            entry = self.feedback_entry()
            FEEDBACK_OUTBOX.mkdir(parents=True,exist_ok=True)
            path = FEEDBACK_OUTBOX/(entry['id']+'.json')
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(entry),encoding='utf-8')
            temp.replace(path)
            self.feedback_path = str(path)
            self.feedback_text = ''
            label = 'Bug report' if entry['kind'] == 'bug' else 'Suggestion'
            self.message = f'{label} logged. It is sent to the developers next time you play online.'
            return True
        except OSError as error:
            self.message = 'Could not log feedback: '+str(error)
            return False

    def feedback_waiting(self):
        try: return sum(1 for _ in FEEDBACK_OUTBOX.glob('*.json'))
        except OSError: return 0

    def draw_feedback(self):
        d = self.d
        d.text(35,85,'BUG REPORTS AND SUGGESTIONS',GOLD)
        d.text(35,125,'Type what happened, steps to reproduce, and what you expected.')
        d.rect(35,205,1030,305,GREEN)
        lines = []
        for paragraph in self.feedback_text.split('\n'):
            lines.extend(textwrap.wrap(paragraph,89) or [''])
        for i,line in enumerate(lines[-11:]): d.text(45,215+i*25,line)
        d.text(45,490,f'{len(self.feedback_text)}/1500 characters',GOLD)
        d.text(35,535,'Each report is logged separately and sent to the developers when you play online.')
        d.text(35,570,'Includes version, platform, screen and system; no save file attached.')
        waiting = self.feedback_waiting()
        if waiting: d.text(35,610,f'{waiting} report{"s" if waiting > 1 else ""} waiting to send.',GOLD)

    INTRO = [
        ('WELCOME, COMMANDER',[
            'You are a freelance starship commander. You start docked at Halvora station with a small trading ship, 150 credits, a pulse laser and three missiles. Nobody knows your name yet.',
            'Eight star systems lie within reach, each with its own government, economy and technology. Lawful stations are patrolled and police their space; Anarchy and Feudal ports are frontier territory where anything goes.',
            'First, what should we call you? Type your commander name below.']),
        ('THE POINT OF THE GAME',[
            'Make your fortune and your name. Buy low and sell high, upgrade your ship, and climb the ranks from Newbie to Legend. Kills, trading profit and hyperspace jumps all count.',
            'Trade honestly, smuggle contraband for Crymto, or hunt pirates for bounties. Break the law and you face fines, station police and even prison.',
            'Online, other commanders fly in the same universe: you will see their ships on your scanner.']),
        ('HOW TO PLAY',[
            'Docked: select cargo with UP / DOWN, then B buys and S sells. Food is cheap on agricultural worlds and sells well at industrial ones.',
            'Money (9), Nav (G), VMS (X) and Menu run along the top. VMS refuels, repairs and fits equipment.',
            'L launches. In flight W / S set the throttle, the arrows steer and Q / E roll. In Nav, lock a destination, fly 5,000 m clear of the station, then hold H for 3 seconds to jump. Watch your fuel.',
            'Near a station press 7 for docking clearance, then fly slowly into the slot, matching its roll. Within 5,000 m of a lawful station, pirates leave you alone.',
            'BACKSPACE goes back. ESC saves and closes the game at any time. Menu, Controls has the full pilot handbook.']),
        ('BUGS AND SUGGESTIONS',[
            'Star Trader is being built with its players. Found a bug or have an idea? Press 0 (or Menu, Report a bug), choose Bug report or Suggestion, describe it and click Log report.',
            'Each report is logged on your computer and reaches the developers the next time you play online.',
            'The game updates itself when a new version is released, so your idea might arrive in the next one. Good luck, Commander.'])]

    def intro_next(self):
        if self.intro_page == 0:
            self.p.name = self.p.name.strip()
            if not self.p.name and not self.intro_name_skipped:
                self.intro_name_skipped = True
                self.message = 'Type a commander name first, or press ENTER again to stay Unnamed for now.'
                return
        if self.intro_page < len(self.INTRO)-1:
            self.intro_page += 1
            return
        self.p.intro_seen = True
        self.mode = self.intro_return
        self.message = 'Welcome aboard, Commander. Press 0 any time to send a suggestion.'
        self.checkpoint()

    def draw_intro(self):
        d = self.d
        title,paragraphs = self.INTRO[self.intro_page]
        d.text(35,85,title,GOLD)
        d.text(900,85,f'{self.intro_page+1} / {len(self.INTRO)}',GOLD)
        y = 140
        for paragraph in paragraphs:
            for line in textwrap.wrap(paragraph,88):
                d.text(45,y,line)
                y += 26
            y += 16
        if self.intro_page == 0:
            d.text(45,y,'COMMANDER NAME',GOLD)
            d.rect(45,y+28,620,46,GOLD)
            if self.text_selection_all and self.text_selection_mode == 'intro' and self.p.name: d.fill(50,y+34,len(self.p.name)*11+8,34,(20,65,70))
            d.text(57,y+40,self.p.name+('_' if int(time.monotonic()*2)%2 == 0 else ''),GOLD)
            d.text(45,y+90,'You can change it any time under Menu, Commander name.',(135,175,185))
        d.text(45,615,'ENTER or RIGHT continues. LEFT goes back a page. You can reopen this from Menu.',(135,175,185))

    def finish_rename(self):
        self.p.name = self.p.name.strip()
        self.mode = self.rename_return
        self.message = f'Commander name set: {self.p.name or "Unnamed"}.'
        self.checkpoint()

    def redeem_credit_code(self):
        code = self.credit_code_text.strip().upper()
        if code != 'STAR-TEST-100K':
            self.message = 'Code not recognised. No funds changed.'
        elif code in self.p.redeemed_credit_codes:
            self.message = 'This pilot has already redeemed that code.'
        else:
            self.p.redeemed_credit_codes.append(code)
            self.p.credits += 100000
            self.credit_code_text = ''
            self.message = 'Testing code redeemed: 100,000 credits added.'
            self.checkpoint()

    def pay_fines(self):
        if self.p.credits < self.p.fine:
            self.message = f'Insufficient credits. Outstanding fines: {self.p.fine} cr.'
        else:
            amount = self.p.fine
            self.p.credits -= amount
            self.p.fine = 0
            self.message = f'Paid {amount} cr in fines. Station hostility is separate.'
            self.checkpoint()

    def draw_money(self):
        d,p = self.d,self.p
        d.text(35,85,'MONEY',GOLD)
        for i,line in enumerate([f'Wallet: {p.credits:,.2f} credits',f'Crymto account: {p.crymto:,} CYM',
                                 f'Bank: {p.bank_balance:,.2f} credits',f'Outstanding fines: {p.fine:,} credits']):
            d.text(45,155+i*45,line)
        d.text(45,350,'Banking, exchange, codes, fines and paid station jobs.')
        d.text(45,435,'Crymto exchange: '+('available here' if self.exchange_available() else 'feudal and anarchy ports only'))
        if self.money_return != 'market': d.text(45,480,'6 Trade log is available anywhere.')

        d.text(45,320,f'Pay fines costs {p.fine:,} credits. Code redemption is single-use per pilot.')
        d.text(45,570,'Crymto survives ship destruction. Bank funds and stored cargo are protected.')
        d.text(45,610,'BACKSPACE returns. Docking is required for financial services.' if self.money_return != 'market' else 'BACKSPACE returns to the market.')

    def draw_trades(self):
        d,log = self.d,self.p.trade_log
        d.text(35,85,'MONEY / TRADE LOG',GOLD)
        if not log:
            d.text(45,160,'No trades yet. Buy with B and sell with S in a station market.')
            return
        sells = [e for e in log if e['side'] == 'sell']
        d.text(45,125,f'Last {len(log)} trades. Profit on sales shown: {sum(e["profit"] for e in sells if e["unit"] == "cr"):+,} cr.',(135,175,185))
        d.text(45,165,'WHEN         WHERE      TRADE  COMMODITY          PRICE        PROFIT',GOLD)
        newest = list(reversed(log))
        page = newest[self.trades_page*14:(self.trades_page+1)*14]
        for i,e in enumerate(page):
            when = time.strftime('%d %b %H:%M',time.localtime(e['time']))
            profit = f'{e["profit"]:+,} {e["unit"]}' if e['side'] == 'sell' else ''
            color = (120,220,140) if e['side'] == 'sell' and e['profit'] > 0 else RED if e['side'] == 'sell' and e['profit'] < 0 else GREEN
            d.text(45,200+i*27,f'{when:<12} {SYSTEMS[e["system"]][0]:<10} {e["side"].upper():<6} {GOODS[e["good"]]:<18} {e["price"]:>5} {e["unit"]:<4}  {profit}',color)
        pages = max(1,math.ceil(len(log)/14))
        d.text(45,595,f'Page {self.trades_page+1} of {pages}. UP shows older trades, DOWN newer. BACKSPACE returns.',(135,175,185))

    def draw_notepad(self):
        d = self.d
        d.text(35,85,'NOTES / YOUR PERSONAL NOTEPAD',GOLD)
        d.rect(35,130,1030,465,GREEN)
        lines = []
        for paragraph in self.p.notes.split('\n'): lines.extend(textwrap.wrap(paragraph,89) or [''])
        self.notes_scroll = max(0,min(self.notes_scroll,max(0,len(lines)-17)))
        end = len(lines)-self.notes_scroll
        for i,line in enumerate(lines[max(0,end-17):end]): d.text(45,140+i*25,line)
        d.text(35,615,f'{len(self.p.notes)}/4000 characters. Typing appends; arrows scroll; ENTER adds a line.')

    def open_hub(self, target):
        base = self.session_mode()
        if base not in ('market','flight','cruise','dead'):
            self.message = 'Wait until transit finishes before opening ship services.'
            return
        if self.mode == target:
            self.mode = getattr(self,target+'_return')
            return
        setattr(self,target+'_return',base)
        self.mode = target
        self.keys.clear()
        self.release_mouse()
        self.alert = None

    def open_navigation(self):
        if self.mode == 'map':
            self.mode = self.map_return
            self.map_input = ''
            return
        base = self.session_mode()
        if base not in ('market','flight','cruise'):
            self.message = 'Navigation is available while docked or flying.'
            return
        self.mode = base
        self.key(ord('g'))

    def engineering_location(self):
        return self.vms_return if self.engineering_return == 'vms' else self.engineering_return

    def draw_vms(self):
        d,p = self.d,self.p
        d.text(35,85,'VMS / VESSEL MANAGEMENT SYSTEM',GOLD)
        for i,line in enumerate([f'Hull {p.hull:.0f}% / Shields {self.shield:.0f}%',
                                 f'Fuel {p.fuel:.2f}/7',
                                 f'Cargo {sum(p.cargo)}/{p.capacity} tonnes / Mass {p.mass_factor:.2f}',
                                 f'Maintenance wear {p.maintenance:.0f}% / Flights since service {p.flights_since_service}',
                                 f'Front laser: {p.laser} / Rear: '+('pulse' if 'rear' in p.equipment else 'not fitted'),
                                 f'Missiles {p.missiles}/4 / Mines {p.mines}/4',
                                 f'Engineering level {p.engineering_level}/5 / Workshop XP {p.workshop_xp}']):
            d.text(45,145+i*35,line)
        modules = ', '.join(label for key,label,*_ in EQUIPMENT if key in p.equipment) or 'Standard starter equipment'
        d.text(45,405,'FITTED EQUIPMENT',GOLD)
        for i,line in enumerate(textwrap.wrap(modules,90)[:3]): d.text(45,440+i*25,line)
        if self.vms_return == 'market':
            d.text(45,535,f'Fuel {fuel_price(p.system)} cr/unit (sells for {fuel_price(p.system)*3//4}). Refill {p.fuel_cost()} cr / Service {p.service_cost()} cr')
        else:
            d.text(45,535,'Fuel, station repairs and fitting require docking. Field engineering remains available.')
        d.text(45,625,'BACKSPACE returns. G opens Nav. 8 opens engineering.')

    def open_utility(self, target):
        if target == 'help':
            if self.mode == 'help': self.mode = self.help_return
            else: self.help_return,self.mode = self.mode,'help'
        elif target == 'notes':
            self.notes_return,self.mode = self.mode,'notes'
        elif target == 'rename':
            self.rename_return,self.mode = self.mode,'rename'
        elif target == 'intro':
            self.intro_return,self.mode,self.intro_page = self.mode,'intro',0
            self.intro_name_skipped = False
        elif target == 'updates':
            self.update_return,self.mode = self.mode,'updates'
        elif target == 'feedback':
            self.feedback_return,self.mode = self.mode,'feedback'
        elif target == 'menu':
            self.menu_return,self.mode = self.mode,'menu'
        self.keys.clear()
        self.release_mouse()
        self.alert = None

    def menu_actions(self):
        return [
            ('Controls',lambda:self.open_utility('help')),
            ('Notes',lambda:self.open_utility('notes')),
            ('Report a bug / 0',lambda:self.open_utility('feedback')),
            ('Check updates / 2',lambda:self.open_utility('updates')),
            ('Fullscreen / 3',self.mouse_fullscreen),
            ('Save and quit',self.request_exit),
            ('Commander name',lambda:self.open_utility('rename')),
            ('Introduction',lambda:self.open_utility('intro'))]

    def choose_menu_action(self, index):
        self.mode = self.menu_return
        self.menu_actions()[index][1]()

    def draw_menu(self):
        d = self.d
        d.text(35,85,'GAME MENU',GOLD)
        d.text(35,125,'UP / DOWN selects. ENTER opens. BACKSPACE returns. ESC saves and closes.')
        remote = getattr(self,'remote_save',None)
        status_color = RED if remote and remote.conflicted else GOLD if remote and 'unavailable' in remote.status else GREEN
        d.text(35,155,remote.status if remote else 'Offline game: progress saved on this laptop.',status_color)
        presence = getattr(self,'presence',None)
        if presence: d.text(35,180,presence.status,(140,185,255))
        descriptions = ['Key bindings and flight help','Your saved private notes','Bug reports and suggestions','Check for game updates','Toggle display size','Save current state and close','Name shown on your status panel','Who you are and how to play']
        for i,description in enumerate(descriptions):
            x,y = 35+(i%2)*515,200+(i//2)*110
            d.text(x+10,y+42,description,(135,175,185))

    def key(self, k):
        # Escape is a global emergency save-and-close, even inside text fields.
        if k == 27:
            self.request_exit()
            return
        if self.mode == 'bank' and self.bank_custom is not None:
            # Typing an amount: digits arrive as text input, so shortcut keys are paused.
            if k == 8: self.bank_custom = self.bank_custom[:-1]
            elif k == 13: self.set_custom_bank_amount()
            return
        # Backspace is Back on every screen; in a text field it still deletes.
        if k == 8 and not self.active_text_field() and not (self.mode == 'map' and self.map_input) and self.mode not in ('market','flight','cruise','hyperspace','dead','prison'):
            self.mouse_back()
            return
        if k == 8 and self.text_selection_all and self.text_selection_mode == self.mode and self.active_text_field():
            owner,name,_ = self.active_text_field()
            setattr(owner,name,'')
            self.text_selection_all = False
            return
        if self.mode == 'menu':
            if k in (27,96): self.mode = self.menu_return
            elif k in (UP,DOWN,LEFT,RIGHT):
                self.menu_selected = (self.menu_selected+(-1 if k in (UP,LEFT) else 1))%len(self.menu_actions())
            elif k == 13: self.choose_menu_action(self.menu_selected)
            return
        if k == 96 and self.mode not in ('feedback','notes','redeem','rename') and not (self.mode == 'map' and self.map_input):
            self.menu_return,self.mode = self.mode,'menu'
            self.release_mouse()
            self.keys.clear()
            self.alert = None
            return
        if self.mode == 'notes':
            if k == UP: self.notes_scroll += 5
            elif k == DOWN: self.notes_scroll = max(0,self.notes_scroll-5)
            elif k == 27: self.mode = self.notes_return; self.checkpoint()
            elif k == 8: self.p.notes = self.p.notes[:-1]
            elif k == 13: self.text_input('\n')
            return
        if self.mode == 'trades':
            pages = max(1,math.ceil(len(self.p.trade_log)/14))
            if k == UP: self.trades_page = min(pages-1,self.trades_page+1)
            elif k == DOWN: self.trades_page = max(0,self.trades_page-1)
            return
        if self.mode == 'hail':
            if k in (ord('1'),ord('2'),ord('3')): self.hail_ask(HAIL_ASKS[k-ord('1')])
            elif k == ord('4') and self.hail['counter']: self.hail_settle(self.hail['counter'])
            elif k == ord('5'): self.hail_cargo()
            return
        if self.mode == 'intro':
            naming = self.intro_page == 0
            if k == 8 and naming: self.p.name = self.p.name[:-1]
            elif k in (13,RIGHT) or (k == 32 and not naming): self.intro_next()
            elif k == LEFT: self.intro_page = max(0,self.intro_page-1)
            return
        if self.mode == 'prison':
            if k == ord('w'): self.prison_work()
            elif k == ord('b'): self.prison_bribe()
            return
        if self.mode == 'rename':
            if k == 8: self.p.name = self.p.name[:-1]
            elif k == 13: self.finish_rename()
            return
        if self.mode == 'redeem':
            if k == 27: self.mode = 'money'
            elif k == 8: self.credit_code_text = self.credit_code_text[:-1]
            elif k == 13: self.redeem_credit_code()
            return
        if k == ord('-') and self.mode != 'feedback' and not (self.mode == 'map' and self.map_input):
            self.notes_return,self.mode = self.mode,'notes'
            self.alert = None
            self.release_mouse()
            self.keys.clear()
            return
        if k == ord('x') and self.mode != 'feedback' and not (self.mode == 'map' and self.map_input):
            self.open_hub('vms')
            return
        if k == ord('g') and self.mode in ('money','vms'):
            self.open_navigation()
            return
        if self.mode == 'vms':
            if k == 27: self.mode = self.vms_return
            elif k == ord('9'): self.open_hub('money')
            elif k == ord('8'):
                self.engineering_return,self.mode = 'vms','engineering'
            elif k in (ord('f'),ord('k'),ord('r'),ord('u'),ord('l')):
                if self.vms_return != 'market': self.message = 'Dock before using station vessel services.'
                elif k == ord('f'): self.message = self.p.refuel(); self.checkpoint()
                elif k == ord('k'): self.message = self.p.sell_fuel(); self.checkpoint()
                elif k == ord('r'): self.message = self.p.repair(); self.checkpoint()
                elif k == ord('u'): self.outfit_return,self.mode = 'vms','outfit'
                elif k == ord('l'): self.mode = 'market'; self.request_launch()
            return
        if self.mode == 'money':
            if k in (27,ord('9')): self.mode = self.money_return
            elif k == ord('6'): self.trades_page,self.mode = 0,'trades'
            elif self.money_return != 'market' and k != ord('0'): self.message = 'Dock at a station to use Money services.'
            elif k == ord('1'): self.mode = 'bank'
            elif k == ord('2'):
                if self.exchange_available(): self.mode = 'exchange'
                else: self.message = 'No Crymto exchange here. Visit a feudal or anarchy port.'
            elif k == ord('3'): self.mode = 'redeem'
            elif k == ord('4'): self.pay_fines()
            elif k in (ord('5'),ord('j')): self.mode = 'jobs'; self.alert = None
            elif k == ord('0'): self.feedback_return,self.mode = 'money','feedback'
            return
        if (k == ord('9') and self.mode != 'feedback' and not (self.mode == 'map' and self.map_input)) or (k == ord('p') and self.mode in ('market','outfit')):
            self.open_hub('money')
            return
        if self.mode == 'trade_deal' and k != ord('0'):
            if k == ord('y'):
                self.message = self.p.trade(self.deal_good,False,clean_deal=True)
                self.mode = 'market'
                self.checkpoint()
            elif k in (27,ord('n')): self.mode = 'market'
            return
        if self.mode == 'exchange' and k != ord('0'):
            if k in (27,ord('e')): self.mode = 'money'
            elif k == ord('l'): self.convert_crymto(True)
            elif k == ord('b'): self.convert_crymto(False)
            return
        if k == ord('c') and self.mode == 'market':
            if self.selected not in ILLEGAL: self.message = 'Crymto purchases are available for contraband only.'
            else: self.message = self.p.trade(self.selected,True,use_crymto=True); self.checkpoint()
            return
        if k == ord('n') and self.mode == 'market':
            if self.selected not in ILLEGAL or self.p.cargo[self.selected] < 1:
                self.message = 'Select contraband aboard to negotiate a clean-credit sale.'
            else:
                self.deal_good,self.mode = self.selected,'trade_deal'
                self.alert = None
            return
        if k == ord('e') and self.mode in ('market','outfit','bank'):
            if self.exchange_available(): self.mode = 'exchange'; self.alert = None
            else: self.message = 'Crymto exchanges operate at feudal and anarchy ports.'
            return
        if self.mode == 'feedback':
            if k in (27,ord('0')):
                if k == 27: self.mode = self.feedback_return
            elif k == 8: self.feedback_text = self.feedback_text[:-1]
            elif k == 13: self.text_input('\n')
            return
        if k == ord('0') and not (self.mode == 'map' and self.map_input):
            self.feedback_return,self.mode = self.mode,'feedback'
            self.release_mouse()
            self.keys.clear()
            self.alert = None
            return
        if self.mode == 'planet_profile':
            if k in (27,ord('i'),ord('g')): self.mode = 'map'
            elif k in (LEFT,RIGHT): self.profile_system = (self.profile_system+(-1 if k == LEFT else 1))%len(SYSTEMS)
            return
        if self.mode == 'jobs':
            if self.p.dock_job is None and k in (UP,DOWN):
                self.job_selected = (self.job_selected+(-1 if k == UP else 1))%3
            elif self.p.dock_job is None and k == 13: self.start_job(self.job_selected)
            elif k in (27,ord('j')): self.mode = 'money'; self.checkpoint()
            elif k in (ord('1'),ord('2'),ord('3')):
                choice = k-ord('1')
                if self.p.dock_job is None: self.start_job(choice)
                else: self.answer_job(choice)
            return
        if k == ord('j') and self.mode in ('market','outfit','bank'):
            self.mode = 'jobs'
            self.alert = None
            return
        if self.mode == 'bank':
            if k in (ord('9'),27): self.mode = 'money'
            elif k == UP: self.selected = (self.selected-1)%len(GOODS)
            elif k == DOWN: self.selected = (self.selected+1)%len(GOODS)
            elif k == ord('d'): self.bank_transfer(True)
            elif k == ord('w'): self.bank_transfer(False)
            elif k == ord('b'): self.buy_storage(False)
            elif k == ord('r'): self.buy_storage(True)
            elif k == ord('s'): self.transfer_storage(True)
            elif k == ord('t'): self.transfer_storage(False)
            return
        if k == ord('9') and self.mode in ('market','outfit'):
            self.mode = 'bank'
            self.alert = None
            return
        if self.mode == 'departure':
            if k == 27: self.mode = 'market'
            elif k == ord('l') and self.departure_remaining <= 0: self.launch()
            return
        if self.mode == 'engineering':
            if k in (ord('8'),27): self.mode = self.engineering_return
            elif k == ord('t'): self.train_engineering()
            elif k == ord('r'): self.attempt_engineering()
            elif k == ord('h'): self.attempt_engineering(True)
            return
        if k == ord('8') and self.mode in ('flight','market','outfit'):
            self.engineering_return = self.mode
            self.mode = 'engineering'
            self.keys.clear()
            return
        if self.mode == 'launch_warning':
            if k == ord('g'):
                self.map_return,self.mode = self.launch_return,'map'
                return
            if k == ord('l'): self.request_departure()
            elif k == ord('f'):
                self.message = self.p.refuel()
                self.save()
                if not self.launch_warnings(): self.mode = self.launch_return
            elif k == 27: self.mode = self.launch_return
            return
        if self.mode == 'distress':
            if k in (UP,DOWN):
                self.rescue['selected'] = (self.rescue['selected']+(-1 if k == UP else 1))%len(self.rescue['offers'])
            elif k == ord('n'): self.negotiate_rescue()
            elif k == ord('a'): self.accept_rescue()
            elif k in (ord('r'),27):
                self.rescue = None
                self.mode = 'flight'
                self.keys.clear()
                self.message = 'Recovery offers declined. No salvage payment made.'
            return
        if k == ord('6') and self.mode in ('flight','cruise'):
            self.open_distress()
            return
        if self.mode == 'hyperspace' and k not in (27,ord('3')): return
        if self.mode == 'map' and self.map_input:
            self.map_edit(k)
            return
        if k == ord('2'):  # Update screen
            if self.mode == 'updates': self.mode = self.update_return
            else:
                self.update_return = self.mode
                self.mode = 'updates'
            self.keys.clear()
            return
        if self.mode == 'updates':
            if k == 27: self.mode = self.update_return
            return
        if k == ord('3'):
            self.d.is_fullscreen = not self.d.is_fullscreen
            self.d.fullscreen(self.d.win, 0x1001 if self.d.is_fullscreen else 0)
            return
        if k == 27:
            self.request_exit()
            return
        if self.mode == 'dead':
            if k == ord('r'):
                self.recover_destroyed_pilot()
                return
            if k == ord('n'):
                self.p = Pilot()
                self.shield = 100
                self.mode = 'market'
                self.save()
            return
        if k == ord('1'):
            if self.mode == 'help': self.mode = self.help_return
            else:
                self.help_return = self.mode
                self.mode = 'help'
            self.keys.clear()
            return
        if self.mode == 'help':
            if k == 13: self.mode = self.help_return
            elif k in (LEFT,RIGHT): self.help_page=(self.help_page+(-1 if k == LEFT else 1))%len(self.help_sections())
            return
        if k == ord('g'):
            if self.mode == 'map': self.mode = self.map_return
            else:
                self.map_return = self.mode
                self.mode = 'map'
                if self.p.waypoint:
                    self.map_cursor = self.p.waypoint['position'][:]
                    self.cursor_mode = self.p.waypoint['system'] is None
                    if not self.cursor_mode: self.target = self.p.waypoint['system']
                else: self.map_cursor = coordinates(self.target)
            self.keys.clear()
            return
        if self.mode == 'map':
            if k == ord('i'):
                system = self.selected_waypoint()['system']
                if system is None: self.message = 'No planet at these coordinates. Select a named planet for its profile.'
                else: self.profile_system,self.mode = system,'planet_profile'
            elif k == ord('/'):

                self.map_input,self.map_text = 'search',''
            elif k == ord('c'):
                self.map_input,self.map_text = 'coordinates',''
            elif k == 9:
                self.cursor_mode = not self.cursor_mode
            elif k in (LEFT,RIGHT,UP,DOWN):
                if self.cursor_mode:
                    axis = 0 if k in (LEFT,RIGHT) else 1
                    step = -.1 if k in (LEFT,UP) else .1
                    self.map_cursor[axis] = round(max(0,min(10,self.map_cursor[axis]+step)),2)
                else:
                    self.target = (self.target + (-1 if k in (LEFT,UP) else 1))%8
                    self.map_cursor = coordinates(self.target)
            elif k == 13: self.lock_waypoint()
            elif k == ord('h'):
                self.lock_waypoint()
                self.jump()
            elif k == ord('t'):
                self.lock_waypoint()
                self.begin_cruise()
            return
        if self.mode in ('market', 'outfit'):
            if k == ord('u'):
                if self.mode == 'outfit': self.mode = self.outfit_return
                else: self.outfit_return,self.mode = 'market','outfit'
                return
            if k == ord('l'): self.request_launch(); return
            if k == ord('f'):
                self.message = self.p.refuel()
                self.save()
            if k == ord('p'):
                if self.p.credits >= self.p.fine:
                    self.p.credits -= self.p.fine
                    self.p.fine = 0
                    self.message = 'Fines cleared.'
                    self.save()
                else: self.message = f'Outstanding fine: {self.p.fine} cr.'
            if k == ord('r'):
                self.message = self.p.repair()
                self.save()
            if self.mode == 'outfit':
                if k == UP: self.shop_selected = (self.shop_selected-1)%len(EQUIPMENT)
                if k == DOWN: self.shop_selected = (self.shop_selected+1)%len(EQUIPMENT)
                if k in (ord('b'),13):
                    self.message = self.p.buy_equipment(self.shop_selected)
                    self.save()
            else:
                if k == UP: self.selected = (self.selected-1)%len(GOODS)
                if k == DOWN: self.selected = (self.selected+1)%len(GOODS)
                if k in (ord('b'),ord('s')):
                    self.message = self.p.trade(self.selected,k==ord('b'))
                    self.save()
            return
        if self.mode == 'cruise':
            if k == ord('t'):
                self.arrive(self.p.position, None)
                self.message = 'Cruise cancelled. Lock a new course or continue from the map.'
            return
        if self.mode != 'flight': return
        if k == ord('n') and self.mode == 'flight':
            self.hail_disabled_ship()
            return
        if k == ord('7'):
            self.request_docking()
            return
        if k == ord('4'):
            self.rear_view = not self.rear_view
            self.laser_flash = 0
            self.message = ('REAR VIEW - rear pulse laser ready.' if 'rear' in self.p.equipment else 'REAR VIEW - no rear laser fitted. Buy one in outfitting.') if self.rear_view else 'FORWARD VIEW.'
            return
        if k == ord('5'):
            targets = ([self.enemy] if self.enemy is not None else [])+([self.disabled_ship['object']] if self.disabled_ship else [])+[p['object'] for p in self.other_players.values()]
            current = next((i for i,target in enumerate(targets) if target is self.ship_target),-1)
            self.ship_target = targets[current+1] if current+1 < len(targets) else None
            self.message = 'Ship target selected.' if self.ship_target else 'No ship selected.'
            return
        if k == ord('h'):
            self.jump()
            return
        if k == ord('t'): self.begin_cruise()
        if k == ord('b'):
            if self.p.mines:
                self.p.mines -= 1
                self.cloaked = False
                self.cancel_surrender('mine deployed.')
                self.mine_objects.append([0.,0.,-40.,1.5,75.,'player'])
                self.message = 'Mine deployed astern. Arming in 1.5 seconds. Keep clear!'
            else: self.message = 'No mines aboard. Buy them in outfitting.'
        if k == ord('z'):
            if 'jammer' not in self.p.equipment: self.message = 'Signal jammer not fitted.'
            elif self.jammer_cooldown > 0: self.message = f'Jammer cooling down: {self.jammer_cooldown:.0f}s.'
            elif self.p.fuel < .05: self.message = 'Insufficient fuel for jammer.'
            else:
                self.p.fuel -= .05
                self.jamming,self.jammer_cooldown = 8,20
                self.message = 'Jamming active for 8 seconds.'
        if k == ord('k'):
            if 'cloak' not in self.p.equipment: self.message = 'Phase cloak not fitted.'
            elif self.p.fuel <= 0: self.message = 'Insufficient fuel for cloaking.'
            else:
                self.cloaked = not self.cloaked
                self.message = 'Cloak engaged.' if self.cloaked else 'Cloak disengaged.'
        if k == ord('i'):
            self.fine_control = not self.fine_control
            self.message = 'Fine steering ON: arrows and roll at 20%.' if self.fine_control else 'Normal steering.'
        if k == ord('y'):
            self.course_assist = not self.course_assist
            self.autodock = False
            if self.course_assist:
                self.message = 'Approach guidance ON. You control throttle and roll; request docking clearance.'
            else: self.message = 'Approach guidance OFF.'
        if k == ord('p'):
            self.nav = 'planet'
        if k in (UP, DOWN, LEFT, RIGHT, ord('w'),ord('s'),ord('q'),ord('e')):
            self.autodock = False
            if k in (UP,DOWN,LEFT,RIGHT): self.course_assist = False
        if k == ord('d'):
            if self.p.deep_space:
                self.message = 'No station here. Use G to lock a planet.'
                return
            self.nav = 'station'
            self.message = 'Fly through slot: centre +/-14m, height +/-6m, roll +/-14deg, speed 1-25.'
        if k == ord('c'):
            if self.p.deep_space: self.message = 'No station in deep space.'
            elif 'docking' not in self.p.equipment: self.message = 'Buy a docking computer in outfitting (U).'
            elif self.enemy: self.message = 'Clear hostile contact before auto-docking.'
            elif not 65 < self.station[2] <= 2500: self.message = 'Docking computer range: 2500 m.'
            elif not self.docking_permitted(): self.message = 'Docking refused: wanted status.'
            else:
                self.course_assist = False
                self.autodock = not self.autodock
                if self.autodock and not self.dock_clearance: self.request_docking()
                self.nav = 'station'
                self.message = 'Docking computer engaged. C or manual controls cancel.' if self.autodock else 'Manual control.'
        if k == ord('v'):
            if self.rear_view:
                self.message = 'Rear mount: pulse laser.' if 'rear' in self.p.equipment else 'No rear laser fitted.'
                return
            available = [name for name in LASERS if name == 'pulse' or name in self.p.equipment]
            self.p.laser = available[(available.index(self.p.laser)+1)%len(available)]
            self.message = self.p.laser.title() + ' laser selected.'
        if k == ord('m'):
            if not self.enemy: self.message = 'No hostile target.'
            elif not self.p.missiles: self.message = 'No missiles. Buy replacements at a station.'
            else:
                self.cloaked = False
                self.cancel_surrender('missile fired.')
                self.p.missiles -= 1
                self.missiles_in_flight.append(dict(position=[0.,-25.,40.]))
                self.message = 'Missile away! Tracking target.'
        if k == ord('a'):
            self.nav = 'asteroid'
            self.message = 'Asteroid beacon selected. V selects laser; SPACE fires; O scoops nearby ore.'
        if k == ord('j'):
            self.nav = 'sun'
            self.message = 'Sun beacon. With scoops: skim within 500m, speed 10-60; watch heat!'
        if k == ord('o'): self.scoop()

    def selected_waypoint(self):
        position = self.map_cursor[:] if self.cursor_mode else coordinates(self.target)
        closest = min(range(8),key=lambda i: galactic_distance(position,coordinates(i)))
        system = closest if galactic_distance(position,coordinates(closest)) < .12 else None
        if system is not None: position = coordinates(system)
        return dict(name=SYSTEMS[system][0] if system is not None else 'Deep-space waypoint',position=position,system=system)

    def lock_waypoint(self):
        self.p.waypoint = self.selected_waypoint()
        w = self.p.waypoint
        self.nav = 'course'
        self.message = f'Course locked: {w["name"]} ({w["position"][0]:.2f}, {w["position"][1]:.2f}).'
        if self.mode in ('market','outfit') or (self.mode == 'map' and self.map_return in ('market','outfit')): self.save()

    def map_edit(self, key):
        if key == 27:
            self.map_input = None
            return
        if key == 8: self.map_text = self.map_text[:-1]
        elif key == 13:
            if self.map_input == 'search':
                matches = [i for i,s in enumerate(SYSTEMS) if self.map_text.casefold() in s[0].casefold()]
                if not self.map_text or not matches:
                    self.message = 'No matching planet. Try another name.'
                    return
                self.target = matches[0]
                self.map_cursor = coordinates(self.target)
                self.cursor_mode = False
            else:
                try: position = [float(n) for n in self.map_text.replace(',',' ').split()]
                except ValueError: position = []
                if not valid_coordinates(position):
                    self.message = 'Enter X,Y between 0 and 10, for example 4.5,6.2.'
                    return
                self.map_cursor = position
                self.cursor_mode = True
            self.map_input = None
            self.lock_waypoint()
        elif 32 <= key <= 126 and len(self.map_text) < 40:
            self.map_text += chr(key)

    def jump(self):
        if self.broken_down:
            self.message = 'Drive disabled. Engineering 8 or distress 6.'
            return
        if self.jump_charge: return
        w = self.p.waypoint
        if not w: self.message = 'Lock a course first (G, ENTER).'; return
        dist = galactic_distance(self.p.position,w['position'])
        cost = hyperspace_cost(dist)
        allowed = self.mode == 'flight' or (self.mode == 'map' and self.map_return == 'flight')
        if not allowed:
            self.message = 'Launch, or cancel cruise, before charging hyperspace.'
        elif dist < .001: self.message = 'Already at that coordinate.'
        elif cost > self.p.fuel: self.message = f'Jump requires {cost:.2f} fuel; aboard {self.p.fuel:.2f}.'
        elif not self.p.deep_space and (station := math.sqrt(sum(v*v for v in self.station))) < PATROL_RADIUS:
            # Station mass lock: you must leave the patrolled space before jumping.
            self.message = f'Hyperspace blocked by station mass lock. Fly beyond {PATROL_RADIUS:,} m (now {station:,.0f} m).'
        else:
            destination = dict(name=w['name'],position=w['position'][:],system=w['system'])
            self.jump_charge = dict(destination=destination,cost=cost,held=0.)
            self.mode = 'flight'
            self.autodock = False
            self.message = 'Hold H: hyperspace in 3 seconds. Release to cancel.'

    def begin_cruise(self):
        if self.broken_down:
            self.message = 'Drive disabled. Engineering 8 or distress 6.'
            return
        if self.mode == 'map' and self.map_return not in ('flight','cruise'):
            self.message = 'Launch before beginning interstellar cruise.'
            return
        w = self.p.waypoint
        if not w: self.message = 'Lock a course in Navigation first.'; return
        dist = galactic_distance(self.p.position,w['position'])
        cost = dist*.25*self.p.mass_factor
        if dist < .001: self.message = 'Already at that coordinate.'; return
        if cost > self.p.fuel: self.message = f'Cruise requires {cost:.2f} fuel.'; return
        if self.enemy: self.message = 'Clear hostile contact before beginning cruise.'; return
        self.cruise = dict(start=self.p.position[:],destination=dict(w),distance=dist,
                           elapsed=0.,duration=dist*CRUISE_SECONDS_PER_LY*self.p.mass_factor,
                           fuel=cost)
        self.cloaked = False
        self.mode = 'cruise'
        self.message = 'Interstellar cruise. T cancels; G map. Hyperspace is faster but costs more fuel.'
        self.keys.clear()

    def update_cruise(self, dt):
        trip = self.cruise
        step = min(dt,trip['duration']-trip['elapsed'])
        fuel = trip['fuel'] * step/trip['duration']
        if fuel > self.p.fuel:
            self.arrive(self.p.position,None)
            self.message = 'Cruise halted: insufficient fuel.'
            return
        trip['elapsed'] += step
        self.p.fuel = max(0,self.p.fuel-fuel)
        fraction = min(1,trip['elapsed']/trip['duration'])
        self.p.position = [a+(b-a)*fraction for a,b in zip(trip['start'],trip['destination']['position'])]
        if fraction >= 1:
            destination = trip['destination']
            self.arrive(destination['position'],destination['system'])
            self.message = 'Cruise complete. Arrived at '+destination['name']+'.'

    def arrive(self, position, system, from_hyperspace=False):
        self.p.position = list(position)
        self.p.deep_space = system is None
        if system is not None: self.p.system = system
        self.security_elapsed = self.security_dispatch = 0.
        self.surrendering = False
        self.station_laser_warning,self.station_laser_timer = False,15.
        self.enemy_police_system = None
        self.security_warning = 0
        self.launch(departure=False)
        if system is not None:
            # Hyperspace drops you outside the patrol zone, where pirates can be waiting.
            depth = PATROL_RADIUS+random.uniform(800,2000) if from_hyperspace else 2200.
            self.station = [random.uniform(-80,80),random.uniform(-50,50),depth]
        name = SYSTEMS[system][0] if system is not None else f'Deep space ({position[0]:.2f}, {position[1]:.2f})'
        self.arrival = dict(name=name,remaining=5.)

    def update_planet(self, dt):
        if self.p.deep_space: return
        radius = self.planet_radius
        dist = math.sqrt(sum(v*v for v in self.planet))
        if dist < radius:
            self.damage(100*dt)
            self.speed = -20
        if dist < radius*4 and abs(self.speed) > 20:
            self.flyby_min = min(self.flyby_min,dist)
        elif self.flyby_min < radius*4:
            if radius*1.05 < self.flyby_min < radius*3 and self.speed > 20:
                extra = min(55,radius*30/max(radius,self.flyby_min))
                self.assist_speed = min(80,self.assist_speed+extra)
                self.speed += extra
            self.flyby_min = float('inf')

    def update_mines(self, dt):
        for mine in self.mine_objects[:]:
            mine[3] -= dt
            mine[4] -= dt
            if mine[4] <= 0:
                self.mine_objects.remove(mine)
                continue
            if mine[3] > 0: continue
            player_range = math.sqrt(sum(v*v for v in mine[:3]))
            enemy_range = math.dist(mine[:3],self.enemy[:3]) if self.enemy else float('inf')
            if (mine[5] == 'player' and enemy_range < 110) or (mine[5] != 'player' and player_range < 110):
                if player_range < 190: self.damage(75)
                if self.enemy and enemy_range < 190: self.destroy_enemy()
                self.mine_objects.remove(mine)
                self.flash = .3
                self.message = 'Mine detonated!'

    def draw_map(self):
        d,p = self.d,self.p
        d.text(30,75,'NAV / arrows select / TAB cursor / ENTER lock')
        d.text(30,105,'/ search  C coordinates  HOLD H jump  T cruise  G return')
        for n in range(11):
            x,y = 60+n*60,155+n*39
            d.line(x,155,x,545,(20,45,55))
            d.line(60,y,660,y,(20,45,55))
            if n%2 == 0:
                d.text(x-4,550,str(n),(100,145,155))
                d.text(30,y-8,str(n),(100,145,155))
        def plot(position): return 60+position[0]*60,155+position[1]*39
        for i,(name,_,_,_) in enumerate(SYSTEMS):
            x,y = plot(coordinates(i))
            d.rect(x-4,y-4,8,8,GOLD if i == self.target and not self.cursor_mode else GREEN)
            presence = getattr(self,'presence',None)
            count = sum(p['system'] == i and p['mode'] not in ('transit','deep-space') for p in presence.snapshot['players']) if presence else 0
            d.text(x+9,y-15,name+(f' [{count}]' if count else ''))
        x,y = plot(p.position)
        d.rect(x-8,y-8,16,16,(140,185,255))
        d.text(x+12,y+7,'YOU',(140,185,255))
        if p.waypoint:
            wx,wy = plot(p.waypoint['position'])
            d.line(x,y,wx,wy,(90,100,140))
            d.rect(wx-11,wy-11,22,22,GOLD)
        w = self.selected_waypoint()
        wx,wy = plot(w['position'])
        d.line(wx-13,wy,wx+13,wy,GOLD); d.line(wx,wy-13,wx,wy+13,GOLD)
        dist = galactic_distance(p.position,w['position'])
        sec = dist*CRUISE_SECONDS_PER_LY*p.mass_factor
        info = [w['name'],f'X {w["position"][0]:.2f}  Y {w["position"][1]:.2f}',
                f'Distance {dist:.2f} LY',f'Jump fuel {hyperspace_cost(dist):.2f}',
                f'Cruise fuel {dist*.25*p.mass_factor:.2f}',f'Cruise ETA {int(sec//60)}m {int(sec%60)}s',f'Aboard fuel {p.fuel:.2f}/7']
        if w['system'] is not None:
            i = w['system']; govt,pop,size = PROFILES[i]
            info += [SYSTEMS[i][1],f'Technology {TECH[i]}',govt,
                     'I / Profile: full details',
                     'Docking: allowed' if self.station_allows(i) else 'Docking: refused']
        else: info += ['Uninhabited coordinates','No station or services']
        for i,line in enumerate(info): d.text(720,155+i*31,line,GOLD if i==0 else GREEN)
        if self.map_input:
            d.text(30,610,('Search planet: ' if self.map_input == 'search' else 'Coordinates X,Y: ')+self.map_text+'_',GOLD)
            if self.map_input == 'search':
                matches = [s[0] for s in SYSTEMS if self.map_text.casefold() in s[0].casefold()]
                d.text(30,645,'Matches: '+', '.join(matches),GREEN)
            else: d.text(30,645,'Range 0..10 on both axes. ENTER locks; click Back to cancel.')
        else:
            d.text(30,610,'Selection: '+('free coordinate cursor' if self.cursor_mode else 'planet list'))
            d.text(30,645,'Locked: '+(p.waypoint['name'] if p.waypoint else 'none'))

    def draw_planet_profile(self):
        d,i = self.d,self.profile_system
        name,economy,_,_ = SYSTEMS[i]
        government,population,size = PROFILES[i]
        position = coordinates(i)
        d.text(35,85,'PLANET PROFILE / '+name.upper(),GOLD)
        facts = [f'Coordinates: {position[0]:.2f}, {position[1]:.2f}',
                 'Economy: '+economy,'Government: '+government,
                 f'Population: {population:.1f} billion',f'Diameter: {size:,} km',
                 f'Technology level: {TECH[i]}',
                 f'Police reserve: {self.p.station_police_remaining[i]}/{STATION_POLICE_CAPACITY}',
                 'Customs: minimal' if government in ('Anarchy','Feudal') else 'Customs: regulated; contraband can be seized',
                 ('Docking: allowed' if self.station_allows(i) else 'Docking: refused')+(' / '+self.hostility_label(i) if self.station_hostilities[i] else '')]
        for row,line in enumerate(facts): d.text(35,140+row*31,line)
        d.text(35,410,'STATION FACILITIES',GOLD)
        for row,line in enumerate(['Fuel, hull service and equipment fitting',
                                   'Bank, cargo-bay rental and purchase',
                                   'Crymto exchange' if government in ('Anarchy','Feudal') else 'No Crymto exchange',
                                   'Daily cargo, inventory and workshop jobs',
                                   'Engineering training and fine payments']): d.text(35,440+row*27,line)
        d.text(610,140,'MARKET / * sells for Crymto',GOLD)
        d.text(610,178,'COMMODITY              BUY  SELL')
        for row,good in enumerate(GOODS):
            d.text(610,210+row*27,f'{good+chr(42) if row in ILLEGAL else good:<20} {quote(i,row):>4} {quote(i,row,False):>5}',GOLD if row in ILLEGAL else GREEN)
        demand = {'Industrial':'Cheaper manufactured goods / contraband',
                  'Agricultural':'Food / ore exports; narcotics demand',
                  'Frontier':'Strong arms demand; mixed exports'}[economy]
        for row,line in enumerate(textwrap.wrap(demand,42)): d.text(610,490+row*27,line)
        d.text(35,595,'I: map     LEFT / RIGHT: browse planets')

    def camera_vector(self, obj):
        x,y,z = obj[:3]
        roll = self.roll
        if self.rear_view: x,z,roll = -x,-z,-roll
        c,s = math.cos(roll),math.sin(roll)
        return x*c+y*s,-x*s+y*c,z

    def active_navigation(self):
        if self.nav == 'object' and self.nav_target:
            obj,label = self.nav_target
            if any(obj is item for item in self.asteroids+self.fragments+self.mine_objects+[self.sun]): return obj,label
        if self.nav == 'course' and self.p.waypoint:
            w = self.p.waypoint
            delta = [b-a for a,b in zip(self.p.position,w['position'])]
            if math.hypot(*delta) > .001:
                # Galactic X/Y map axes are shown as a compass bearing, not metres.
                return [delta[0]*10000,0.,-delta[1]*10000],w['name']+' / COURSE'
            if not self.p.deep_space: return self.station,w['name']+' / STATION'
            return [0.,0.,500.],w['name']+' / ARRIVED'
        if self.nav == 'asteroid':
            objects = self.fragments or self.asteroids
            if objects: return min(objects,key=lambda r: sum(v*v for v in r[:3])),'ORE' if self.fragments else 'ASTEROID'
        if self.nav == 'sun': return self.sun,'SUN'
        if self.nav == 'planet' and not self.p.deep_space: return self.planet,SYSTEMS[self.p.system][0].upper()
        if self.p.deep_space: return None,'DEEP SPACE'
        return self.station,'STATION'

    def scanner_contacts(self):
        contacts = []
        if not self.p.deep_space:
            contacts += [('station',self.station,'STATION',GREEN),('planet',self.planet,SYSTEMS[self.p.system][0],(100,170,255))]
        if self.disabled_ship:
            contacts.append(('disabled',self.disabled_ship['object'],'DISABLED SHIP',GOLD))
        if self.enemy is not None:
            contacts.append(('ship',self.enemy,self.enemy_kind.upper(),RED if self.enemy_kind == 'pirate' else (120,170,255)))
        for mine in self.mine_objects:
            contacts.append(('object',mine,'MINE',RED))
        for rock in self.asteroids: contacts.append(('object',rock,{8:'GOLD ROCK',9:'SILVER ROCK'}.get(rock[4] if len(rock) > 4 else 2,'ASTEROID'),GOLD))
        for ore in self.fragments: contacts.append(('object',ore,'ORE',(150,190,255)))
        contacts += [('player',p['object'],'PLAYER '+p['name'],(140,185,255)) for p in self.other_players.values()]
        contacts.append(('object',self.sun,'SUN',GOLD))
        return contacts

    def scanner_position(self, obj):
        x,_,z = self.camera_vector(obj)
        # Fixed 2500m radius. Contacts beyond the radius sit at its rim.
        scale = max(2500,math.hypot(x,z))
        return 955+x/scale*85,165-z/scale*53

    def click(self, x, y):
        for bx,by,w,h,action in reversed(self.buttons):
            if bx <= x <= bx+w and by <= y <= by+h:
                action()
                return
        if self.mode == 'map' and not self.map_input and 60 <= x <= 660 and 155 <= y <= 545:
            position = [(x-60)/60,(y-155)/39]
            nearest = min(range(8),key=lambda i:galactic_distance(position,coordinates(i)))
            if galactic_distance(position,coordinates(nearest)) < .25:
                self.target,self.cursor_mode = nearest,False
                self.map_cursor = coordinates(nearest)
            else:
                self.map_cursor = [round(n,2) for n in position]
                self.cursor_mode = True
            self.lock_waypoint()
            return
        if self.mode != 'flight' or not (840 <= x <= 1070 and 80 <= y <= 245): return
        choices = []
        for kind,obj,label,color in self.scanner_contacts():
            sx,sy = self.scanner_position(obj)
            distance = math.hypot(sx-x,sy-y)
            if distance <= 12: choices.append((distance,kind,obj,label))
        if not choices: return
        _,kind,obj,label = min(choices,key=lambda contact:contact[0])
        if kind in ('ship','disabled','player'):
            self.ship_target = obj
            self.message = label+' selected. Direction marker tracks this ship; 5 clears selection.'
        elif kind == 'object':
            self.nav = 'object'
            self.nav_target = (obj,label)
            self.message = label+' beacon selected.'
        elif kind in ('station','planet'):
            self.nav = kind
            self.message = label+' beacon selected.'

    def draw_marker(self, obj, label, color):
        d = self.d
        vx,vy,vz = self.camera_vector(obj)
        projected = self.project(obj)
        if projected and 55 <= projected[0] <= W-55 and 110 <= projected[1] <= 510:
            x,y,_ = projected
            d.fill(x-3,y-3,7,7,color)
            d.rect(x-10,y-10,20,20,color)
            d.text(max(35,min(W-330,x+16)),max(105,min(515,y-10)),label[:28],color)
            return
        if projected:
            dx,dy = projected[0]-W/2,projected[1]-330
        else:
            dx,dy = vx,vy
            if abs(dx)+abs(dy) < 1: dx,dy = 0,1
        length = math.hypot(dx,dy)
        if length < 1: dx,dy,length = 0,1,1
        dx,dy = dx/length,dy/length
        limit = min(490/max(abs(dx),.0001),190/max(abs(dy),.0001))
        x,y = W/2+dx*limit,330+dy*limit
        bx,by = x-dx*18,y-dy*18
        d.line(x,y,bx-dy*8,by+dx*8,color)
        d.line(x,y,bx+dy*8,by-dx*8,color)
        d.line(bx-dy*8,by+dx*8,bx+dy*8,by-dx*8,color)
        text = label+(' / BEHIND: 4' if vz <= 0 else '')
        d.text(max(35,min(W-350,x-140)),max(102,min(515,y+14)),text[:34],color)

    def draw_heat_instrument(self):
        d = self.d
        color = RED if self.heat >= 90 else GOLD if self.heat >= 70 else GREEN
        near_sun = self.sun_altitude() < 2000
        d.fill(840,430,230,130 if near_sun else 82,(5,16,27))
        d.rect(840,430,230,130 if near_sun else 82,(45,105,115))
        d.text(850,435,f'HEAT {self.heat:.0f}% / LIMIT 90',color)
        d.text(850,458,f'SHIELDS {self.shield:.0f}%',color)
        d.rect(850,490,210,8,(45,105,115))
        d.fill(851,491,int(min(120,self.heat)/120*208),6,color)
        d.line(850+210*90/120,487,850+210*90/120,501,GOLD)
        if near_sun:
            altitude = self.sun_altitude()
            state,label = self.scoop_status()
            d.text(850,510,'INSIDE THE SUN' if altitude < 0 else f'SUN ALTITUDE {altitude:.0f} m',RED if altitude < 0 else GOLD)
            d.text(850,533,label,GREEN if state == 'collecting' else (120,140,150) if state == 'none' else GOLD)

    def draw_scanner(self):
        d = self.d
        d.fill(840,80,230,165,(5,16,27))
        d.rect(840,80,230,165,(45,105,115))
        d.text(850,85,'RADAR 2.5km '+('AFT' if self.rear_view else 'FWD'),GREEN)
        d.line(870,165,1040,165,(35,75,85))
        d.line(955,112,955,218,(35,75,85))
        d.line(950,171,955,160,(235,245,250))
        d.line(955,160,960,171,(235,245,250))
        d.text(920,105,'AHEAD',GREEN)
        d.text(920,203,'BEHIND',GREEN)
        if 'scanner' in self.faults:
            for _ in range(14):
                d.fill(random.randint(860,1048),random.randint(112,214),3,2,(70,90,95))
            d.text(890,150,'SCANNER FAULT',RED)
        else:
            for kind,obj,label,color in self.scanner_contacts():
                x,y = self.scanner_position(obj)
                d.fill(x-3,y-3,6,6,color)
                if kind in ('ship','disabled','player') and obj is self.ship_target: d.rect(x-7,y-7,14,14,GOLD)
        d.text(850,224,'TOP VIEW / click',(135,175,185))
        self.draw_bearing()

    def draw_bearing(self):
        d = self.d
        d.fill(840,255,230,160,(5,16,27))
        d.rect(840,255,230,160,(45,105,115))
        d.text(850,260,'TARGET BEARING',GOLD)
        d.line(885,340,1025,340,(45,105,115))
        d.line(955,290,955,385,(45,105,115))
        d.rect(949,334,12,12,GREEN)
        if 'bearing' in self.faults:
            d.text(875,325,'BEARING OFFLINE',RED)
            return
        obj,label = (self.ship_target,'SHIP') if self.ship_target is not None else self.active_navigation()
        if obj is None: return
        x,y,z = self.camera_vector(obj)
        length = max(1,math.sqrt(x*x+y*y+z*z))
        px,py = 955+x/length*65,340+y/length*40
        d.fill(px-4,py-4,8,8,GOLD)
        direction = ('RIGHT' if x > length*.03 else 'LEFT' if x < -length*.03 else '')
        direction += (' DOWN' if y > length*.03 else ' UP' if y < -length*.03 else '')
        d.text(850,390,'BEHIND: 4' if z < 0 else ('TURN '+direction.strip() if direction.strip() else 'ON HEADING'),GOLD)
        # Positive cockpit Y is downward, matching the view and arrow keys.

    def update_jump_charge(self, dt):
        charge = self.jump_charge
        if not charge: return
        if self.mode != 'flight' or ord('h') not in self.keys:
            self.jump_charge = None
            self.message = 'Hyperspace cancelled. Hold H continuously for 3 seconds.'
            return
        charge['held'] = min(3,charge['held']+dt)
        if charge['held'] < 3: return
        if self.p.fuel < charge['cost']:
            self.jump_charge = None
            self.message = 'Hyperspace cancelled: insufficient fuel at ignition.'
            return
        self.p.fuel = round(self.p.fuel-charge['cost'],5)
        self.jump_warp = dict(destination=charge['destination'],elapsed=0.)
        self.jump_charge = None
        self.mode = 'hyperspace'
        self.keys.clear()
        self.laser_flash = self.flash = 0
        self.message = 'Hyperspace transit to '+charge['destination']['name']+'.'

    def draw_hyperspace(self):
        d = self.d
        elapsed = self.jump_warp['elapsed']
        clip = bind(d.sdl,'SDL_RenderSetClipRect',C.c_int,[C.c_void_p,C.c_void_p])
        viewport = (C.c_int*4)(25,65,W-50,640)
        clip(d.r,viewport)
        for i,star in enumerate(self.stars):
            angle = math.atan2(star[1],star[0])
            progress = ((i/len(self.stars))+elapsed*1.1)%1
            radius = 20+progress*progress*850
            tail = max(10,radius-(30+progress*180))
            c,s = math.cos(angle),math.sin(angle)
            d.line(550+c*tail,345+s*tail,550+c*radius,345+s*radius,(100,180+int(progress*65),230))
        clip(d.r,None)
        d.fill(240,285,620,88,(4,9,18))
        d.text(420,300,'H Y P E R S P A C E',GREEN)
        d.text(300,338,'Destination: '+self.jump_warp['destination']['name'],GOLD)

    def sun_altitude(self):
        return math.sqrt(sum(v*v for v in self.sun))-SUN_RADIUS

    def scoop_status(self):
        """Why fitted scoops are or are not collecting sun fuel right now."""
        altitude = self.sun_altitude()
        if 'scoops' not in self.p.equipment: return 'none','SCOOP: NOT FITTED'
        if self.p.fuel >= 7: return 'full','SCOOP: TANK FULL'
        if altitude < 0: return 'low','SCOOP: CLIMB OUT'
        if altitude > SCOOP_ALTITUDE: return 'high',f'SCOOP: BELOW {SCOOP_ALTITUDE} m'
        if not SCOOP_SPEEDS[0] <= self.speed <= SCOOP_SPEEDS[1]: return 'speed',f'SCOOP: SPEED {SCOOP_SPEEDS[0]}-{SCOOP_SPEEDS[1]}'
        return 'collecting','SCOOP: COLLECTING'

    def auto_scoop_ore(self):
        # Fitted scoops pick up ore fragments by themselves when you fly slowly past.
        if 'scoops' not in self.p.equipment or abs(self.speed) > 50 or sum(self.p.cargo) >= self.p.capacity: return
        nearby = next((f for f in self.fragments if math.sqrt(sum(v*v for v in f[:3])) < 260),None)
        if nearby is None: return
        self.collect_fragment(nearby)

    def collect_fragment(self, fragment):
        good = fragment[3] if len(fragment) > 3 else 2
        self.p.cargo[good] += 1
        self.fragments.remove(fragment)
        self.message = f'Scooped 1 tonne of {GOODS[good].lower()}. Sell it at a station.'

    def scoop(self):
        if 'scoops' not in self.p.equipment:
            self.message = 'Fuel / cargo scoops required.'
            return
        nearby = next((f for f in self.fragments if math.sqrt(sum(v*v for v in f[:3])) < 260),None)
        if nearby is None: self.message = 'Fly within 260 m of an ore fragment.'
        elif sum(self.p.cargo) >= self.p.capacity: self.message = 'Cargo hold full.'
        elif abs(self.speed) > 50: self.message = 'Slow below 50 to collect ore.'
        else: self.collect_fragment(nearby)

    def project(self, obj):
        x,y,z = obj[:3]
        roll = self.roll
        if self.rear_view:
            x,z,roll = -x,-z,-roll
        if z <= 5: return None
        c,s = math.cos(roll), math.sin(roll)
        return W/2+(x*c+y*s)*500/z, 330+(-x*s+y*c)*500/z, 500/z

    def on_target(self, obj, radius=32):
        projected = self.project(obj)
        return projected is not None and abs(projected[0]-W/2) < radius and abs(projected[1]-330) < radius

    def turn_world(self, yaw, pitch):
        # Rotate every relative vector by the inverse cockpit turn. This
        # preserves ranges: steering changes heading rather than strafing.
        c,s = math.cos(self.roll),math.sin(self.roll)
        cy,sy,cp,sp = math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
        objects = [self.station,self.sun,self.planet] + self.world_basis + self.stars + self.asteroids + self.fragments + self.mine_objects
        if self.enemy: objects.append(self.enemy)
        if self.enemy_shot: objects.append(self.enemy_shot['position'])
        if self.disabled_ship: objects.append(self.disabled_ship['object'])
        objects += [e['position'] for e in self.explosions]+[m['position'] for m in self.missiles_in_flight]
        for obj in objects:
            x,y,z = obj[:3]
            x,y = x*c+y*s,-x*s+y*c
            x,z = x*cy-z*sy,x*sy+z*cy
            y,z = y*cp-z*sp,y*sp+z*cp
            obj[0],obj[1],obj[2] = x*c-y*s,x*s+y*c,z

    def move_world(self, dx, dy, dz):
        for obj in [self.station,self.sun,self.planet] + ([self.enemy_shot['position']] if self.enemy_shot else []) + ([self.disabled_ship['object']] if self.disabled_ship else []) + self.asteroids + self.fragments + self.mine_objects + [e['position'] for e in self.explosions] + [m['position'] for m in self.missiles_in_flight]:
            obj[0] -= dx
            obj[1] -= dy
            obj[2] -= dz

    def _update_simulation(self, dt):
        if self.mode == 'departure':
            self.departure_remaining = max(0,self.departure_remaining-dt)
            if self.departure_remaining == 0: self.message = 'Departure clearance granted. L launches; Cancel stays docked.'
            return
        if self.mode in ('flight','cruise'): self.rescue_cooldown = max(0,self.rescue_cooldown-dt)
        if self.arrival:
            self.arrival['remaining'] -= dt
            if self.arrival['remaining'] <= 0: self.arrival = None
        if self.jump_charge and (self.mode != 'flight' or ord('h') not in self.keys):
            self.jump_charge = None
            self.message = 'Hyperspace cancelled: H released or cockpit focus lost.'
        if self.mode == 'hyperspace':
            self.jump_warp['elapsed'] += dt
            if self.jump_warp['elapsed'] >= 1.6:
                destination = self.jump_warp['destination']
                self.p.jumps += 1
                self.arrive(destination['position'],destination['system'],from_hyperspace=True)
                self.message = 'Arrived at '+destination['name']+'.'
            return
        if self.mode == 'cruise':
            self.update_cruise(dt)
            return
        if self.mode != 'flight': return
        self.dock_clearance = max(0,self.dock_clearance-dt)
        if self.docking_pending > 0:
            self.docking_pending = max(0,self.docking_pending-dt)
            if self.docking_pending == 0:
                if self.arrest_pending():
                    self.dock_clearance = 120
                    self.message = 'STATION CONTROL: clearance to surrender. You will be ARRESTED on docking.'
                elif self.station_allows():
                    self.dock_clearance = 120
                    self.message = 'Docking clearance granted for 120 seconds.'
                else: self.message = 'Docking clearance refused: wanted status.'
        if self.breakdown_in is not None:
            self.breakdown_in -= dt
            if self.breakdown_in <= 0:
                self.breakdown_in = None
                self.broken_down = True
                self.autodock = False
                self.jump_charge = None
                self.speed = 0
                self.message = 'DRIVE BREAKDOWN. Engineering 8 for repairs, or 6 for rescue.'
        self.update_station_security(dt)
        self.assist_spawn_timer -= dt
        if self.assist_spawn_timer <= 0 and self.disabled_ship is None and self.enemy is None and math.sqrt(sum(v*v for v in self.station)) > 1000:
            self.disabled_ship = dict(object=[-160.,70.,850.],hull=40)
            self.message = 'Disabled ship detected (gold contact). N hails it to offer help; 8 engineering.'
        self.cooldown = max(0,self.cooldown-dt)
        self.flash = max(0,self.flash-dt)
        self.laser_flash = max(0,self.laser_flash-dt)
        self.update_explosions_and_missiles(dt)
        if self.mode == 'flight':
            self.update_faults(dt)
            self.update_disabled_ship(dt)
        if self.p.hull <= 0:
            self.mode = 'dead'
            return
        self.jamming = max(0,self.jamming-dt)
        self.jammer_cooldown = max(0,self.jammer_cooldown-dt)
        self.assist_speed = max(0,self.assist_speed-dt*.8)
        if self.cloaked:
            self.p.fuel = max(0,self.p.fuel-.012*dt)
            if self.p.fuel == 0: self.cloaked = False
        mass = self.p.mass_factor
        self.station_angle = (self.station_angle + 0.25*dt) % (2*math.pi)
        if self.autodock and self.enemy:
            self.autodock = False
            self.message = 'Hostile contact: docking computer disengaged.'
        if self.autodock:
            x,y,z = self.station
            limit = 80*dt/mass
            dx,dy = max(-limit,min(limit,x*dt*2/mass)),max(-limit,min(limit,y*dt*2/mass))
            self.roll += max(-dt/mass,min(dt/mass,self.slot_error()))
            desired = min(70/mass,max(12,(z-60)*0.22))
            if z < 150: desired = 12
            if self.dock_clearance <= 0: desired = 0
            if z < 130 and (abs(x)>12 or abs(y)>5 or abs(self.slot_error())>0.12): desired = 0
            self.speed += max(-70*dt/mass,min(70*dt/mass,desired-self.speed))
        else:
            self.speed = max(-60/mass,min(180/mass+self.assist_speed,self.speed+((ord('w') in self.keys)-(ord('s') in self.keys))*70*dt/mass))
            precision = (.2 if self.fine_control else 1.)*self.handling()
            self.roll += ((ord('e') in self.keys)-(ord('q') in self.keys))*dt/mass*precision
            yaw = ((RIGHT in self.keys)-(LEFT in self.keys))*.65*dt/mass*precision
            pitch = ((DOWN in self.keys)-(UP in self.keys))*.5*dt/mass*precision
            if not self.broken_down and self.p.fuel > 0:
                self.turn_world(yaw,pitch)
            dx,dy = 0.,0.
        if self.course_assist and not self.autodock:
            target,label = self.active_navigation()
            remote = self.nav == 'course' and self.p.waypoint and galactic_distance(self.p.position,self.p.waypoint['position']) > .001
            if target is None or remote or target[2] <= 0:
                self.course_assist = False
                self.message = 'Guidance unavailable: use H/T for a galaxy course, or select a local target ahead.'
            else:
                x,y,z = target[:3]
                c,s = math.cos(self.roll),math.sin(self.roll)
                x,y = x*c+y*s,-x*s+y*c
                turn = self.handling()
                yaw = max(-.65*dt/mass*turn,min(.65*dt/mass*turn,math.atan2(x,z)))
                pitch = max(-.5*dt/mass*turn,min(.5*dt/mass*turn,math.atan2(y,math.hypot(x,z))))
                if not self.broken_down and self.p.fuel > 0: self.turn_world(yaw,pitch)
        if self.broken_down: self.speed,dx,dy = 0,0,0
        dz = self.speed*dt
        required = math.sqrt(dx*dx+dy*dy+dz*dz)*.00012*mass
        if required > self.p.fuel and required:
            factor = self.p.fuel/required
            dx,dy,dz = dx*factor,dy*factor,dz*factor
            self.speed *= factor
        self.p.fuel = max(0,self.p.fuel-required)
        if self.p.fuel == 0 and not self.broken_down:
            self.autodock = False
            self.message = 'Fuel exhausted. Press 6 for a distress call and recovery offers.'
        ship_previous = []
        if self.enemy: ship_previous.append(('enemy',self.enemy,self.enemy[:3]))
        if self.disabled_ship: ship_previous.append(('disabled',self.disabled_ship['object'],self.disabled_ship['object'][:]))
        self.move_world(dx,dy,dz)
        if self.enemy:
            self.enemy[0] -= dx
            self.enemy[1] -= dy
            self.enemy[2] -= dz
        self.ship_collisions(ship_previous)
        if self.mode == 'dead': return
        if self.station[2] <= 65 and math.hypot(*self.station[:2]) < 110 and self.station[2] > -100:
            if self.docking_safe(): self.dock(); return
            self.damage(5+abs(self.speed)*.2 if abs(self.speed) <= 25 else 35+abs(self.speed)*.7)
            self.station[2] = 130
            self.speed = 0
            self.autodock = False
            self.course_assist = False
            self.message = 'Station contact! Use I fine steering; centre slot, roll within +/-14deg, speed 1-25; request clearance with 7.'
            if self.mode == 'dead': return
        # Rocks can damage the ship; fragments drift past if not collected.
        for rock in self.asteroids[:]:
            if rock[2] < 35:
                if abs(rock[0]) < 45 and abs(rock[1]) < 45: self.damage(40)
                self.asteroids.remove(rock)
        if self.mode == 'dead': return
        self.update_planet(dt)
        if self.mode == 'dead': return
        self.update_mines(dt)
        if self.mode == 'dead': return
        self.fragments[:] = [f for f in self.fragments if f[2] > -300]
        for star in self.stars:
            star[0] -= dx*0.5
            star[1] -= dy*0.5
            star[2] -= (self.speed+12)*dt
            if abs(star[2]) > 1800 or abs(star[0]) > 1800 or abs(star[1]) > 1200:
                star[:] = [random.uniform(-1000,1000),random.uniform(-650,650),1800 if self.speed+12 >= 0 else -1800]
        sun_range = math.sqrt(sum(v*v for v in self.sun))
        if sun_range < 600:
            old_heat = self.heat
            self.heat = min(120,self.heat + (6 if sun_range > 250 else 30)*(.6 if self.shield > 0 else 1)*dt)
            if old_heat < 70 <= self.heat: self.message = 'THERMAL WARNING: shield protection degrading. Leave the sun before shields fail!'
            if old_heat < 90 <= self.heat: self.message = 'THERMAL WARNING: temperature tolerance exceeded! Turn away from the sun!'
            if self.scoop_status()[0] == 'collecting':
                if self.p.fuel < 7 and not self.message.startswith('Sun skimming'):
                    self.message = 'Sun skimming: collecting fuel. Turn away before overheating!'
                self.p.fuel = min(7,self.p.fuel+0.15*dt)
            if self.heat > 70: self.damage((2+(self.heat-70)*.25)*dt)
            if self.mode == 'dead': return
        else: self.heat = max(0,self.heat-10*dt)
        self.auto_scoop_ore()
        self.spawn -= dt
        patrolled = self.in_patrol_zone()
        if self.enemy and self.enemy_kind == 'pirate' and patrolled:
            self.enemy = self.ship_target = None
            self.spawn = 24
            self.message = 'Pirate breaks off: you are inside the station patrol zone.'
        if self.spawn <= 0 and not self.enemy and self.station[2] > 450:
            if self.p.fine > 0 and random.random() < .5 and self.p.station_police_remaining[self.p.system] > 0 and not self.p.deep_space:
                self.dispatch_station_police()
            elif patrolled: self.spawn = 5
            else:
                self.enemy_kind = 'pirate'
                self.enemy = [random.uniform(-120,120),random.uniform(-70,70),-850. if random.random()<.3 else 850.,6,0.]
                self.message = 'Hostile contact! SPACE lasers; M missile; V switch laser.'
                self.checkpoint()
        if self.enemy:
            e = self.enemy
            e[0] += math.sin(time.monotonic()*1.7)*25*dt
            e[1] += math.cos(time.monotonic()*1.3)*20*dt
            e[2] = max(250,e[2]-20*dt) if e[2] > 0 else min(-100,e[2]+120*dt)
            self.npc_mine_timer -= dt
            if self.npc_mine_timer <= 0 and e[2] > 200 and self.enemy_kind == 'pirate':
                self.mine_objects.append([e[0],e[1],e[2]-40,1.5,75.,'pirate'])
                self.npc_mine_timer = 30
                self.message = 'Mine detected ahead!'
            e[4] += dt
            if self.cloaked: e[4] = 0
            if e[4] >= (6 if self.jamming else 2):
                e[4] = 0
                self.enemy_shot = dict(position=e[:3],kind=self.enemy_kind,remaining=.25)
                self.damage(7 if abs(e[0])<250 and abs(e[1])<180 else 2)
                if self.mode == 'dead': return
        self.ship_collisions(ship_previous)
        if self.mode == 'dead': return
        if 32 in self.keys and self.cooldown <= 0:
            self.fire_laser()
        self.shield = min(100,self.shield+(0 if sun_range < 600 else dt)*(3 if 'energy' in self.p.equipment else 1.5)*(0.3 if self.cloaked else 1))
        if self.p.hull <= 0: self.mode = 'dead'
        self.update_jump_charge(dt)

    def fire_laser(self):
        if self.rear_view and 'rear' not in self.p.equipment:
            self.cooldown = .3
            self.message = 'No rear laser fitted. U opens outfitting when docked.'
            return
        self.cloaked = False
        self.cancel_surrender('weapons fired.')
        if 'laser' in self.faults and random.random() < .5:
            self.cooldown = .8
            self.message = 'LASER MALFUNCTION: damaged emitter misfired.'
            return
        weapon = 'pulse' if self.rear_view else self.p.laser
        delay,power = LASERS[weapon]
        self.cooldown,self.laser_flash = delay,.09
        candidates = []
        if self.enemy: candidates.append(('ship',self.enemy))
        if self.disabled_ship: candidates.append(('disabled',self.disabled_ship['object']))
        if not self.p.deep_space: candidates.append(('station',self.station))
        candidates += [('player',p['object']) for p in self.other_players.values()]
        candidates += [('asteroid',rock) for rock in self.asteroids]
        hits = [(depth,kind,obj) for kind,obj in candidates if (depth := self.laser_hit_depth(obj,kind)) is not None]
        if not hits: return
        _,kind,obj = min(hits,key=lambda hit:hit[0])
        if kind == 'player':
            self.message = 'Shared-universe test: player combat is not enabled yet.'
        elif kind == 'ship':
            obj[3] -= power
            if obj[3] <= 0: self.destroy_enemy()
        elif kind == 'disabled':
            self.disabled_ship['hull'] -= power*8
            if self.disabled_ship['hull'] <= 0:
                self.explode(obj)
                # The wreck spills cargo canisters that fitted scoops can collect.
                spill = [random.choice((0,1,3,4,5,5,6,8)) for _ in range(random.randint(2,4))]
                self.fragments += [[obj[0]+random.uniform(-40,40),obj[1]+random.uniform(-25,25),obj[2],good] for good in spill]
                self.disabled_ship = self.ship_target = None
                self.p.kills += 1
                lawful = not self.p.deep_space and PROFILES[self.p.system][0] not in ('Anarchy','Feudal')
                if lawful: self.p.fine += 100
                self.message = 'Disabled ship destroyed: cargo canisters spilled.'+(' Attacking a helpless vessel: 100 cr fine.' if lawful else ' Fly slowly to scoop them.')
                self.checkpoint()
            else: self.disabled_ship_struck()
        elif kind == 'station':
            self.station_struck()
        elif kind == 'asteroid' and weapon == 'mining':
            obj[3] -= 1
            if obj[3] <= 0:
                self.asteroids.remove(obj)
                yields = obj[4] if len(obj) > 4 else 2
                self.fragments += [[obj[0]+offset,obj[1]+10,obj[2],yields] for offset in (-18,0,18)]
                self.explode(obj,.7)
                self.message = 'Asteroid fragmented! Fly slowly within 260 m and your scoops collect the ore.'
            else: self.message = f'Mining laser hit: asteroid cracking ({obj[3]} more hit{"s" if obj[3] > 1 else ""}).'
        elif kind == 'asteroid':
            self.message = 'Only a mining laser breaks asteroids.'+(' V selects it.' if 'mining' in self.p.equipment else ' Fit one at a tech 4+ station.')

    def laser_hit_depth(self, obj, kind):
        point = self.project(obj)
        if point is None: return None
        sx,sy,scale = point
        angle = self.roll if self.rear_view else -self.roll
        if kind == 'station':
            angle += -self.station_angle if self.rear_view else self.station_angle
            vertices = [(math.cos(i*math.pi/4)*100,math.sin(i*math.pi/4)*100) for i in range(8)]
        elif kind in ('ship','disabled','player'):
            vertices = [(-65,10),(-20,-15),(0,-5),(20,-15),(65,10),(0,28)]
        else:
            vertices = [(math.cos(i*2*math.pi/7)*42*(.85+.15*(i%3)),math.sin(i*2*math.pi/7)*42) for i in range(7)]
        # Test the central laser ray against the same outline drawn on screen.
        x,y = (W/2-sx)/scale,(330-sy)/scale
        c,s = math.cos(angle),math.sin(angle)
        x,y = x*c+y*s,-x*s+y*c
        inside = False
        for (ax,ay),(bx,by) in zip(vertices,vertices[1:]+vertices[:1]):
            cross = (x-ax)*(by-ay)-(y-ay)*(bx-ax)
            if abs(cross)<1e-8 and min(ax,bx)-1e-8<=x<=max(ax,bx)+1e-8 and min(ay,by)-1e-8<=y<=max(ay,by)+1e-8:
                return self.camera_vector(obj)[2]
            if (ay>y) != (by>y) and x < (bx-ax)*(y-ay)/(by-ay)+ax: inside = not inside
        return self.camera_vector(obj)[2] if inside else None

    def release_mouse(self):
        for key in self.mouse_held: self.keys.discard(key)
        self.mouse_held.clear()

    def mouse_key(self, key, hold=False):
        if hold:
            self.keys.add(key)
            self.mouse_held.add(key)
        if key == ord('h') and hold: self.mouse_controls = False
        self.key(key)

    def mouse_button(self, x,y,w,label,key=None,action=None,hold=False):
        if key == 27 and action is None:
            key,action = None,self.mouse_back
        if y >= 638:
            callback = action if action is not None else lambda:self.mouse_key(key,hold)
            self.footer_actions.append((label,key,callback,hold))
            return
        d = self.d
        d.fill(x,y,w,32,(13,35,46))
        d.rect(x,y,w,32,(55,125,135))
        d.text(x+5,y+3,label,GREEN)
        callback = action if action is not None else lambda:self.mouse_key(key,hold)
        self.buttons.append((x,y,w,32,callback))

    def draw_action_bar(self):
        if not self.footer_actions: return
        d = self.d
        hints = {13:'Enter',27:'Esc',32:'Space',UP:'Up',DOWN:'Down',LEFT:'Left',RIGHT:'Right'}
        rows,items,width = [],[],0
        for label,key,callback,hold in self.footer_actions:
            hint = hints.get(key,chr(key).upper() if type(key) is int and 32 < key < 127 else '')
            if hint and label.endswith(' '+hint): label = label[:-len(hint)-1]
            hint_width = max(30,len(hint)*11+12) if hint else 0
            button_width = max(132,min(330,len(label)*11+24+hint_width))
            if items and width+10+button_width > W-70:
                rows.append(items)
                items,width = [],0
            items.append((label,hint,callback,button_width,hint_width,hold))
            width += (10 if width else 0)+button_width
        if items: rows.append(items)
        start = 674-(len(rows)-1)*36
        d.fill(25,start-6 if self.mode != 'flight' else start,W-50,710-start+6,(7,19,28))
        if self.mode != 'flight': d.line(25,start-6,W-25,start-6,(35,65,80))
        for row,items in enumerate(rows):
            x,y = 35,start+row*36
            for index,(label,hint,callback,w,hint_width,hold) in enumerate(items):
                back = label.lower().startswith(('return','back','cancel','decline','refuse'))
                danger = 'reset' in label.lower() or 'quit' in label.lower()
                if back and index == len(items)-1: x = max(x,W-35-w)
                primary = index == 0 and not back and not danger
                border = GOLD if primary else RED if danger else (55,95,110)
                d.fill(x,y,w,32,(15,56,61) if primary else (12,29,40))
                d.rect(x,y,w,32,border)
                d.text(x+10,y+4,label,RED if danger else GREEN)
                if hint:
                    badge = x+w-hint_width-6
                    d.fill(badge,y+5,hint_width,22,(7,19,28))
                    d.text(badge+6,y+4,hint,GOLD if primary else (145,180,190))
                self.buttons.append((x,y,w,32,callback))
                x += w+10
        if self.mode == 'flight':
            if self.p.waypoint:
                w = self.p.waypoint
                dist = galactic_distance(self.p.position,w['position'])
                d.text(245,681,f'COURSE {w["name"][:18]}  {dist:.2f} LY / T cruise',GOLD)
            elif self.p.fuel < 1:
                d.text(245,681,'LOW FUEL / 6 distress',RED)

    def mouse_row(self,x,y,w,h,action):
        self.buttons.append((x,y,w,h,action))

    def draw_mouse_ui(self):
        self.buttons = []
        self.footer_actions = []
        d = self.d
        if self.mode not in ('feedback','notes','redeem','rename','menu','prison','intro'):
            self.mouse_button(155,18,95,'Money',action=lambda:self.open_hub('money'))
            self.mouse_button(365,18,75,'VMS',action=lambda:self.open_hub('vms'))
            self.mouse_button(260,18,95,'Nav',action=self.open_navigation)
            self.mouse_button(450,18,85,'Menu',action=lambda:self.open_utility('menu'))
            section = 'money' if self.mode in ('money','bank','jobs','exchange') else 'vms' if self.mode in ('vms','outfit','engineering') else 'map' if self.mode in ('map','planet_profile') else None
            if section:
                x,w = {'money':(155,95),'vms':(365,75),'map':(260,95)}[section]
                d.rect(x,18,w,32,GOLD)
        modal = self.mode not in ('market','flight','cruise','hyperspace','dead','prison')
        self.mouse_button(545,18,85,'Back' if modal else 'Quit',action=self.mouse_back)
        row_y = 674
        if self.mode == 'menu':
            for i,(label,_) in enumerate(self.menu_actions()):
                x,y = 35+(i%2)*515,200+(i//2)*110
                self.mouse_button(x,y,490,label,action=lambda i=i:self.choose_menu_action(i))
                if i == self.menu_selected: d.rect(x-3,y-3,496,38,GOLD)
            self.mouse_button(35,674,1000,'Return to game',action=self.mouse_back)
        elif self.mode in ('market','outfit'):
            if self.mode == 'market':
                for i in range(len(GOODS)):
                    self.mouse_row(35,162+i*30,610,30,lambda i=i:setattr(self,'selected',i))
                labels = [('Buy',ord('b')),('Sell',ord('s'))]
            else:
                start = max(0,min(self.shop_selected-4,len(EQUIPMENT)-8))
                for i in range(start,min(start+8,len(EQUIPMENT))):
                    self.mouse_row(35,130+(i-start)*37,720,37,lambda i=i:setattr(self,'shop_selected',i))
                self.mouse_button(690,90,45,'Up',UP)
                self.mouse_button(740,90,60,'Down',DOWN)
                labels = [('Fit',ord('b')),('Return to VMS' if self.outfit_return == 'vms' else 'Return to market',ord('u'))]
            for i,(label,key) in enumerate(labels): self.mouse_button(35+i*220,row_y,210,label,key)
            if self.mode == 'market':
                self.mouse_button(350,638,300,'Negotiate payout N',ord('n'))
                self.mouse_button(665,638,300,'Buy with Crymto C',ord('c'))
        elif self.mode == 'vms':
            if self.vms_return == 'market':
                for i,(label,key) in enumerate([('Buy fuel F',ord('f')),('Sell fuel K',ord('k')),('Service R',ord('r')),('Outfit U',ord('u')),('Engineer 8',ord('8')),('Launch L',ord('l'))]):
                    self.mouse_button(35+i*172,575,164,label,key)
            else: self.mouse_button(35,575,300,'Engineering 8',ord('8'))
            self.mouse_button(35,674,1000,'Return',action=self.mouse_back)
        elif self.mode == 'money' and self.money_return == 'market':
            for i,(label,key) in enumerate([('Bank / storage',ord('1')),('Crymto exchange',ord('2')),('Redeem code',ord('3')),('Pay fines',ord('4'))]):
                self.mouse_button(35+(i%2)*515,380+(i//2)*100,490,label,key)
            self.mouse_button(35,535,490,'Station jobs / earn credits',ord('5'))
            self.mouse_button(550,535,490,'Trade log',ord('6'))
            self.mouse_button(35,674,1000,'Return to market',ord('9'))
        elif self.mode == 'money':
            self.mouse_button(35,535,490,'Trade log',ord('6'))
            self.mouse_button(35,674,1000,'Return',ord('9'))
        elif self.mode == 'trades':
            self.mouse_button(35,674,240,'Older',UP)
            self.mouse_button(290,674,240,'Newer',DOWN)
            self.mouse_button(800,674,240,'Return to Money',action=self.mouse_back)
        elif self.mode == 'redeem':
            self.mouse_button(35,315,160,'Paste',action=lambda:self.handle_clipboard('paste'))
            self.mouse_button(210,315,160,'Copy',action=lambda:self.handle_clipboard('copy'))
            self.mouse_button(385,315,160,'Select all',action=lambda:self.handle_clipboard('select_all'))
            self.mouse_button(35,674,490,'Redeem code',action=self.redeem_credit_code)
            self.mouse_button(550,674,490,'Return to Money',action=lambda:setattr(self,'mode','money'))
        elif self.mode == 'intro':
            if self.intro_page: self.mouse_button(35,674,300,'Previous',LEFT)
            self.mouse_button(735,674,300,'Start flying' if self.intro_page == len(self.INTRO)-1 else 'Next',13)
        elif self.mode == 'prison':
            self.mouse_button(35,674,490,'Work a shift W',ord('w'))
            self.mouse_button(550,674,490,'Bribe a guard B',ord('b'))
        elif self.mode == 'rename':
            self.mouse_button(35,315,160,'Paste',action=lambda:self.handle_clipboard('paste'))
            self.mouse_button(210,315,160,'Select all',action=lambda:self.handle_clipboard('select_all'))
            self.mouse_button(35,674,1000,'Save name',action=self.finish_rename)
        elif self.mode == 'notes':
            self.mouse_button(35,674,240,'Earlier',UP)
            self.mouse_button(290,674,240,'Later',DOWN)
            self.mouse_button(545,674,240,'Save notes',action=self.checkpoint)
            self.mouse_button(800,674,240,'Return',action=self.mouse_back)
        elif self.mode == 'trade_deal':
            self.mouse_button(35,674,490,'Accept clean-credit deal',ord('y'))
            self.mouse_button(550,674,490,'Decline',ord('n'))
        elif self.mode == 'exchange':
            for i,amount in enumerate([10,50,100,None]):
                self.mouse_button(35+i*255,594,240,'All' if amount is None else str(amount),action=lambda amount=amount:setattr(self,'exchange_amount',amount))
                if self.exchange_amount == amount: d.rect(35+i*255,594,240,28,GOLD)
            self.mouse_button(35,674,330,'Launder to credits',ord('l'))
            self.mouse_button(380,674,330,'Buy Crymto',ord('b'))
            self.mouse_button(725,674,330,'Return',ord('e'))
        elif self.mode == 'feedback':
            for i,(label,kind) in enumerate([('Bug report','bug'),('Suggestion','suggestion')]):
                self.mouse_button(35+i*240,165,225,label,action=lambda kind=kind:setattr(self,'feedback_type',kind))
                if self.feedback_type == kind: d.rect(35+i*240,165,225,28,GOLD)
            for i,(label,action) in enumerate([('Log report',self.save_feedback),('Return',self.mouse_back)]):
                self.mouse_button(35+i*520,674,505,label,action=action)
        elif self.mode == 'jobs':
            if self.p.dock_job is None:

                for i,label in enumerate(['Cargo handling','Inventory checks','Workshop assistant']):
                    self.mouse_row(40,150+i*75,1000,55,lambda i=i:self.start_job(i))
                    self.mouse_button(40+i*345,674,330,label,ord('1')+i)
            elif self.p.dock_job['step'] < 5:
                for i in range(3):
                    self.mouse_row(45,335+i*55,990,45,lambda i=i:self.answer_job(i))
                    self.mouse_button(40+i*345,674,330,'Answer '+str(i+1),ord('1')+i)
            self.mouse_button(790,570,250,'Return to Money',ord('j'))
        elif self.mode == 'bank':
            for i in range(len(GOODS)):
                self.mouse_row(35,162+i*30,600,30,lambda i=i:setattr(self,'selected',i))
            for i,amount in enumerate([50,100,1000,None]):
                self.mouse_button(720+(i%2)*145,270+(i//2)*38,135,'All' if amount is None else str(amount)+' cr',action=lambda amount=amount:self.choose_bank_amount(amount))
            self.mouse_button(720,346,280,'Set amount' if self.bank_custom is not None else 'Custom amount',action=self.set_custom_bank_amount if self.bank_custom is not None else lambda:setattr(self,'bank_custom',''))
            for i,(label,key) in enumerate([('Deposit',ord('d')),('Withdraw',ord('w')),('Rent bay',ord('r')),('Buy bay',ord('b'))]): self.mouse_button(35+i*255,638,240,label,key)
            for i,(label,key) in enumerate([('Store 1t',ord('s')),('Retrieve 1t',ord('t')),('Return',ord('9'))]): self.mouse_button(35+i*340,674,320,label,key)
        elif self.mode == 'planet_profile':
            for i,(label,key) in enumerate([('Previous',LEFT),('Next',RIGHT),('Return to map',ord('i'))]):
                self.mouse_button(35+i*345,674,330,label,key)
        elif self.mode == 'map':
            if not self.map_input: self.mouse_button(720,590,300,'Planet profile I',ord('i'))
            labels = [('Search',ord('/'),False),('Coords',ord('c'),False),('Lock',13,False),('Hold Jump',ord('h'),True),('Cruise',ord('t'),False),('Return',ord('g'),False)]
            if self.map_input:
                labels = [('Confirm',13,False),('Erase',8,False),('Cancel',27,False)]
            for i,(label,key,hold) in enumerate(labels): self.mouse_button(35+i*166,row_y,155,label,key,hold=hold)
        elif self.mode == 'launch_warning':
            self.mouse_button(35,630,300,'Choose destination G',ord('g'))
            for i,(label,key) in enumerate([('Buy fuel',ord('f')),('Request launch',ord('l')),('Cancel',27)]): self.mouse_button(50+i*300,row_y,280,label,key)
        elif self.mode == 'departure':
            self.mouse_button(50,row_y,300,'Launch when cleared',ord('l'))
            self.mouse_button(370,row_y,250,'Cancel',27)
        elif self.mode == 'hail':
            for i,ask in enumerate(HAIL_ASKS): self.mouse_button(35+i*200,600,190,f'Ask {ask}',ord('1')+i)
            if self.hail['counter']: self.mouse_button(635,600,200,f'Accept {self.hail["counter"]}',ord('4'))
            self.mouse_button(35,674,300,'Paid in cargo 5',ord('5'))
            self.mouse_button(735,674,300,'Close channel',action=self.mouse_back)
        elif self.mode == 'distress':
            for i in range(len(self.rescue['offers'])):
                self.mouse_row(35,169+i*38,1000,38,lambda i=i:self.rescue.update(selected=i))
            for i,(label,key) in enumerate([('Accept claim',ord('a')),('Negotiate',ord('n')),('Refuse',ord('r'))]): self.mouse_button(50+i*300,row_y,280,label,key)
        elif self.mode == 'engineering':
            for i,(label,key) in enumerate([('Train',ord('t')),('Repair self',ord('r')),('Help target',ord('h')),('Return',ord('8'))]): self.mouse_button(35+i*255,row_y,240,label,key)
        elif self.mode in ('help','updates'):
            if self.mode == 'help':
                for i,(title,_) in enumerate(self.help_sections()):
                    self.mouse_button(35+i*172,137,165,title,action=lambda i=i:setattr(self,'help_page',i))
                    if i == self.help_page: self.d.rect(35+i*172,137,165,28,GOLD)
            self.mouse_button(40,row_y,160,'Return',ord('1') if self.mode == 'help' else ord('2'))
        elif self.mode == 'cruise':
            for i,(label,key) in enumerate([('Cancel cruise',ord('t')),('Navigation',ord('g')),('Distress',ord('6'))]): self.mouse_button(50+i*300,row_y,280,label,key)
        elif self.mode == 'dead':
            self.mouse_button(50,row_y,350,'Recover starter ship',ord('r'))
            self.mouse_button(440,row_y,300,'New pilot / reset',ord('n'))
        if self.mode == 'flight':
            self.mouse_button(35,674,190,'Flight controls',action=lambda:setattr(self,'mouse_controls',not self.mouse_controls))
        if self.mode == 'flight' and self.mouse_controls:
            groups=[('Flight', [('Thrust W',ord('w'),True),('Brake S',ord('s'),True),('Fire Spc',32,True),('Left',LEFT,True),('Up',UP,True),('Right',RIGHT,True),('Roll Q',ord('q'),True),('Down',DOWN,True),('Roll E',ord('e'),True)]),
                ('Nav',[('Nav G',ord('g'),False),('Hold jump',ord('h'),True),('Cruise',ord('t'),False),('Station',ord('d'),False),('Planet',ord('p'),False),('Rocks',ord('a'),False),('Sun',ord('j'),False),('Scoop',ord('o'),False),('Guide ON' if self.course_assist else 'Guide Y',ord('y'),False)]),
                ('Combat',[('Fire',32,True),('View 4',ord('4'),False),('Laser',ord('v'),False),('Missile',ord('m'),False),('Mine',ord('b'),False),('Jammer',ord('z'),False),('Cloak',ord('k'),False),('Target',ord('5'),False)]),
                ('Safety',[('Surrender 7' if not self.p.deep_space and self.station_hostilities[self.p.system] and self.arrest_pending() and not self.surrendering else 'Radio 7',ord('7'),False),('Hail N',ord('n'),False),('Autodock',ord('c'),False),('Skills',ord('8'),False),('Distress',ord('6'),False),('Fine ON' if self.fine_control else 'Fine I',ord('i'),False)])]
            d.fill(30,105,350,270,(5,16,27));d.rect(30,105,350,270,GREEN)
            d.text(40,112,'FLIGHT CONTROLS',GOLD)
            for i,(title,_) in enumerate(groups):
                self.mouse_button(40+i*82,145,78,title,action=lambda i=i:setattr(self,'action_tab',i))
                if i == self.action_tab: d.rect(40+i*82,145,78,28,GOLD)
            for i,(label,key,hold) in enumerate(groups[self.action_tab][1]): self.mouse_button(40+(i%3)*110,190+(i//3)*45,105,label,key,hold=hold)
            d.text(40,341,'Hold movement / fire buttons.',(130,175,185))

        self.draw_action_bar()

    def mouse_fullscreen(self):
        self.d.is_fullscreen = not self.d.is_fullscreen
        self.d.fullscreen(self.d.win,0x1001 if self.d.is_fullscreen else 0)

    def mouse_back(self):
        """Navigate back independently of the Escape emergency close shortcut."""
        if self.mode == 'map' and self.map_input:
            self.map_input = None
            return
        if self.mode == 'distress':
            self.rescue = None
            self.mode = 'flight'
            self.message = 'Recovery offers declined. No salvage payment made.'
        else:
            returns = {'map':'map_return','help':'help_return','updates':'update_return',
                       'menu':'menu_return','notes':'notes_return','rename':'rename_return','intro':'intro_return','feedback':'feedback_return',
                       'money':'money_return','vms':'vms_return','outfit':'outfit_return',
                       'engineering':'engineering_return','launch_warning':'launch_return'}
            fixed = {'planet_profile':'map','redeem':'money','bank':'money','jobs':'money','trades':'money','hail':'flight',
                     'exchange':'money','trade_deal':'market','departure':'market'}
            if self.mode in returns: self.mode = getattr(self,returns[self.mode],'market')
            elif self.mode in fixed: self.mode = fixed[self.mode]
            else:
                self.request_exit()
                return
        self.keys.clear()
        self.release_mouse()
        self.checkpoint()

    def help_sections(self):
        return [
            ('Quick start',[
                ('First trade','B / S','Buy food on Halvora. Sell it at an industrial port such as Corvant.'),
                ('Mouse flight controls','Flight controls','Open the bottom-left panel. Flight, Nav, Combat and Safety group the actions.'),
                ('Plan a trip','G / ENTER','Choose a planet or coordinate, check fuel, then lock your course.'),
                ('Leaving the station','L','Request clearance, wait for approval, then launch. Read fuel warnings.'),
                ('Keep a reserve','F / R','Buy fuel and service the hull while docked. Cargo adds weight and inertia.'),
                ('Emergency close','ESC / Save/quit','Saves and closes from every screen. In space your saved ship continues unattended.')]),
            ('Flight',[
                ('Throttle and braking','HOLD W / S','W accelerates. S brakes, then reverses. Heavy cargo makes stopping slower.'),
                ('Fine steering','I + ARROWS','Arrows turn. I toggles 20% turning and Q/E roll. Safety tab has a mouse toggle.'),
                ('Rolling','HOLD Q / E','Roll the ship left or right to match the station entrance.'),
                ('Look behind','4','Toggle rear view. Your course stays the same; a rear laser must be fitted.'),
                ('Local navigation','D / P / A / J','Select station, planet, rocks or sun. Gold dots and arrows show the bearing.'),
                ('Pick up ore','O','Fit scoops. Get within 260m of a fragment at speed 50 or below.')]),
            ('Nav',[
                ('Navigation','G','Click a planet or empty point. Planet profiles show coordinates and services.'),
                ('Search and lock','/  C  ENTER','Search by name, enter coordinates, then lock. Mouse map clicks also lock.'),
                ('Fast travel','HOLD H','Keep holding for the 3-second countdown. Release early to cancel the jump.'),
                ('Economical travel','T','Cruise uses less fuel but takes time. T cancels at your current coordinates.'),
                ('Scanner targets','CLICK / 5','Select a ship. Pink markers track it; edge arrows show off-screen contacts.'),
                ('Approach guidance','Y','Toggle centring on a local target ahead. You set speed and roll. Arrows cancel; H/T for galaxy travel.')]),
            ('Combat',[
                ('Laser fire','HOLD SPACE','Fire the current view’s fitted laser. Rear view cannot use the front mount.'),
                ('Choose a laser','V','Cycle front pulse, beam, military or mining lasers you have bought.'),
                ('Missiles','M','Use one carried homing missile against the hostile contact. Replacements cost credits.'),
                ('Proximity mines','B','Drop a mine astern. It arms after 1.5 seconds; its blast can hurt you too.'),
                ('Electronic defence','Z / K','Bought jammer disrupts targeting. Bought cloak burns fuel; firing reveals you.'),
                ('Collision danger','KEEP CLEAR','Ships have solid collision hulls. A fast impact damages both ships.')]),
            ('Safety',[
                ('Docking radio','7','Request station clearance before entry. Wanted pilots may be refused.'),
                ('Manual docking','Q / E + LOW SPEED','Enter the rotating slot at 1–25. Centre within 14m / 6m; roll within +/-14 degrees.'),
                ('Automatic docking','C','A fitted docking computer requests clearance and guides the approach.'),
                ('Emergency rescue','6','Review rescue terms. Nearby stations claim 25%; distant salvagers negotiate.'),
                ('Field engineering','8','Repair your ship or a nearby selected disabled ship. Training improves odds.'),
                ('Repair cooldown','30m, 60m, 120m…','Failed repairs impose real-time waits. Rescue is still available during a cooldown.')]),
            ('Station',[
                ('Market','UP/DOWN  B / S','Click goods or use arrows. Buy and sell prices differ; station stock is finite.'),
                ('Outfitting','U','Buy modules and ammunition. Availability depends on local technology.'),
                ('Fuel and service','F / R','Fuel is a separate purchase. Service repairs damage and resets maintenance wear.'),
                ('Bank and cargo bays','9','Deposit money, store cargo, rent 40t or buy 100t of station capacity.'),
                ('Earn fuel money','J station jobs','Free dockside shifts pay 15-40 credits. Workshop practice earns engineering experience.'),
                ('Updates and display','2 / 3','Check version/update instructions, or toggle fullscreen. No function keys needed.')])]

    def draw_help(self):
        d=self.d
        sections=self.help_sections()
        self.help_page %= len(sections)
        title,cards=sections[self.help_page]
        d.text(35,78,'PILOT HANDBOOK / '+title.upper(),GOLD)
        d.text(35,105,'Click a tab. LEFT / RIGHT changes page. 1 or Return goes back.')
        for i,(heading,keys,description) in enumerate(cards):
            x,y=35+(i%2)*530,180+(i//2)*150
            d.fill(x,y,510,130,(7,23,33));d.rect(x,y,510,130,(35,90,105))
            d.text(x+15,y+10,heading,GREEN)
            d.text(x+15,y+38,keys,GOLD)
            for line_index,line in enumerate(textwrap.wrap(description,43)[:3]): d.text(x+15,y+67+line_index*20,line,(160,200,205))

    def draw(self):
        d,p = self.d,self.p
        d.color(d.r,4,9,18,255)
        d.clear(d.r)
        d.text(28,20,'STAR TRADER',GREEN)
        location = 'In transit' if self.mode == 'hyperspace' else 'Deep space' if p.deep_space or self.mode == 'cruise' else SYSTEMS[p.system][0]
        economy = '' if p.deep_space or self.mode in ('cruise','hyperspace') else f' / {SYSTEMS[p.system][1]} / Tech {TECH[p.system]}'
        d.text(640,5,location+economy,GOLD)
        d.text(640,29,f'CR {p.credits:.0f}  CYM {p.crymto}  KILLS {p.kills}')
        d.line(25,52,W-25,52)
        if self.mode == 'vms':
            self.draw_vms()
        elif self.mode == 'menu':
            self.draw_menu()
        elif self.mode == 'money':
            self.draw_money()
        elif self.mode == 'notes':
            self.draw_notepad()
        elif self.mode == 'intro':
            self.draw_intro()
        elif self.mode == 'trades':
            self.draw_trades()
        elif self.mode == 'prison':
            self.draw_prison()
        elif self.mode == 'rename':
            d.text(35,85,'MENU / COMMANDER NAME',GOLD)
            d.text(45,180,'Type a name (up to 24 characters), then press ENTER or click Save name.')
            d.rect(35,245,1030,60,GREEN)
            if self.text_selection_all and self.text_selection_mode == 'rename': d.fill(40,250,max(20,len(p.name)*11+20),42,(20,65,70))
            d.text(45,265,p.name+'_',GOLD)
            remote = getattr(self,'remote_save',None)
            if remote and remote.player_name: d.text(45,360,f'Shown on your status panel. Other pilots online see your account name: {remote.player_name}.')
            d.text(45,415,'ESC saves and closes.')
        elif self.mode == 'redeem':
            d.text(35,85,'MONEY / REDEEM CREDIT CODE',GOLD)
            d.text(45,180,'Type a code or paste with CTRL+V, then press ENTER to redeem.')
            d.rect(35,245,1030,60,GREEN)
            if self.text_selection_all and self.text_selection_mode == 'redeem': d.fill(40,250,max(20,len(self.credit_code_text)*11+20),42,(20,65,70))
            d.text(45,265,self.credit_code_text+'_',GOLD)
            d.text(45,360,'Codes can only be redeemed once by this pilot.')
            d.text(45,415,'Click Return to Money. ESC saves and closes.')
        elif self.mode == 'trade_deal':
            good = self.deal_good
            dirty = quote(p.system,good,False)
            clean = dirty*85//100
            d.text(35,85,'NEGOTIATE CLEAN PAYMENT',GOLD)
            d.text(45,180,f'Buyer offers {clean} clean credits for 1 tonne of {GOODS[good]}.')
            d.text(45,240,f'Normal sale pays {dirty} Crymto. This deal takes a 15% discount.')
            d.text(45,300,'Y accepts and sells one tonne. N declines without selling.')
            d.text(45,360,'Crymto is retained after ship destruction; shipboard credits are lost.')
        elif self.mode == 'exchange':
            self.draw_exchange()
        elif self.mode == 'feedback':
            self.draw_feedback()
        elif self.mode == 'jobs':
            self.draw_jobs()
        elif self.mode == 'engineering':
            self.draw_engineering()
        elif self.mode == 'departure':
            d.text(80,150,'STATION TRAFFIC CONTROL',GOLD)
            d.text(80,220,f'Requesting departure: {self.departure_remaining:.1f}s' if self.departure_remaining else 'Departure clearance GRANTED.')
            d.text(80,290,'L launches when cleared. Click Cancel to stay docked.')
            d.text(80,345,f'Next flight breakdown risk: {self.breakdown_risk(True)*100:.1f}%. Station R services your ship.')
        elif self.mode == 'launch_warning':
            self.draw_launch_warning()
        elif self.mode == 'distress':
            self.draw_distress()
        elif self.mode == 'hail':
            self.draw_hail()
        elif self.mode == 'hyperspace':
            self.draw_hyperspace()
        elif self.mode == 'help':
            self.draw_help()
        elif self.mode == 'updates':
            latest = self.updates.latest
            lines = ['STAR TRADER / UPDATES',f'Installed version: {VERSION}',
                'New release: '+latest if latest else ('No newer release detected.' if self.updates.checked else 'Offline, disabled, or check still pending.'),
                '', 'New releases install automatically when Star Trader starts.',
                'Saved games are preserved. To update by hand, in a terminal:',
                '    python3 update.py', '',
                'Or run the installed updater:',
                '    python3 "${XDG_DATA_HOME:-$HOME/.local/share}/star-trader/update.py"',
                '', 'The updater requires a clean main branch and stops on local edits.',
                'It fetches the official repository, then reruns the installer.',
                'Release notes: github.com/womb4t/star-trader/releases',
                '', 'If an automatic update fails, details are in update.log.',
                'Use --no-update-check to disable network checks.', '', 'BACKSPACE returns. ESC saves and closes the game.']
            for i,line in enumerate(lines): d.text(30,80+i*31,line,GOLD if i==2 else GREEN)
        elif self.mode in ('market','outfit'):
            if self.mode == 'market':
                d.text(35,85,'ORBITAL EXCHANGE / '+SYSTEMS[p.system][1].upper())
                for x,label in [(35,'COMMODITY'),(270,'BUY'),(340,'SELL'),(415,'STOCK'),(495,'HOLD'),(565,'BEST IN RANGE')]:
                    d.text(x,130,label)
                for i,g in enumerate(GOODS):
                    color = GOLD if i == self.selected else GREEN
                    d.text(35,170+i*30,('> ' if i == self.selected else '  ')+g+(' *' if i in ILLEGAL else ''),color)
                    for x,value in [(270,quote(p.system,i)),(340,quote(p.system,i,False)),(415,p.stock[p.system][i]),(495,p.cargo[i])]:
                        d.text(x,170+i*30,str(value),color)
                    best = self.best_sale_in_range(i)
                    if best:
                        price,system = best
                        d.text(565,170+i*30,f'{price:>3} {SYSTEMS[system][0][:7]}',(120,220,140) if price > quote(p.system,i) else (120,140,150))
                    else: d.text(565,170+i*30,'-',(120,140,150))
                d.text(35,470,'BUY = you pay. * Contraband sales pay Crymto (CYM).')
                d.text(35,500,'BEST IN RANGE: top sale price at systems your fuel can reach.',(135,175,185))
            else:
                d.text(35,85,f'SHIP OUTFITTING / LOCAL TECH {TECH[p.system]} / U market')
                start = max(0,min(self.shop_selected-4,len(EQUIPMENT)-8))
                for i in range(start,min(start+8,len(EQUIPMENT))):
                    key,label,cost,tech,desc = EQUIPMENT[i]
                    state = 'FITTED' if key in p.equipment else f'NEEDS TECH {tech}' if tech>TECH[p.system] else 'AVAILABLE'
                    if key in ('missile','mine'): state += f' / {p.missiles if key == "missile" else p.mines}/4 ABOARD'
                    d.text(35,135+(i-start)*37,f'{">" if i==self.shop_selected else " "} {label:<23} {cost:>4} cr  {state}',GOLD if i==self.shop_selected else GREEN)
                d.text(35,455,EQUIPMENT[self.shop_selected][4],GOLD)
                item,label,cost,required,_ = EQUIPMENT[self.shop_selected]
                d.text(35,490,f'Selected: {label} / needs tech {required} / local tech {TECH[p.system]}',GOLD if required <= TECH[p.system] else RED)
                d.text(35,520,'UP/DOWN select; B or ENTER buys. Mines and missiles: maximum 4 each.')
            wanted = self.wanted_level()
            for i,t in enumerate(['COMMANDER STATUS',f'Cmdr  {self.commander_name()[:16]}',f'Rank  {p.rank}',f'Wanted {"*"*wanted}{"-"*(5-wanted)} {wanted}/5',f'Cargo {sum(p.cargo)}/{p.capacity} t',f'Fuel  {p.fuel:.2f}/7',f'Hull  {p.hull:.0f}%',f'Refill {p.fuel_cost()} cr',f'Service {p.service_cost()} cr',f'Mines {p.mines}/4',f'Fine {p.fine} cr',f'Wear {p.maintenance:.0f}%',f'Eng. {p.engineering_level}/5']): d.text(790,130+i*35,t,RED if i == 3 and wanted else GREEN)
            d.text(35,550,'Ship fuel, service, fitting and engineering: open VMS above.')
            d.text(35,590,'9 Money / station jobs   X VMS   G Nav')
        elif self.mode == 'planet_profile':
            self.draw_planet_profile()
        elif self.mode == 'map':
            self.draw_map()
        elif self.mode == 'cruise':
            trip = self.cruise
            remaining = max(0,trip['duration']-trip['elapsed'])
            d.text(320,200,'INTERSTELLAR CRUISE',GREEN)
            d.text(250,255,'Destination: '+trip['destination']['name'])
            d.text(250,300,f'ETA {int(remaining//60)}m {int(remaining%60)}s    FUEL {p.fuel:.2f}/7')
            d.text(250,345,f'Coordinates {p.position[0]:.3f}, {p.position[1]:.3f}')
            d.rect(250,405,600,25)
            progress = min(1,trip['elapsed']/trip['duration'])
            for x in range(int(594*progress)): d.line(253+x,409,253+x,426)
            d.text(250,475,'T cancels at current coordinates. G opens map.')
        elif self.mode == 'bank':
            self.draw_bank()
        elif self.mode == 'dead':
            d.text(350,250,'SHIP DESTROYED',RED)
            d.text(80,300,'R recovers a starter ship; costs up to 100 bank credits. Shipboard assets are lost.')
            d.text(80,340,'Bank and station cargo survive. N starts a new pilot and resets ALL assets.')
            d.text(80,380,'ESC quits. This destroyed state is saved; quitting cannot restore the old ship.')
        else:
            self.draw_flight()
        self.draw_alert()
        self.draw_mouse_ui()
        d.line(25,710,W-25,710)
        notice = 'Update '+self.updates.latest+' available - 2' if self.updates.latest else self.message
        d.text(28,725,notice[:94],GOLD)
        d.present(d.r)

    def draw_flight(self):
        d,p = self.d,self.p
        # Clip the 3D view so near objects do not overwrite cockpit instruments.
        clip = bind(d.sdl,'SDL_RenderSetClipRect',C.c_int,[C.c_void_p,C.c_void_p])
        viewport = (C.c_int*4)(25,65,W-50,490)
        clip(d.r,viewport)
        for star in self.stars:
            point = self.project(star)
            if point:
                x,y,_ = point
                d.line(x,y,x+1,y+1,(100,135,150))
        self.object(self.sun,'sun')
        if not p.deep_space:
            self.object(self.planet,'planet')
            self.object(self.station,'station')
        for mine in self.mine_objects: self.object(mine,'mine')
        for rock in self.asteroids: self.object(rock,'asteroid')
        for fragment in self.fragments: self.object(fragment,'ore')
        for player in self.other_players.values():
            self.object(player['object'],'player')
            projected = self.project(player['object'])
            if projected: d.text(max(35,min(W-240,projected[0]-60)),max(100,min(510,projected[1]-35)),player['name'],(140,185,255))
        if self.enemy: self.object(self.enemy,self.enemy_kind)
        if self.disabled_ship: self.object(self.disabled_ship['object'],'disabled')
        for m in self.missiles_in_flight:
            point = self.project(m['position'])
            if point:
                x,y,_ = point
                d.line(x-6,y,x+6,y,(255,240,160)); d.line(x,y-6,x,y+6,(255,240,160))
                d.line(x,y,x+(W/2-x)*.15,y+(560-y)*.15,GOLD)
        for e in self.explosions:
            point = self.project(e['position'])
            if point:
                x,y,scale = point
                grow = (1-e['remaining']/.8)*e['size']
                radius = max(6,(30+170*grow)*max(scale,.05))
                color = (255,220,120) if e['remaining'] > .4 else (230,110,60)
                for i in range(12):
                    a = i*math.pi/6
                    d.line(x+math.cos(a)*radius*.3,y+math.sin(a)*radius*.3,x+math.cos(a)*radius,y+math.sin(a)*radius,color)
        if self.laser_flash:
            color = GOLD if p.laser == 'mining' and not self.rear_view else RED
            d.line(160,550,550,330,color)
            d.line(940,550,550,330,color)
        if self.enemy_shot:
            shot = self.enemy_shot
            color = GOLD if shot['kind'] == 'station' else RED if shot['kind'] == 'pirate' else (120,170,255)
            origin = self.project(shot['position'])
            if origin:
                x,y,_ = origin
                d.line(x,y,550,330,color)
                d.line(x+2,y,552,330,color)
                d.rect(x-6,y-6,12,12,color)
            else:
                self.draw_marker(shot['position'],'INCOMING FIRE',color)
            d.text(435,465,'INCOMING '+shot['kind'].upper()+' FIRE',color)
        d.line(530,330,542,330); d.line(558,330,570,330)
        d.line(550,310,550,322); d.line(550,338,550,350)
        clip(d.r,None)
        target,label = self.active_navigation()
        if target is not None: self.draw_marker(target,label,GOLD)
        if self.ship_target is not self.enemy and (not self.disabled_ship or self.ship_target is not self.disabled_ship['object']) and not self.player_label(self.ship_target): self.ship_target = None
        if self.ship_target is not None: self.draw_marker(self.ship_target,self.player_label(self.ship_target) or ('DISABLED SHIP' if self.disabled_ship and self.ship_target is self.disabled_ship['object'] else 'TARGET '+self.enemy_kind.upper()),(255,100,180))
        self.draw_scanner()
        self.draw_heat_instrument()
        d.text(35,73,'REAR VIEW' if self.rear_view else 'FORWARD VIEW',GOLD)
        if self.faults: d.text(35,127,'DAMAGE: '+'  '.join(FAULT_LABELS[name] for name in sorted(self.faults)),RED)
        status = self.target_status()
        if status:
            name,shield,hull = status
            d.text(35,100,f'TARGET {name}  SHIELD {shield:.0f}%  HULL {hull:.0f}%',(255,100,180))
        if getattr(self,'presence',None): d.text(360,73,f'PLAYERS NEARBY {len(self.other_players)} / PvP disabled',(140,185,255))
        if self.flash: d.rect(26,65,W-52,490,RED)
        obj,label = self.active_navigation()
        if obj is None: obj = [0.,0.,0.]
        c,s = math.cos(self.roll),math.sin(self.roll)
        x,y,z = obj[:3]
        if self.nav == 'course' and p.waypoint and galactic_distance(p.position,p.waypoint['position']) > .001:
            w = p.waypoint
            d.text(35,563,f'GALACTIC COURSE {w["name"]}: ({w["position"][0]:.2f}, {w["position"][1]:.2f})  {galactic_distance(p.position,w["position"]):.2f} LY')
        else:
            d.text(35,563,f'BEACON {label}: X {x*c+y*s:+.0f} Y {-x*s+y*c:+.0f} Z {z:+.0f} RANGE {math.sqrt(x*x+y*y+z*z):.0f}m')
        if self.heat >= 70:
            d.text(35,520,'THERMAL LIMIT 90% / SHIELDS DRAINING - TURN AWAY',RED if self.heat >= 90 else GOLD)
        d.text(35,594,f'SPEED {self.speed:.0f}  FUEL {p.fuel:.2f}  {("REAR PULSE" if "rear" in p.equipment else "REAR UNARMED") if self.rear_view else p.laser.upper()} LASER  MISSILES {p.missiles}')
        d.text(35,625,f'SHIELD {self.shield:.0f}%  HULL {p.hull:.0f}%  HOLD {sum(p.cargo)}/{p.capacity}t')
        error = math.degrees(self.slot_error())
        d.text(650,598,('GUIDANCE Y  ' if self.course_assist else '')+('FINE I' if self.fine_control else ''),GOLD)
        d.text(650,625,'DRIVE DISABLED' if self.broken_down else 'AUTODOCK' if self.autodock else f'SLOT {error:+.0f}/14deg '+('CLEAR' if self.dock_clearance else '7 radio'),GOLD)
        status = 'CLOAKED' if self.cloaked else 'JAMMING' if self.jamming else ''
        d.text(35,650,f'MINES {p.mines}  {status}  6 distress  /  4 rear view'+('  /  PATROL ZONE' if self.in_patrol_zone() else ''),GOLD)
        if p.fuel < 1.0:
            d.text(810,650,'LOW FUEL',RED)
        if p.waypoint:
            w = p.waypoint
            delta = [b-a for a,b in zip(p.position,w['position'])]
            d.text(245,681,f'COURSE {w["name"][:18]}  {math.hypot(*delta):.2f} LY / T cruise',GOLD)
        elif p.fuel < 1.0:
            d.text(245,681,'LOW FUEL - buy fuel / skim the sun. Press 6 for distress.',RED)
        if self.jump_charge:
            count = max(1,math.ceil(3-self.jump_charge['held']))
            d.fill(240,265,600,90,(4,9,18))
            d.text(335,280,f'HYPERSPACE IN {count}...',GOLD)
            d.text(300,320,'Keep holding H. Release to cancel.',GREEN)
        elif self.arrival:
            d.fill(225,110,610,82,(4,9,18))
            d.rect(225,110,610,82,GREEN)
            d.text(250,125,'ARRIVED AT '+self.arrival['name'].upper(),GOLD)
            d.text(250,157,f'Galactic coordinates {p.position[0]:.2f}, {p.position[1]:.2f}',GREEN)

    def object(self,obj,kind):
        projected = self.project(obj)
        if projected is None: return
        sx,sy,scale = projected
        if sx < -800 or sx > W+800 or sy < -800 or sy > H+800: return
        color = GREEN
        angle = self.roll if self.rear_view else -self.roll
        if kind in ('pirate','police','disabled','player'):
            points = [(-65,10),(-20,-15),(0,-5),(20,-15),(65,10),(0,28)]
            edges = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,0),(0,4),(2,5)]
            color = GOLD if kind == 'disabled' else RED if kind == 'pirate' else (120,170,255)
        elif kind == 'station':
            angle += -self.station_angle if self.rear_view else self.station_angle
            points = [(math.cos(i*math.pi/4)*100,math.sin(i*math.pi/4)*100) for i in range(8)]
            points += [(-35,-12),(35,-12),(35,12),(-35,12)]
            edges = [(i,(i+1)%8) for i in range(8)] + [(8,9),(9,10),(10,11),(11,8)]
        else:
            count = 24 if kind in ('sun','planet') else 7 if kind == 'asteroid' else 6 if kind == 'mine' else 4
            radius = 220 if kind == 'sun' else self.planet_radius if kind == 'planet' else 42 if kind == 'asteroid' else 9 if kind == 'mine' else 7
            points = [(math.cos(i*2*math.pi/count)*radius*(1 if kind != 'asteroid' else 0.85+0.15*(i%3)), math.sin(i*2*math.pi/count)*radius) for i in range(count)]
            edges = [(i,(i+1)%count) for i in range(count)]
            color = RED if kind == 'mine' else (90,150,220) if kind == 'planet' else GOLD if kind in ('sun','asteroid') else (150,190,255)
        c,s = math.cos(angle),math.sin(angle)
        points = [(sx+(x*c-y*s)*scale,sy+(x*s+y*c)*scale) for x,y in points]
        for a,b in edges: self.d.line(*points[a],*points[b],color)
        if abs(obj[2]) > 150:
            self.d.text(max(30,min(W-220,sx-65)),max(75,min(525,sy+110*scale)),kind.upper(),color)


def self_test():
    p = Pilot()
    initial = p.credits
    p.trade(0,True); p.trade(0,False)
    assert p.credits < initial and p.cargo[0] == 0
    p.cargo = [20]+[0]*(len(GOODS)-1); before = p.credits
    p.trade(0,True)
    assert p.credits == before and sum(p.cargo) == 20
    assert quote(0,0) < quote(1,0,False) and quote(1,5) < quote(0,5,False)
    assert distance(0,0) == 0 and 0 < distance(0,1) < 7
    print('Economy spread, cargo capacity and navigation checks passed.')


def grant_testing_credits(amount):
    """Explicit offline testing tool; caller must hold the game's save lock."""
    if type(amount) is not int or not 1 <= amount <= 1000000000:
        raise ValueError('Testing grant must be 1 to 1,000,000,000 credits.')
    raw = SAVE.read_bytes()
    data = json.loads(raw)
    pilot = Pilot()
    for key in vars(pilot):
        if key in data: setattr(pilot,key,data[key])
    pilot.validate()
    backup = SAVE.with_name('save.before-test-grant-'+uuid.uuid4().hex[:12]+'.json')
    backup.write_bytes(raw)
    data['credits'] = pilot.credits+amount
    temp = SAVE.with_suffix('.grant.tmp')
    temp.write_text(json.dumps(data,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(SAVE)
    print(f'Added {amount:,} testing credits. Wallet: {data["credits"]:,.2f}. Backup: {backup}')


def notify(text):
    if shutil.which('notify-send'): subprocess.run(['notify-send','Star Trader',text],check=False)
    elif sys.platform == 'darwin':
        subprocess.run(['osascript','-e','on run argv','-e','display notification (item 1 of argv) with title "Star Trader"','-e','end run',text],check=False)


def auto_update():
    """Install a newer published release before the game opens, then restart into it."""
    here = Path(__file__).resolve().parent
    # Only installed copies update themselves; source checkouts are left to Git.
    if not (here/'install-info.json').is_file() or not (here/'update.py').is_file(): return
    if os.environ.get('STAR_TRADER_NO_UPDATE_CHECK') == '1' or '--no-update-check' in sys.argv: return
    latest = UpdateNotice.fetch_latest()
    if not UpdateNotice.newer(latest): return
    notify(f'Installing update {latest}. Your saved game is preserved.')
    try:
        result = subprocess.run([sys.executable,str(here/'update.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
        ok = result.returncode == 0
        log = result.stdout+result.stderr
    except (OSError,subprocess.TimeoutExpired) as error:
        ok,log = False,str(error)
    try:
        SAVE.parent.mkdir(parents=True,exist_ok=True)
        (SAVE.parent/'update.log').write_text(f'{time.ctime()} update to {latest}\n{log}',encoding='utf-8')
    except OSError: pass
    if not ok:
        notify(f'Update {latest} could not be installed; starting {VERSION}. Details: {SAVE.parent/"update.log"}')
        return
    notify(f'Updated to {latest}.')
    os.execv(sys.executable,[sys.executable,str(here/'star_trader.py'),*sys.argv[1:],'--no-update-check'])


def main():
    global SAVE
    if '--version' in sys.argv:
        print(VERSION)
        return
    if '--self-test' in sys.argv:
        self_test()
        return
    parser = argparse.ArgumentParser(description='Star Trader — offline game with optional private progress server')
    parser.add_argument('--offline',action='store_true',help='Start offline directly without the mode chooser')
    parser.add_argument('--server')
    parser.add_argument('--token-file',type=Path)
    parser.add_argument('--allow-lan',action='store_true')
    parser.add_argument('--import-local-save',action='store_true')
    parser.add_argument('--restore-server-save',action='store_true')
    parser.add_argument('--offline-if-unavailable',action='store_true')
    options, _ = parser.parse_known_args()
    display = None
    scratch = None
    instance_file = None
    remote = None
    game = None
    presence = None
    feedback = None
    try:
        offline_save = SAVE
        if options.offline and options.server: raise ValueError('Choose --offline or --server')
        if options.server and not options.token_file: raise ValueError('--server requires --token-file')
        if not options.server and (options.token_file or options.import_local_save or options.restore_server_save):
            raise ValueError('Server options require --server')
        testing = '--smoke-test' in sys.argv or '--grant-test-credits' in sys.argv
        if not testing: auto_update()
        if testing and options.server: raise ValueError('Testing CLI tools require offline mode')
        if '--smoke-test' in sys.argv:
            scratch = tempfile.TemporaryDirectory(prefix='star-trader-smoke-')
            SAVE = Path(scratch.name)/'save.json'
        if not testing and not options.offline:
            from startup import StartScreen,load_connection,migrate_online_launcher
            migrate_online_launcher(Path.home()/'.local/bin/star-trader-online')
            config = load_connection()
            if options.server:
                config.update(server=options.server,token_file=str(options.token_file),
                              allow_lan=options.allow_lan,import_local_save=options.import_local_save)
            display = Display()
            screen = StartScreen(display,config)
            if options.server: screen.selected = 0
            try:
                while True:
                    choice = screen.choose()
                    if choice == 'quit': return
                    SAVE = offline_save
                    remote = None
                    try:
                        if choice == 'online':
                            from save_sync import RemoteSave,pick_server
                            config = screen.config
                            screen.error = 'Connecting to your progress server...'
                            screen.draw()
                            # Fallback addresses (for example the host's home-network name) cover a public link that is down.
                            server = pick_server([config['server']]+config.get('fallback_servers',[]),config['allow_lan'])
                            remote = RemoteSave(server,config['token_file'],offline_save.parent,config['allow_lan'])
                            SAVE = remote.save_path
                            screen.error = 'Connecting to your progress server...'
                            screen.draw()
                        SAVE.parent.mkdir(parents=True,exist_ok=True)
                        instance_file = SAVE.with_suffix('.lock').open('a')
                        fcntl.flock(instance_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        if remote:
                            remote.prepare(offline_save if config['import_local_save'] else None,
                                           options.restore_server_save,options.offline_if_unavailable)
                        break
                    except (OSError,RuntimeError,ValueError) as error:
                        if instance_file: instance_file.close(); instance_file = None
                        remote = None
                        screen.error = str(error) if not isinstance(error,OSError) else 'Could not connect or open save. Check settings, retry, or choose Offline play.'
            finally: screen.close()
        else:
            SAVE.parent.mkdir(parents=True,exist_ok=True)
            instance_file = SAVE.with_suffix('.lock').open('a')
            try: fcntl.flock(instance_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise RuntimeError('Star Trader is already running for this save. Close it before starting another copy.')
        if '--grant-test-credits' in sys.argv:
            index = sys.argv.index('--grant-test-credits')
            if index+1 >= len(sys.argv): raise ValueError('Specify the testing credit amount.')
            grant_testing_credits(int(sys.argv[index+1]))
            return
        if display is None: display = Display()
        game = Game(display)
        if remote:
            game.remote_save = remote
            from presence import PresenceClient
            from save_sync import FeedbackUploader
            presence = PresenceClient(remote)
            feedback = FeedbackUploader(remote,FEEDBACK_OUTBOX)
            feedback.start()
            game.presence = presence
            remote.start()
            game.checkpoint()
        last = time.monotonic()
        frames = 0
        while game.running:
            now = time.monotonic()
            dt,last = min(0.05,now-last),now
            for kind,key in display.events():
                if kind == 'quit': game.request_exit()
                elif kind == 'blur':
                    game.keys.clear()
                    game.release_mouse()
                elif kind == 'text': game.text_input(key)
                elif kind == 'clipboard': game.handle_clipboard(key)
                elif kind == 'click': game.click(*key)
                elif kind == 'mouse_up': game.release_mouse()
                elif kind == 'down':
                    game.keys.add(key)
                    game.key(key)
                else: game.keys.discard(key)
            game.update(dt)
            game.draw()
            frames += 1
            if '--smoke-test' in sys.argv and frames >= 5: break
            time.sleep(max(0,1/60-(time.monotonic()-now)))
    except (OSError,RuntimeError,ValueError) as e:
        print(f'Unable to start: {e}',file=sys.stderr)
        sys.exit(1)
    finally:
        if remote and game: game.checkpoint()
        if display: display.quit()
        if presence: presence.close()
        if feedback: feedback.close()
        if remote:
            remote.close()
            print(remote.status)
        if instance_file: instance_file.close()
        if scratch: scratch.cleanup()


if __name__ == '__main__':
    main()
