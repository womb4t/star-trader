#!/usr/bin/env python3
"""STAR TRADER — an original Elite-inspired game. Python 3 + system SDL2/SDL2_ttf.
Run: python3 star_trader.py   Test: python3 star_trader.py --self-test
"""
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
import uuid
import tempfile
import fcntl
import textwrap

VERSION = '0.2.7'
DOCK_ROLL_TOLERANCE = math.radians(14)
CRUISE_SECONDS_PER_LY = 45
W, H = 1100, 760
GOODS = ['Food', 'Textiles', 'Ore', 'Machinery', 'Medicine', 'Computers', 'Narcotics', 'Unlicensed Arms']
BASE = [8, 15, 24, 48, 65, 90, 150, 110]
ILLEGAL = (6, 7)
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
UP, DOWN, LEFT, RIGHT = 1073741906, 1073741905, 1073741904, 1073741903
GREEN, GOLD, RED = (68, 227, 182), (255, 206, 113), (255, 112, 100)
SYSTEMS = [
    ('Lave', 'Agricultural', 0.15, 0.40), ('Zaonce', 'Industrial', 0.40, 0.20),
    ('Diso', 'Agricultural', 0.34, 0.64), ('Leesti', 'Industrial', 0.60, 0.46),
    ('Riedquat', 'Frontier', 0.76, 0.76), ('Tionisla', 'Industrial', 0.72, 0.16),
    ('Orerve', 'Frontier', 0.14, 0.84), ('Reorte', 'Agricultural', 0.90, 0.43)]
PROFILES = [
    ('Dictatorship', 4.2, 6400), ('Corporate state', 5.8, 9100),
    ('Democracy', 3.1, 5800), ('Confederacy', 4.9, 7600),
    ('Anarchy', 1.2, 11500), ('Democracy', 6.4, 12800),
    ('Feudal', 0.8, 4200), ('Communist', 3.6, 8100)]

SAVE = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'star-trader' / 'save.json'


def price(system, good):
    rng = random.Random(system * 97 + good * 13)
    economy = SYSTEMS[system][1]
    factor = (0.65 if good < 3 else 1.25) if economy == 'Agricultural' else (1.3 if good < 3 else 0.7)
    if economy == 'Frontier':
        factor = 1.0
    return round(BASE[good] * factor * rng.uniform(0.9, 1.1))


def distance(a, b):
    return math.hypot(SYSTEMS[a][2] - SYSTEMS[b][2], SYSTEMS[a][3] - SYSTEMS[b][3]) * 10


def quote(system, good, buy=True):
    """Player buy price includes a spread; selling immediately costs money."""
    base = price(system, good)
    return base + max(1, math.ceil(base * 0.08)) if buy else max(1, base - math.ceil(base * 0.08))


def initial_stock():
    return [[random.Random(i * 113 + j).randint(12, 35) for j in range(len(GOODS))] for i in range(8)]


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
        self.cargo = [0] * len(GOODS)
        self.system = 0
        self.fuel = 7.0
        self.hull = 100
        self.kills = 0
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
        self.bank_balance = 0
        self.storage = [dict(owned=False,rented_until=0.,cargo=[0]*len(GOODS)) for _ in SYSTEMS]

    @property
    def capacity(self):
        return 35 if 'cargo' in self.equipment else 20

    def trade(self, good, buy):
        value = quote(self.system, good, buy)
        stock = self.stock[self.system]
        if buy:
            if stock[good] <= 0: return 'Station has no stock.'
            if sum(self.cargo) >= self.capacity: return 'Cargo hold full.'
            if self.credits < value: return 'Insufficient credits.'
            self.credits -= value
            self.cargo[good] += 1
            stock[good] -= 1
        else:
            if self.cargo[good] <= 0: return 'None aboard to sell.'
            self.credits += value
            self.cargo[good] -= 1
            stock[good] += 1
        return f'{"Bought" if buy else "Sold"} 1 t {GOODS[good]} for {value} cr.'

    def buy_equipment(self, index):
        key, label, cost, tech, _ = EQUIPMENT[index]
        if TECH[self.system] < tech: return f'Requires technology level {tech}.'
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
        return math.ceil(round(7 - self.fuel, 3) * 3)

    def refuel(self):
        cost = self.fuel_cost()
        if self.credits < cost: return f'Refill costs {cost} cr. Sell cargo first.'
        self.credits -= cost
        self.fuel = 7.0
        return f'Fuel purchased: {cost} cr. Tank full.'

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
            if len(candidate.cargo) == 6: candidate.cargo += [0] * (len(GOODS)-6)
            if isinstance(candidate.stock,list):
                for i,row in enumerate(candidate.stock):
                    if isinstance(row,list) and len(row) == 6:
                        row.extend(initial_stock()[i][6:])
            candidate.validate()
            self.__dict__.update(vars(candidate))
            if 'commander_id' not in data:
                try: self.save()
                except OSError: pass
            return True
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def validate(self):
        def integer(n): return type(n) is int and n >= 0
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


def bind(lib, name, restype, args):
    f = getattr(lib, name)
    f.restype, f.argtypes = restype, args
    return f


class Display:
    def __init__(self):
        self.sdl = C.CDLL(ctypes.util.find_library('SDL2') or 'libSDL2.so')
        self.ttf = C.CDLL(ctypes.util.find_library('SDL2_ttf') or 'libSDL2_ttf.so')
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
        self.logical_point = bind(self.sdl,'SDL_RenderWindowToLogical',None,[ptr,i,i,C.POINTER(C.c_float),C.POINTER(C.c_float)])
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
        self.fullscreen = bind(self.sdl, 'SDL_SetWindowFullscreen', i, [ptr, C.c_uint32])
        self.is_fullscreen = False
        if not self.win or not self.r:
            raise RuntimeError('Could not create game window.')
        fonts = ['/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf', '/usr/share/fonts/TTF/DejaVuSansMono.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
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
                lx,ly = C.c_float(),C.c_float()
                self.logical_point(self.r,x,y,C.byref(lx),C.byref(ly))
                yield 'click' if typ == 1025 else 'mouse_up',(lx.value,ly.value)
            elif typ in (768,769):
                key = int.from_bytes(raw[20:24], sys.byteorder, signed=True)
                if typ == 769 or raw[13] == 0:
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
        latest = None
        try:
            req = urllib.request.Request('https://api.github.com/repos/womb4t/star-trader/releases/latest',headers={'User-Agent':f'StarTrader/{VERSION}','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(req,timeout=2) as response:
                data = json.loads(response.read(65536))
            latest = data.get('tag_name')
            if self.newer(latest): self.latest = latest
        except (OSError,ValueError,TypeError,AttributeError): pass
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
        self.station = [0., 0., 1500.]
        self.roll = self.station_angle = 0.
        self.autodock = False
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
        self.customs_checked = False
        self.cruise = None
        self.jump_charge = self.jump_warp = self.arrival = None
        self.npc_mine_timer = 25.
        self.spawn = 12
        self.cooldown = self.flash = self.laser_flash = 0.
        self.message = 'Welcome back, Commander.' if loaded else 'Welcome, Commander. 1 manual; U ship outfitting.'
        self.stars = [[random.uniform(-1000,1000),random.uniform(-650,650),random.uniform(-1800,1800)] for _ in range(180)]
        self.broken_down = False
        self.breakdown_in = None
        self.disabled_ship = None
        self.assist_spawn_timer = 35.
        self.dock_clearance = self.docking_pending = 0.
        self.rescue = None
        self.rescue_cooldown = 0.
        self.mouse_controls = False
        self.mouse_held = set()
        self.buttons = []
        self.running = True
        if self.p.hull <= 0: self.mode = 'dead'
        self.resume_saved_session()

    def save(self):
        self.checkpoint()

    def launch(self, departure=True):
        if departure:
            self.p.flights_since_service += 1
            self.p.maintenance = min(100,self.p.maintenance+self.p.departure_wear())
        self.breakdown_in = random.uniform(8,25) if departure and random.random() < self.breakdown_risk() else None
        self.broken_down = False
        self.disabled_ship = None
        self.assist_spawn_timer = 35.
        self.dock_clearance = self.docking_pending = 0.
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
        self.asteroids = [[150.,-70.,1000.,3],[-250.,100.,1700.,3],[320.,180.,2300.,3]]
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
        critical = ('collision','breakdown','fuel exhausted','refused','seized','repair failed','mine detected','hostile contact','clearance granted','destroyed','rescued')
        if text != old and any(word in text.lower() for word in critical):
            self.alert = dict(text=text,remaining=5.,elapsed=0.)

    def session_mode(self):
        mode = self.mode
        for _ in range(6):
            if mode in ('market','outfit','departure','launch_warning','bank'): return 'market'
            if mode in ('flight','cruise','hyperspace','dead'): return mode
            attr = {'help':'help_return','updates':'update_return','map':'map_return','engineering':'engineering_return'}.get(mode)
            if not attr: return 'flight'
            mode = getattr(self,attr,'flight')
        return 'flight'

    def checkpoint(self):
        if getattr(self,'_restoring',False): return
        fields = ('shield','speed','station','roll','station_angle','autodock','course_assist','fine_control','enemy','enemy_kind',
                  'asteroids','fragments','sun','heat','nav','rear_view','planet','planet_radius',
                  'assist_speed','mine_objects','jamming','jammer_cooldown','cloaked','customs_checked',
                  'cruise','jump_warp','npc_mine_timer','spawn','cooldown','broken_down','breakdown_in',
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
            for key in ('station','planet','sun'):
                if not isinstance(state.get(key),list) or len(state[key]) != 3 or not all(type(n) in (int,float) for n in state[key]): raise ValueError('geometry')
            for key in ('shield','speed','roll','station_angle','planet_radius','spawn','rescue_cooldown'):
                if type(state.get(key)) not in (int,float): raise ValueError('simulation scalar')
            if not 0 <= state['shield'] <= 100 or not -200 <= state['speed'] <= 400: raise ValueError('ship state')
            if state.get('enemy') is not None and (not isinstance(state['enemy'],list) or len(state['enemy']) != 5): raise ValueError('contact')
            if mode == 'cruise' and (not isinstance(state.get('cruise'),dict) or state['cruise'].get('duration',0) <= 0): raise ValueError('cruise')
            if mode == 'hyperspace' and not isinstance(state.get('jump_warp'),dict): raise ValueError('warp')
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
        self._update_simulation(dt)
        self._save_elapsed += dt
        if self._save_elapsed >= 2 or before != self.mode:
            self.checkpoint()

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
            d.text(35,175+i*36,('> ' if i == self.selected else '  ')+name,GOLD if i == self.selected else GREEN)
            d.text(320,175+i*36,str(p.cargo[i]))
            d.text(440,175+i*36,str(bay['cargo'][i]))
        d.text(720,135,f'Wallet {p.credits:.2f} cr')
        d.text(720,175,f'Bank   {p.bank_balance:.2f} cr',GOLD)
        d.text(720,215,'Transfer: '+('ALL' if self.bank_amount is None else str(self.bank_amount))+' cr')
        d.text(35,490,'Bay: '+('OWNED' if bay['owned'] else 'RENTED' if self.storage_capacity() else 'NONE / RENT EXPIRED'))
        d.text(35,530,f'Stored {sum(bay["cargo"])}/{self.storage_capacity()} t. Rent 40t: 50 cr / 7 real days. Buy 100t: 750 cr.')
        d.text(35,570,'Expired rentals retain cargo; retrieval is allowed, new deposits require renewal.')
        d.text(35,608,'Bank money and station cargo stay off-ship during salvage or ship destruction.')

    def request_launch(self):
        distance = galactic_distance(self.p.position,self.p.waypoint['position']) if self.p.waypoint else 0
        required = hyperspace_cost(distance)+(.4*self.p.mass_factor if distance > .001 else 0) if self.p.waypoint else None
        if self.p.fuel < 1 or (required is not None and required > self.p.fuel):
            self.launch_return = self.mode
            self.mode = 'launch_warning'
            self.keys.clear()
            self.message = 'Low fuel warning. F buys fuel, L launches anyway, ESC stays docked.'
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
        lines = ['FUEL WARNING',
                 'NO FUEL ABOARD' if p.fuel <= 0 else f'Fuel aboard: {p.fuel:.2f} / 7 units',
                 f'Full refill costs {p.fuel_cost()} cr; you have {p.credits:.2f} cr.',
                 'Normal flight and hyperspace both consume fuel.']
        if p.waypoint:
            cost = hyperspace_cost(galactic_distance(p.position,p.waypoint['position']))
            lines += [f'Locked course: {p.waypoint["name"]}; jump requires {cost:.2f} fuel.',
                      f'Allow another {.4*p.mass_factor:.2f} for local approach / reserve.']
        lines += ['', 'F buys a refill. L launches despite this warning.',
                  'ESC cancels departure. Sell cargo first if you need fuel money.',
                  '', 'If stranded, 6 sends a distress call. Salvage fees may apply.']
        for i,line in enumerate(lines): d.text(70,135+i*42,line,RED if i < 2 else GREEN)

    def draw_distress(self):
        d,p = self.d,self.p
        contract = self.rescue
        d.text(40,85,'DISTRESS / RECOVERY OFFERS',GOLD)
        d.text(40,125,'Station coverage: '+('YES / regulated 25% claim' if contract['covered'] else 'NO / independent salvagers'))
        for i,offer in enumerate(contract['offers']):
            d.text(40,175+i*38,f'{">" if i == contract["selected"] else " "} {offer["name"]}: {offer["percent"]}% of credits AND cargo',GOLD if i == contract['selected'] else GREEN)
        offer = contract['offers'][contract['selected']]
        fee = self.salvage_terms(offer['percent'])
        d.text(40,315,f'Exact claim: {fee["credits"]:.2f} credits + {fee["tonnes"]} tonnes (rounded up).',GOLD)
        goods = ', '.join(f'{n}t {GOODS[i]}' for i,n in enumerate(fee['cargo']) if n)
        if goods:
            for i in range(0,len(goods),86): d.text(40,355+(i//86)*27,goods[i:i+86])
        else: d.text(40,355,'No cargo to claim. Zero assets do not prevent rescue.')
        d.text(40,440,'Tow destination: '+SYSTEMS[contract['destination']][0])
        d.text(40,478,'Includes full fuel refill and emergency hull stabilisation to 25%.')
        d.text(40,516,'Equipment is preserved. Customs still apply on station arrival.')
        d.text(40,570,'UP/DOWN choose rescuer. A accepts the displayed claim.')
        d.text(40,608,'N counters (twice per private offer). R / ESC refuses with no payment.')
        d.text(40,650,'Settlement and docking save progress. Calls have a 60s cooldown.')

    def station_allows(self, system=None):
        system = self.p.system if system is None else system
        return self.p.fine < 100 or PROFILES[system][0] in ('Anarchy','Feudal')

    def request_departure(self):
        self.departure_remaining = 2.
        self.mode = 'departure'
        self.keys.clear()
        self.message = 'Requesting departure clearance. Please wait for station control.'

    def request_docking(self):
        if self.p.deep_space or math.sqrt(sum(v*v for v in self.station)) > 10000:
            self.message = 'No station traffic control in radio range (10,000m).'
        elif not self.station_allows():
            self.dock_clearance = 0
            self.docking_pending = 0
            self.message = 'Docking refused: wanted status. Seek an anarchy/feudal port.'
        elif self.dock_clearance > 0:
            self.message = f'Docking clearance remains valid for {math.ceil(self.dock_clearance)}s.'
        else:
            self.docking_pending = 2.
            self.message = 'Docking clearance requested. Await station response.'

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
        return max(.05,min(.85,.2+self.p.engineering_level*.12-(100-condition)*.001))

    def train_engineering(self):
        if self.engineering_return not in ('market','outfit'):
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
        if self.engineering_return != 'flight':
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
                 '', '8 / ESC returns. Distress 6 is available from the cockpit.']
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
        if not self.station_allows():
            self.message = 'Docking refused: wanted status.'
            return
        inspection = self.inspect_cargo() if not self.customs_checked else ''
        self.mode = 'market'
        self.shield = 100
        self.speed = 0
        self.autodock = False
        self.keys.clear()
        self.cloaked = False
        self.message = ('Docked.' + inspection) if inspection else 'Docked. F fuel; R repairs; U outfitting; P pay fines.'
        self.save()

    def slot_error(self):
        # A rectangular slot has the same orientation after half a turn.
        return (self.station_angle - self.roll + math.pi/2) % math.pi - math.pi/2

    def docking_safe(self):
        x,y,_ = self.station
        c,s = math.cos(self.station_angle),math.sin(self.station_angle)
        x,y = x*c+y*s,-x*s+y*c
        return abs(x) <= 14 and abs(y) <= 6 and 0 < self.speed <= 25 and abs(self.slot_error()) <= DOCK_ROLL_TOLERANCE + 1e-12 and not self.enemy and self.dock_clearance > 0 and self.station_allows()

    def damage(self, amount):
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        self.p.hull = max(0, self.p.hull - (amount-absorbed))
        self.flash = 0.15
        if self.p.hull <= 0:
            self.mode = 'dead'
            self.autodock = False
        if amount >= 1: self.checkpoint()

    def destroy_enemy(self):
        self.enemy = None
        self.ship_target = None
        if self.enemy_kind == 'police': self.p.fine += 150
        else: self.p.credits += 35
        self.p.kills += 1
        self.spawn = 24
        self.message = 'Police ship destroyed. Fine increased by 150 cr.' if self.enemy_kind == 'police' else 'Hostile destroyed. Bounty: 35 credits.'

    def key(self, k):
        if self.mode == 'bank':
            if k in (ord('9'),27): self.mode = 'market'
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
            if k == ord('l'): self.request_departure()
            elif k == ord('f'):
                self.message = self.p.refuel()
                self.save()
                if self.p.fuel >= 1: self.mode = self.launch_return
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
            if k == ord('/'):
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
                self.mode = 'market' if self.mode == 'outfit' else 'outfit'
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
        if k == ord('7'):
            self.request_docking()
            return
        if k == ord('4'):
            self.rear_view = not self.rear_view
            self.laser_flash = 0
            self.message = ('REAR VIEW - rear pulse laser ready.' if 'rear' in self.p.equipment else 'REAR VIEW - no rear laser fitted. Buy one in outfitting.') if self.rear_view else 'FORWARD VIEW.'
            return
        if k == ord('5'):
            targets = ([self.enemy] if self.enemy is not None else [])+([self.disabled_ship['object']] if self.disabled_ship else [])
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
            elif not self.station_allows(): self.message = 'Docking refused: wanted status.'
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
                self.p.missiles -= 1
                self.destroy_enemy()
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
        if not w: self.message = 'Lock a course on the galaxy map first.'; return
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

    def arrive(self, position, system):
        self.p.position = list(position)
        self.p.deep_space = system is None
        if system is not None: self.p.system = system
        self.launch(departure=False)
        if system is not None: self.station = [random.uniform(-80,80),random.uniform(-50,50),2200.]
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
        d.text(30,75,'GALAXY / arrows select / TAB free cursor / ENTER lock')
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
            d.text(x+9,y-15,name)
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
            info += [SYSTEMS[i][1],f'Technology {TECH[i]}',govt,f'Population {pop:.1f} billion',f'Diameter {size:,} km',
                     'Exports: food / ore' if SYSTEMS[i][1] == 'Agricultural' else 'Exports: technology' if SYSTEMS[i][1] == 'Industrial' else 'Exports: mixed goods',
                     'Customs: minimal' if govt in ('Anarchy','Feudal') else 'Customs: regulated',
                     'Docking: allowed' if self.station_allows(i) else 'Docking: REFUSED (wanted)']
        else: info += ['Uninhabited coordinates','No station or services']
        for i,line in enumerate(info): d.text(720,155+i*31,line,GOLD if i==0 else GREEN)
        if self.map_input:
            d.text(30,610,('Search planet: ' if self.map_input == 'search' else 'Coordinates X,Y: ')+self.map_text+'_',GOLD)
            if self.map_input == 'search':
                matches = [s[0] for s in SYSTEMS if self.map_text.casefold() in s[0].casefold()]
                d.text(30,645,'Matches: '+', '.join(matches),GREEN)
            else: d.text(30,645,'Range 0..10 on both axes. ENTER locks; ESC cancels.')
        else:
            d.text(30,610,'Selection: '+('free coordinate cursor' if self.cursor_mode else 'planet list'))
            d.text(30,645,'Locked: '+(p.waypoint['name'] if p.waypoint else 'none'))

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
        for rock in self.asteroids: contacts.append(('object',rock,'ASTEROID',GOLD))
        for ore in self.fragments: contacts.append(('object',ore,'ORE',(150,190,255)))
        contacts.append(('object',self.sun,'SUN',GOLD))
        return contacts

    def scanner_position(self, obj):
        x,z = obj[0],obj[2]
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
        if kind in ('ship','disabled'):
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

    def draw_scanner(self):
        d = self.d
        d.fill(840,80,230,165,(5,16,27))
        d.rect(840,80,230,165,(45,105,115))
        d.text(850,85,'SCANNER  2500m',GREEN)
        d.line(870,165,1040,165,(35,75,85))
        d.line(955,112,955,218,(35,75,85))
        d.fill(952,162,6,6,(235,245,250))
        for kind,obj,label,color in self.scanner_contacts():
            x,y = self.scanner_position(obj)
            d.fill(x-3,y-3,6,6,color)
            if kind in ('ship','disabled') and obj is self.ship_target: d.rect(x-7,y-7,14,14,GOLD)
        d.text(850,220,'Click / 5 target',(135,175,185))

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

    def scoop(self):
        if 'scoops' not in self.p.equipment:
            self.message = 'Fuel / cargo scoops required.'
            return
        nearby = next((f for f in self.fragments if math.sqrt(sum(v*v for v in f)) < 260),None)
        if nearby is None: self.message = 'Fly within 260 m of an ore fragment.'
        elif sum(self.p.cargo) >= self.p.capacity: self.message = 'Cargo hold full.'
        elif abs(self.speed) > 50: self.message = 'Slow below 50 to collect ore.'
        else:
            self.p.cargo[2] += 1
            self.fragments.remove(nearby)
            self.message = 'Scooped 1 tonne of ore. Sell it at a station.'

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

    def move_world(self, dx, dy, dz):
        for obj in [self.station,self.sun,self.planet] + ([self.disabled_ship['object']] if self.disabled_ship else []) + self.asteroids + self.fragments + self.mine_objects:
            obj[0] -= dx
            obj[1] -= dy
            obj[2] -= dz

    def _update_simulation(self, dt):
        if self.mode == 'departure':
            self.departure_remaining = max(0,self.departure_remaining-dt)
            if self.departure_remaining == 0: self.message = 'Departure clearance granted. L launches; ESC stays docked.'
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
                self.arrive(destination['position'],destination['system'])
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
                if self.station_allows():
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
        self.assist_spawn_timer -= dt
        if self.assist_spawn_timer <= 0 and self.disabled_ship is None and self.enemy is None and math.sqrt(sum(v*v for v in self.station)) > 1000:
            self.disabled_ship = dict(object=[-160.,70.,850.],hull=40)
            self.message = 'Disabled ship detected. Select its gold scanner contact; engineering 8.'
        self.cooldown = max(0,self.cooldown-dt)
        self.flash = max(0,self.flash-dt)
        self.laser_flash = max(0,self.laser_flash-dt)
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
            precision = .2 if self.fine_control else 1.
            self.roll += ((ord('e') in self.keys)-(ord('q') in self.keys))*dt/mass*precision
            # Steering is in cockpit coordinates, including while rolling.
            horizontal = ((RIGHT in self.keys)-(LEFT in self.keys))*110*dt/mass*precision
            vertical = ((DOWN in self.keys)-(UP in self.keys))*85*dt/mass*precision
            c,s = math.cos(self.roll),math.sin(self.roll)
            dx,dy = horizontal*c-vertical*s,horizontal*s+vertical*c
        if self.course_assist and not self.autodock:
            target,label = self.active_navigation()
            remote = self.nav == 'course' and self.p.waypoint and galactic_distance(self.p.position,self.p.waypoint['position']) > .001
            if target is None or remote or target[2] <= 0:
                self.course_assist = False
                self.message = 'Guidance unavailable: use H/T for a galaxy course, or select a local target ahead.'
            else:
                # Match the existing local-flight model: centre the beacon,
                # without commanding forward speed or station-slot roll.
                dx = max(-110*dt/mass,min(110*dt/mass,target[0]*min(1,2*dt/mass)))
                dy = max(-85*dt/mass,min(85*dt/mass,target[1]*min(1,2*dt/mass)))
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
            self.heat = min(120,self.heat + (6 if sun_range > 250 else 30)*dt)
            if 'scoops' in self.p.equipment and 10 <= self.speed <= 60 and 150 < sun_range <= 500:
                self.p.fuel = min(7,self.p.fuel+0.15*dt)
                self.message = 'Sun skimming: collecting fuel. Turn away before overheating!'
            if self.heat > 90: self.damage(15*dt)
            if self.mode == 'dead': return
        else: self.heat = max(0,self.heat-10*dt)
        self.spawn -= dt
        if self.spawn <= 0 and not self.enemy and self.station[2] > 450:
            self.enemy_kind = 'police' if self.p.fine > 0 and random.random() < .5 else 'pirate'
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
                self.damage(7 if abs(e[0])<250 and abs(e[1])<180 else 2)
                if self.mode == 'dead': return
        self.ship_collisions(ship_previous)
        if self.mode == 'dead': return
        if 32 in self.keys and self.cooldown <= 0:
            self.fire_laser()
        self.shield = min(100,self.shield+dt*(3 if 'energy' in self.p.equipment else 1.5)*(0.3 if self.cloaked else 1))
        if self.p.hull <= 0: self.mode = 'dead'
        self.update_jump_charge(dt)

    def fire_laser(self):
        if self.rear_view and 'rear' not in self.p.equipment:
            self.cooldown = .3
            self.message = 'No rear laser fitted. U opens outfitting when docked.'
            return
        self.cloaked = False
        weapon = 'pulse' if self.rear_view else self.p.laser
        delay,power = LASERS[weapon]
        self.cooldown,self.laser_flash = delay,.09
        if self.enemy and self.on_target(self.enemy):
            self.enemy[3] -= power
            if self.enemy[3] <= 0: self.destroy_enemy()
        elif weapon == 'mining':
            rock = next((r for r in self.asteroids if self.on_target(r)),None)
            if rock:
                rock[3] -= 1
                if rock[3] <= 0:
                    self.asteroids.remove(rock)
                    self.fragments += [[rock[0]+offset,rock[1]+10,rock[2]] for offset in (-18,0,18)]
                    self.message = 'Asteroid fragmented! Approach slowly; O collects ore within 260m.'

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
        d = self.d
        d.fill(x,y,w,28,(13,35,46))
        d.rect(x,y,w,28,(55,125,135))
        d.text(x+5,y+3,label,GREEN)
        callback = action if action is not None else lambda:self.mouse_key(key,hold)
        self.buttons.append((x,y,w,28,callback))

    def mouse_row(self,x,y,w,h,action):
        self.buttons.append((x,y,w,h,action))

    def draw_mouse_ui(self):
        self.buttons = []
        d = self.d
        modal = self.mode in ('distress','departure','launch_warning','engineering','hyperspace','bank')
        if self.mode == 'flight':
            self.mouse_button(310,18,92,'Actions',action=lambda:setattr(self,'mouse_controls',not self.mouse_controls))
        if not modal:
            self.mouse_button(408,18,50,'Help',ord('1'))
            self.mouse_button(462,18,70,'Update',ord('2'))
        self.mouse_button(536,18,45,'FS',action=self.mouse_fullscreen)
        self.mouse_button(585,18,45,'<' if modal or self.mode in ('help','updates') else 'X',action=self.mouse_back)
        row_y = 674
        if self.mode in ('market','outfit'):
            if self.mode == 'market':
                for i in range(len(GOODS)):
                    self.mouse_row(35,165+i*35,610,35,lambda i=i:setattr(self,'selected',i))
                labels = [('Buy',ord('b')),('Sell',ord('s')),('Fuel',ord('f')),('Service',ord('r')),('Outfit',ord('u')),('Launch',ord('l')),('Map',ord('g')),('Skills',ord('8'))]
            else:
                start = max(0,min(self.shop_selected-4,len(EQUIPMENT)-8))
                for i in range(start,min(start+8,len(EQUIPMENT))):
                    self.mouse_row(35,130+(i-start)*37,720,37,lambda i=i:setattr(self,'shop_selected',i))
                self.mouse_button(690,90,45,'Up',UP)
                self.mouse_button(740,90,60,'Down',DOWN)
                labels = [('Fit',ord('b')),('Fuel',ord('f')),('Service',ord('r')),('Market',ord('u')),('Launch',ord('l')),('Map',ord('g')),('Skills',ord('8')),('Fines',ord('p'))]
            for i,(label,key) in enumerate(labels): self.mouse_button(35+i*128,row_y,120,label,key)
            self.mouse_button(790,570,250,'Bank / storage 9',ord('9'))
        elif self.mode == 'bank':
            for i in range(len(GOODS)):
                self.mouse_row(35,165+i*36,600,36,lambda i=i:setattr(self,'selected',i))
            for i,amount in enumerate([10,50,100,None]):
                self.mouse_button(720+(i%2)*145,270+(i//2)*38,135,'All' if amount is None else str(amount)+' cr',action=lambda amount=amount:setattr(self,'bank_amount',amount))
            for i,(label,key) in enumerate([('Deposit',ord('d')),('Withdraw',ord('w')),('Rent bay',ord('r')),('Buy bay',ord('b'))]): self.mouse_button(35+i*255,638,240,label,key)
            for i,(label,key) in enumerate([('Store 1t',ord('s')),('Retrieve 1t',ord('t')),('Return',ord('9'))]): self.mouse_button(35+i*340,674,320,label,key)
        elif self.mode == 'map':
            labels = [('Search',ord('/'),False),('Coords',ord('c'),False),('Lock',13,False),('Hold Jump',ord('h'),True),('Cruise',ord('t'),False),('Return',ord('g'),False)]
            if self.map_input:
                labels = [('Confirm',13,False),('Erase',8,False),('Cancel',27,False)]
            for i,(label,key,hold) in enumerate(labels): self.mouse_button(35+i*166,row_y,155,label,key,hold=hold)
        elif self.mode == 'launch_warning':
            for i,(label,key) in enumerate([('Buy fuel',ord('f')),('Request launch',ord('l')),('Cancel',27)]): self.mouse_button(50+i*300,row_y,280,label,key)
        elif self.mode == 'departure':
            self.mouse_button(50,row_y,300,'Launch when cleared',ord('l'))
            self.mouse_button(370,row_y,250,'Cancel',27)
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
            for i,(label,key) in enumerate([('Cancel cruise',ord('t')),('Map',ord('g')),('Distress',ord('6'))]): self.mouse_button(50+i*300,row_y,280,label,key)
        elif self.mode == 'dead':
            self.mouse_button(50,row_y,350,'Recover starter ship',ord('r'))
            self.mouse_button(440,row_y,300,'New pilot / reset',ord('n'))
        if self.mode == 'flight' and self.mouse_controls:
            groups=[('Fly', [('Throttle',ord('w'),True),('Brake/rev',ord('s'),True),('Fire',32,True),('Left',LEFT,True),('Up',UP,True),('Right',RIGHT,True),('Roll L',ord('q'),True),('Down',DOWN,True),('Roll R',ord('e'),True)]),
                ('Nav',[('Map',ord('g'),False),('Hold jump',ord('h'),True),('Cruise',ord('t'),False),('Station',ord('d'),False),('Planet',ord('p'),False),('Rocks',ord('a'),False),('Sun',ord('j'),False),('Scoop',ord('o'),False),('Guide Y',ord('y'),False)]),
                ('Fight',[('Fire',32,True),('View 4',ord('4'),False),('Laser',ord('v'),False),('Missile',ord('m'),False),('Mine',ord('b'),False),('Jammer',ord('z'),False),('Cloak',ord('k'),False),('Target',ord('5'),False)]),
                ('Safety',[('Radio 7',ord('7'),False),('Autodock',ord('c'),False),('Skills',ord('8'),False),('Distress',ord('6'),False),('Fine I',ord('i'),False)])]
            d.fill(30,105,350,270,(5,16,27));d.rect(30,105,350,270,GREEN)
            d.text(40,112,'COCKPIT ACTIONS',GOLD)
            for i,(title,_) in enumerate(groups):
                self.mouse_button(40+i*82,145,78,title,action=lambda i=i:setattr(self,'action_tab',i))
                if i == self.action_tab: d.rect(40+i*82,145,78,28,GOLD)
            for i,(label,key,hold) in enumerate(groups[self.action_tab][1]): self.mouse_button(40+(i%3)*110,190+(i//3)*45,105,label,key,hold=hold)
            d.text(40,341,'Hold movement / fire buttons.',(130,175,185))

    def mouse_fullscreen(self):
        self.d.is_fullscreen = not self.d.is_fullscreen
        self.d.fullscreen(self.d.win,0x1001 if self.d.is_fullscreen else 0)

    def mouse_back(self):
        if self.mode == 'help': self.key(ord('1'))
        elif self.mode == 'updates': self.key(ord('2'))
        else: self.key(27)

    def help_sections(self):
        return [
            ('Start',[
                ('First trade','B / S','Buy food on Lave. Sell it at an industrial port such as Zaonce.'),
                ('Mouse controls','Actions','Use the cockpit Actions tabs for flying, navigation, weapons and safety.'),
                ('Plan a trip','G / ENTER','Choose a planet or coordinate, check fuel, then lock your course.'),
                ('Leaving the station','L','Request clearance, wait for approval, then launch. Read fuel warnings.'),
                ('Keep a reserve','F / R','Buy fuel and service the hull while docked. Cargo adds weight and inertia.'),
                ('Leaving the game','ESC / click X','Dock for a safe logout. In space your saved ship continues unattended.')]),
            ('Flight',[
                ('Throttle and braking','HOLD W / S','W accelerates. S brakes, then reverses. Heavy cargo makes stopping slower.'),
                ('Fine steering','I + ARROWS','I toggles 20% steering and Q/E roll for docking. Safety tab has a mouse toggle.'),
                ('Rolling','HOLD Q / E','Roll the ship left or right to match the station entrance.'),
                ('Look behind','4','Toggle rear view. Your course stays the same; a rear laser must be fitted.'),
                ('Local navigation','D / P / A / J','Select station, planet, rocks or sun. Gold dots and arrows show the bearing.'),
                ('Pick up ore','O','Fit scoops. Get within 260m of a fragment at speed 50 or below.')]),
            ('Navigation',[
                ('Galaxy map','G','Click a planet or empty point. Planet profiles show coordinates and services.'),
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
                ('Training and fines','8 / P','Buy engineering training while docked. Pay fines to regain port access.'),
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
        d.text(28,20,'S T A R   T R A D E R',GREEN)
        location = 'In transit' if self.mode == 'hyperspace' else 'Deep space' if p.deep_space or self.mode == 'cruise' else SYSTEMS[p.system][0]
        d.text(640,20,f'{location}  CR {p.credits:.0f}  KILLS {p.kills}')
        d.line(25,52,W-25,52)
        if self.mode == 'engineering':
            self.draw_engineering()
        elif self.mode == 'departure':
            d.text(80,150,'STATION TRAFFIC CONTROL',GOLD)
            d.text(80,220,f'Requesting departure: {self.departure_remaining:.1f}s' if self.departure_remaining else 'Departure clearance GRANTED.')
            d.text(80,290,'L launches when cleared. ESC cancels and stays docked.')
            d.text(80,345,f'Next flight breakdown risk: {self.breakdown_risk(True)*100:.1f}%. Station R services your ship.')
        elif self.mode == 'launch_warning':
            self.draw_launch_warning()
        elif self.mode == 'distress':
            self.draw_distress()
        elif self.mode == 'hyperspace':
            self.draw_hyperspace()
        elif self.mode == 'help':
            self.draw_help()
        elif self.mode == 'updates':
            latest = self.updates.latest
            lines = ['STAR TRADER / UPDATES',f'Installed version: {VERSION}',
                'New release: '+latest if latest else ('No newer release detected.' if self.updates.checked else 'Offline, disabled, or check still pending.'),
                '', 'Updates are optional. Saved games are preserved.',
                'In a terminal, from your game checkout:',
                '    python3 update.py', '',
                'Or run the installed updater:',
                '    python3 "${XDG_DATA_HOME:-$HOME/.local/share}/star-trader/update.py"',
                '', 'The updater requires a clean main branch and stops on local edits.',
                'It fetches the official repository, then reruns the installer.',
                'Release notes: github.com/womb4t/star-trader/releases',
                '', 'Daily update checks run in the background and fail silently offline.',
                'Use --no-update-check to disable network checks.', '', '2 or ESC returns to the game.']
            for i,line in enumerate(lines): d.text(30,80+i*31,line,GOLD if i==2 else GREEN)
        elif self.mode in ('market','outfit'):
            if self.mode == 'market':
                d.text(35,85,'ORBITAL EXCHANGE / '+SYSTEMS[p.system][1].upper())
                for x,label in [(35,'COMMODITY'),(280,'BUY'),(380,'SELL'),(480,'STOCK'),(580,'HOLD')]:
                    d.text(x,130,label)
                for i,g in enumerate(GOODS):
                    color = GOLD if i == self.selected else GREEN
                    d.text(35,170+i*35,('> ' if i == self.selected else '  ')+g+(' *' if i in ILLEGAL else ''),color)
                    for x,value in [(280,quote(p.system,i)),(380,quote(p.system,i,False)),(480,p.stock[p.system][i]),(580,p.cargo[i])]:
                        d.text(x,170+i*35,str(value),color)
                d.text(35,470,'BUY = you pay. SELL = you receive. * Illegal: customs risk.')
            else:
                d.text(35,85,f'SHIP OUTFITTING / LOCAL TECH {TECH[p.system]} / U market')
                start = max(0,min(self.shop_selected-4,len(EQUIPMENT)-8))
                for i in range(start,min(start+8,len(EQUIPMENT))):
                    key,label,cost,tech,desc = EQUIPMENT[i]
                    state = 'FITTED' if key in p.equipment else f'TECH {tech}' if tech>TECH[p.system] else 'AVAILABLE'
                    if key in ('missile','mine'): state = f'{p.missiles if key == "missile" else p.mines}/4 ABOARD'
                    d.text(35,135+(i-start)*37,f'{">" if i==self.shop_selected else " "} {label:<23} {cost:>4} cr  {state}',GOLD if i==self.shop_selected else GREEN)
                d.text(35,455,EQUIPMENT[self.shop_selected][4],GOLD)
                d.text(35,490,'UP/DOWN select; B or ENTER purchases and fits equipment.')
            for i,t in enumerate(['COMMANDER STATUS',f'Cargo {sum(p.cargo)}/{p.capacity} t',f'Fuel  {p.fuel:.2f}/7',f'Hull  {p.hull:.0f}%',f'Refill {p.fuel_cost()} cr',f'Service {p.service_cost()} cr',f'Mines {p.mines}/4',f'Fine {p.fine} cr',f'Wear {p.maintenance:.0f}%',f'Eng. {p.engineering_level}/5']): d.text(790,135+i*40,t)
            d.text(35,550,'F fuel   R repair   P pay fines   U outfitting/market   L launch')
            d.text(35,590,'G galaxy chart   1 manual   ESC quit')
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
        if self.enemy: self.object(self.enemy,self.enemy_kind)
        if self.disabled_ship: self.object(self.disabled_ship['object'],'disabled')
        if self.laser_flash:
            color = GOLD if p.laser == 'mining' and not self.rear_view else RED
            d.line(160,550,550,330,color)
            d.line(940,550,550,330,color)
        d.line(530,330,542,330); d.line(558,330,570,330)
        d.line(550,310,550,322); d.line(550,338,550,350)
        clip(d.r,None)
        target,label = self.active_navigation()
        if target is not None: self.draw_marker(target,label,GOLD)
        if self.ship_target is not self.enemy and (not self.disabled_ship or self.ship_target is not self.disabled_ship['object']): self.ship_target = None
        if self.ship_target is not None: self.draw_marker(self.ship_target,'DISABLED SHIP' if self.disabled_ship and self.ship_target is self.disabled_ship['object'] else 'TARGET '+self.enemy_kind.upper(),(255,100,180))
        self.draw_scanner()
        d.text(35,73,'REAR VIEW' if self.rear_view else 'FORWARD VIEW',GOLD)
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
        d.text(35,594,f'SPEED {self.speed:.0f}  FUEL {p.fuel:.2f}  {('REAR PULSE' if 'rear' in p.equipment else 'REAR UNARMED') if self.rear_view else p.laser.upper()} LASER  MISSILES {p.missiles}  HEAT {self.heat:.0f}%')
        d.text(35,625,f'SHIELD {self.shield:.0f}%  HULL {p.hull:.0f}%  HOLD {sum(p.cargo)}/{p.capacity}t')
        error = math.degrees(self.slot_error())
        d.text(650,598,('GUIDANCE Y  ' if self.course_assist else '')+('FINE I' if self.fine_control else ''),GOLD)
        d.text(650,625,'DRIVE DISABLED' if self.broken_down else 'AUTODOCK' if self.autodock else f'SLOT {error:+.0f}/14deg '+('CLEAR' if self.dock_clearance else '7 radio'),GOLD)
        status = 'CLOAKED' if self.cloaked else 'JAMMING' if self.jamming else ''
        d.text(35,657,f'MINES {p.mines}  {status}  1 controls  2 updates  6 distress',GOLD)
        if p.fuel < 1.0:
            d.text(810,657,'LOW FUEL',RED)
        if p.waypoint:
            w = p.waypoint
            delta = [b-a for a,b in zip(p.position,w['position'])]
            d.text(35,686,f'COURSE {w["name"]} ({w["position"][0]:.2f},{w["position"][1]:.2f})  {math.hypot(*delta):.2f} LY  T cruise',GOLD)
        elif p.fuel < 1.0:
            d.text(35,686,'LOW FUEL - buy fuel / skim the sun. Press 6 for distress.',RED)
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
        if kind in ('pirate','police','disabled'):
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


def main():
    global SAVE
    if '--version' in sys.argv:
        print(VERSION)
        return
    if '--self-test' in sys.argv:
        self_test()
        return
    display = None
    scratch = None
    instance_file = None
    try:
        if '--smoke-test' in sys.argv:
            scratch = tempfile.TemporaryDirectory(prefix='star-trader-smoke-')
            SAVE = Path(scratch.name)/'save.json'
        SAVE.parent.mkdir(parents=True,exist_ok=True)
        instance_file = SAVE.with_suffix('.lock').open('a')
        try: fcntl.flock(instance_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError: raise RuntimeError('Star Trader is already running for this save. Close it before starting another copy.')
        display = Display()
        game = Game(display)
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
    except (OSError,RuntimeError) as e:
        print(f'Unable to start: {e}',file=sys.stderr)
        sys.exit(1)
    finally:
        if display: display.quit()
        if instance_file: instance_file.close()
        if scratch: scratch.cleanup()


if __name__ == '__main__':
    main()
