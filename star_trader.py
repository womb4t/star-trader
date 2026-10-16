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

VERSION = '0.2.0'
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

    def repair(self):
        cost = math.ceil((100 - self.hull) * 0.5)
        if self.credits < cost: return f'Repairs cost {cost} cr.'
        self.credits -= cost
        self.hull = 100
        return f'Hull repaired: {cost} cr. Fuel sold separately (F).'

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
        self.d = display
        self.p = Pilot()
        loaded = self.p.load()
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
        self.enemy = None
        self.asteroids = []
        self.fragments = []
        self.sun = [1200., -500., 3500.]
        self.heat = 0.
        self.nav = 'station'
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
        self.npc_mine_timer = 25.
        self.spawn = 12
        self.cooldown = self.flash = self.laser_flash = 0.
        self.message = 'Welcome back, Commander.' if loaded else 'Welcome, Commander. F1 manual; U ship outfitting.'
        self.stars = [[random.uniform(-1000,1000),random.uniform(-650,650),random.uniform(20,1800)] for _ in range(180)]
        self.running = True

    def save(self):
        try:
            self.p.save()
        except OSError as e:
            self.message = 'Could not save: ' + str(e)

    def launch(self):
        self.mode = 'flight'
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
        self.speed = 30
        self.enemy = None
        self.npc_mine_timer = 25.
        self.spawn = 18
        self.roll = self.station_angle = 0.
        self.autodock = False
        self.nav = 'station'
        self.heat = 0
        self.asteroids = [[150.,-70.,1000.,3],[-250.,100.,1700.,3],[320.,180.,2300.,3]]
        self.fragments = []
        self.sun = [1200.,-500.,3500.]
        self.message = 'Approach slowly. Q/E roll to match the rotating slot. F1 manual.'

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
        return abs(x) <= 14 and abs(y) <= 6 and 0 < self.speed <= 25 and abs(self.slot_error()) <= 0.16 and not self.enemy

    def damage(self, amount):
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        self.p.hull = max(0, self.p.hull - (amount-absorbed))
        self.flash = 0.15
        if self.p.hull <= 0:
            self.mode = 'dead'
            self.autodock = False

    def destroy_enemy(self):
        self.enemy = None
        if self.enemy_kind == 'police': self.p.fine += 150
        else: self.p.credits += 35
        self.p.kills += 1
        self.spawn = 24
        self.message = 'Police ship destroyed. Fine increased by 150 cr.' if self.enemy_kind == 'police' else 'Hostile destroyed. Bounty: 35 credits.'

    def key(self, k):
        if self.mode == 'map' and self.map_input:
            self.map_edit(k)
            return
        if k == 1073741891:  # F10
            if self.mode == 'updates': self.mode = self.update_return
            else:
                self.update_return = self.mode
                self.mode = 'updates'
            self.keys.clear()
            return
        if self.mode == 'updates':
            if k == 27: self.mode = self.update_return
            return
        if k == 1073741892:
            self.d.is_fullscreen = not self.d.is_fullscreen
            self.d.fullscreen(self.d.win, 0x1001 if self.d.is_fullscreen else 0)
            return
        if k == 27:
            self.running = False
            return
        if self.mode == 'dead':
            if k == ord('n'):
                self.p = Pilot()
                self.shield = 100
                self.mode = 'market'
                self.save()
            return
        if k == 1073741882:
            if self.mode == 'help': self.mode = self.help_return
            else:
                self.help_return = self.mode
                self.mode = 'help'
            self.keys.clear()
            return
        if self.mode == 'help': return
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
            if k == ord('l'): self.launch(); return
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
        if k == ord('p'):
            self.nav = 'planet'
        if k in (UP, DOWN, LEFT, RIGHT, ord('w'),ord('s'),ord('q'),ord('e')):
            self.autodock = False
        if k == ord('d'):
            if self.p.deep_space:
                self.message = 'No station here. Use G to lock a planet.'
                return
            self.nav = 'station'
            self.message = 'Fly through slot: centre +/-14m, height +/-6m, roll +/-9deg, speed 1-25.'
        if k == ord('c'):
            if self.p.deep_space: self.message = 'No station in deep space.'
            elif 'docking' not in self.p.equipment: self.message = 'Buy a docking computer in outfitting (U).'
            elif self.enemy: self.message = 'Clear hostile contact before auto-docking.'
            elif not 65 < self.station[2] <= 2500: self.message = 'Docking computer range: 2500 m.'
            else:
                self.autodock = not self.autodock
                self.nav = 'station'
                self.message = 'Docking computer engaged. C or manual controls cancel.' if self.autodock else 'Manual control.'
        if k == ord('v'):
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
        w = self.p.waypoint
        if not w: self.message = 'Lock a course first (G, ENTER).'; return
        dist = galactic_distance(self.p.position,w['position'])
        cost = hyperspace_cost(dist)
        if dist < .001: self.message = 'Already at that coordinate.'
        elif self.mode == 'map' and self.map_return not in ('flight','cruise'):
            self.message = 'Launch before engaging hyperspace.'
        elif cost > self.p.fuel: self.message = f'Jump requires {cost:.2f} fuel; aboard {self.p.fuel:.2f}.'
        else:
            self.p.fuel = round(self.p.fuel-cost,5)
            self.arrive(w['position'],w['system'])
            self.message = f'Hyperspace complete. {w["name"]}. Fuel used: {cost:.2f}.'

    def begin_cruise(self):
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
        self.launch()
        if system is not None: self.station = [random.uniform(-80,80),random.uniform(-50,50),2200.]

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
        d.text(30,105,'/ search  C coordinates  H hyperspace  T cruise  G return')
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
                     'Customs: minimal' if govt in ('Anarchy','Feudal') else 'Customs: regulated']
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
        if z <= 5: return None
        c,s = math.cos(self.roll), math.sin(self.roll)
        return W/2+(x*c+y*s)*500/z, 330+(-x*s+y*c)*500/z, 500/z

    def on_target(self, obj, radius=32):
        projected = self.project(obj)
        return projected is not None and abs(projected[0]-W/2) < radius and abs(projected[1]-330) < radius

    def move_world(self, dx, dy, dz):
        for obj in [self.station,self.sun,self.planet] + self.asteroids + self.fragments + self.mine_objects:
            obj[0] -= dx
            obj[1] -= dy
            obj[2] -= dz

    def update(self, dt):
        if self.mode == 'cruise':
            self.update_cruise(dt)
            return
        if self.mode != 'flight': return
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
            if z < 130 and (abs(x)>12 or abs(y)>5 or abs(self.slot_error())>0.12): desired = 0
            self.speed += max(-70*dt/mass,min(70*dt/mass,desired-self.speed))
        else:
            self.speed = max(-60/mass,min(180/mass+self.assist_speed,self.speed+((ord('w') in self.keys)-(ord('s') in self.keys))*70*dt/mass))
            self.roll += ((ord('e') in self.keys)-(ord('q') in self.keys))*dt/mass
            # Steering is in cockpit coordinates, including while rolling.
            horizontal = ((RIGHT in self.keys)-(LEFT in self.keys))*110*dt/mass
            vertical = ((DOWN in self.keys)-(UP in self.keys))*85*dt/mass
            c,s = math.cos(self.roll),math.sin(self.roll)
            dx,dy = horizontal*c-vertical*s,horizontal*s+vertical*c
        dz = self.speed*dt
        required = math.sqrt(dx*dx+dy*dy+dz*dz)*.00012*mass
        if required > self.p.fuel and required:
            factor = self.p.fuel/required
            dx,dy,dz = dx*factor,dy*factor,dz*factor
            self.speed *= factor
        self.p.fuel = max(0,self.p.fuel-required)
        if self.p.fuel == 0:
            self.autodock = False
            self.message = 'Fuel exhausted. Scoop the sun if nearby, or reload your last station save.'
        self.move_world(dx,dy,dz)
        if self.enemy:
            self.enemy[0] -= dx
            self.enemy[1] -= dy
            self.enemy[2] -= dz
        if self.station[2] <= 65 and math.hypot(*self.station[:2]) < 110 and self.station[2] > -100:
            if self.docking_safe(): self.dock(); return
            self.damage(35+abs(self.speed)*0.7)
            self.station[2] = 130
            self.speed = 0
            self.autodock = False
            self.message = 'Station collision! Stop, centre the slot, match roll and approach slowly.'
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
            if star[2] < 10 or abs(star[0]) > 1800 or abs(star[1]) > 1200:
                star[:] = [random.uniform(-1000,1000),random.uniform(-650,650),1800]
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
        if 32 in self.keys and self.cooldown <= 0:
            self.cloaked = False
            delay,power = LASERS[self.p.laser]
            self.cooldown,self.laser_flash = delay,0.09
            if self.enemy and self.on_target(self.enemy):
                self.enemy[3] -= power
                if self.enemy[3] <= 0: self.destroy_enemy()
            elif self.p.laser == 'mining':
                rock = next((r for r in self.asteroids if self.on_target(r)),None)
                if rock:
                    rock[3] -= 1
                    if rock[3] <= 0:
                        self.asteroids.remove(rock)
                        self.fragments += [[rock[0]+offset,rock[1]+10,rock[2]] for offset in (-18,0,18)]
                        self.message = 'Asteroid fragmented! Approach slowly; O collects ore within 260m.'
        self.shield = min(100,self.shield+dt*(3 if 'energy' in self.p.equipment else 1.5)*(0.3 if self.cloaked else 1))
        if self.p.hull <= 0: self.mode = 'dead'

    def draw(self):
        d,p = self.d,self.p
        d.color(d.r,4,9,18,255)
        d.clear(d.r)
        d.text(28,20,'S T A R   T R A D E R',GREEN)
        location = 'Deep space' if p.deep_space or self.mode == 'cruise' else SYSTEMS[p.system][0]
        d.text(640,20,f'{location}  CR {p.credits:.0f}  KILLS {p.kills}')
        d.line(25,52,W-25,52)
        if self.mode == 'help':
            lines = ['FLIGHT MANUAL',
                'STATION: Arrows select. B buy, S sell, U outfitting, L launch.',
                'F buys fuel (3 cr/unit), R repairs, P pays fines. * = illegal.',
                'FLIGHT: Arrows steer. W/S speed/reverse. Q/E roll. SPACE laser.',
                'Cargo adds inertia, slows turning/braking and uses more fuel.',
                'V cycles lasers. M missile. B mine (arms 1.5s; blast dangerous).',
                'D station beacon. Fly into slot: speed 1-25, Q/E match roll.',
                'Centre +/-14m horizontally, +/-6m vertically; roll under 9deg.',
                'C docking computer (must be fitted). P local planet beacon.',
                'A asteroid beacon. Mining laser + SPACE breaks rock.',
                'O scoops ore within 260m at speed <=50; scoops required.',
                'J sun beacon. Scoops collect within 500m at speed 10-60.',
                'HEAT >90 damages ship. Reverse away with S to retreat.',
                'Z bought jammer: 8s active, 20s cooldown, uses .05 fuel.',
                'K bought cloak: .012 fuel/sec. Firing drops concealment.',
                'G galaxy map: / search, C coordinates, TAB free cursor.',
                'ENTER locks. H fast, expensive jump. T slow, efficient cruise.',
                'T also cancels cruise. Low fuel can strand you: plan reserves.',
                'Dock/trade/purchase to save. In space, quit retains last save.',
                'F1 return. F10 updates. F11 fullscreen. ESC quit.']
            for i,line in enumerate(lines): d.text(30,77+i*30,line)
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
                'Use --no-update-check to disable network checks.', '', 'F10 or ESC returns to the game.']
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
            for i,t in enumerate(['COMMANDER STATUS',f'Cargo {sum(p.cargo)}/{p.capacity} t',f'Fuel  {p.fuel:.2f}/7',f'Hull  {p.hull:.0f}%',f'Refill {p.fuel_cost()} cr',f'Repair {math.ceil((100-p.hull)*0.5)} cr',f'Mines {p.mines}/4',f'Fine {p.fine} cr']): d.text(790,135+i*40,t)
            d.text(35,550,'F fuel   R repair   P pay fines   U outfitting/market   L launch')
            d.text(35,590,'G galaxy chart   F1 manual   ESC quit')
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
        elif self.mode == 'dead':
            d.text(350,250,'SHIP DESTROYED',RED)
            d.text(220,300,'N starts a new pilot. ESC preserves your last station save.')
        else:
            self.draw_flight()
        d.line(25,710,W-25,710)
        notice = 'Update '+self.updates.latest+' available - F10' if self.updates.latest else self.message
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
        if self.laser_flash:
            color = GOLD if p.laser == 'mining' else RED
            d.line(160,550,550,330,color)
            d.line(940,550,550,330,color)
        d.line(530,330,542,330); d.line(558,330,570,330)
        d.line(550,310,550,322); d.line(550,338,550,350)
        clip(d.r,None)
        if self.flash: d.rect(26,65,W-52,490,RED)
        obj,label = self.station,'STATION'
        if self.nav == 'asteroid':
            objects = self.fragments or self.asteroids
            if objects: obj,label = min(objects,key=lambda r: sum(v*v for v in r[:3])),'ORE' if self.fragments else 'ASTEROID'
        elif self.nav == 'sun': obj,label = self.sun,'SUN'
        elif self.nav == 'planet' and not p.deep_space: obj,label = self.planet,'PLANET'
        if p.deep_space and self.nav in ('station','planet'):
            obj,label = [0.,0.,0.],'DEEP SPACE'
        c,s = math.cos(self.roll),math.sin(self.roll)
        x,y,z = obj[:3]
        d.text(35,563,f'BEACON {label}: X {x*c+y*s:+.0f} Y {-x*s+y*c:+.0f} Z {z:+.0f} RANGE {math.sqrt(x*x+y*y+z*z):.0f}m')
        d.text(35,594,f'SPEED {self.speed:.0f}  FUEL {p.fuel:.2f}  {p.laser.upper()} LASER  MISSILES {p.missiles}  HEAT {self.heat:.0f}%')
        d.text(35,625,f'SHIELD {self.shield:.0f}%  HULL {p.hull:.0f}%  HOLD {sum(p.cargo)}/{p.capacity}t')
        error = math.degrees(self.slot_error())
        d.text(650,625,'AUTODOCK' if self.autodock else f'SLOT ROLL {error:+.0f} deg',GOLD)
        status = 'CLOAKED' if self.cloaked else 'JAMMING' if self.jamming else ''
        d.text(35,657,f'MINES {p.mines}  {status}  F1 controls  F10 updates',GOLD)
        if p.fuel < 1.0:
            d.text(810,657,'LOW FUEL',RED)
        if p.waypoint:
            w = p.waypoint
            delta = [b-a for a,b in zip(p.position,w['position'])]
            d.text(35,686,f'COURSE {w["name"]} ({w["position"][0]:.2f},{w["position"][1]:.2f})  {math.hypot(*delta):.2f} LY  T cruise',GOLD)
        elif p.fuel < 1.0:
            d.text(35,686,'LOW FUEL - buy a refill or skim the sun with scoops.',RED)

    def object(self,obj,kind):
        projected = self.project(obj)
        if projected is None: return
        sx,sy,scale = projected
        if sx < -800 or sx > W+800 or sy < -800 or sy > H+800: return
        color = GREEN
        angle = -self.roll
        if kind in ('pirate','police'):
            points = [(-65,10),(-20,-15),(0,-5),(20,-15),(65,10),(0,28)]
            edges = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,0),(0,4),(2,5)]
            color = RED if kind == 'pirate' else (120,170,255)
        elif kind == 'station':
            angle += self.station_angle
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
        if obj[2] > 150:
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
    if '--version' in sys.argv:
        print(VERSION)
        return
    if '--self-test' in sys.argv:
        self_test()
        return
    display = None
    try:
        display = Display()
        game = Game(display)
        last = time.monotonic()
        frames = 0
        while game.running:
            now = time.monotonic()
            dt,last = min(0.05,now-last),now
            for kind,key in display.events():
                if kind == 'quit': game.running = False
                elif kind == 'blur': game.keys.clear()
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


if __name__ == '__main__':
    main()
