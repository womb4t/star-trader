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

W, H = 1100, 760
GOODS = ['Food', 'Textiles', 'Ore', 'Machinery', 'Medicine', 'Computers']
BASE = [8, 15, 24, 48, 65, 90]
SYSTEMS = [
    ('Lave', 'Agricultural', 0.15, 0.40), ('Zaonce', 'Industrial', 0.40, 0.20),
    ('Diso', 'Agricultural', 0.34, 0.64), ('Leesti', 'Industrial', 0.60, 0.46),
    ('Riedquat', 'Frontier', 0.76, 0.76), ('Tionisla', 'Industrial', 0.72, 0.16),
    ('Orerve', 'Frontier', 0.14, 0.84), ('Reorte', 'Agricultural', 0.90, 0.43)]
SAVE = Path.home() / '.local' / 'share' / 'star-trader' / 'save.json'


def price(system, good):
    rng = random.Random(system * 97 + good * 13)
    economy = SYSTEMS[system][1]
    factor = (0.65 if good < 3 else 1.25) if economy == 'Agricultural' else (1.3 if good < 3 else 0.7)
    if economy == 'Frontier':
        factor = 1.0
    return round(BASE[good] * factor * rng.uniform(0.9, 1.1))


def distance(a, b):
    return math.hypot(SYSTEMS[a][2] - SYSTEMS[b][2], SYSTEMS[a][3] - SYSTEMS[b][3]) * 10


class Pilot:
    def __init__(self):
        self.credits = 150
        self.cargo = [0] * 6
        self.system = 0
        self.fuel = 7.0
        self.hull = 100
        self.kills = 0

    def trade(self, good, buy):
        p = price(self.system, good)
        if buy and self.credits >= p and sum(self.cargo) < 20:
            self.credits -= p
            self.cargo[good] += 1
            return 'Cargo purchased.'
        if not buy and self.cargo[good] > 0:
            self.credits += p
            self.cargo[good] -= 1
            return 'Cargo sold.'
        return 'Insufficient credits / cargo hold full.' if buy else 'None aboard to sell.'

    def save(self):
        SAVE.parent.mkdir(parents=True, exist_ok=True)
        temp = SAVE.with_suffix('.tmp')
        temp.write_text(json.dumps(vars(self)), encoding='utf-8')
        temp.replace(SAVE)

    def load(self):
        try:
            d = json.loads(SAVE.read_text(encoding='utf-8'))
            assert isinstance(d, dict)
            assert type(d['system']) is int and 0 <= d['system'] < len(SYSTEMS)
            assert len(d['cargo']) == 6 and all(type(n) is int and n >= 0 for n in d['cargo']) and sum(d['cargo']) <= 20
            for key in ('credits', 'fuel', 'hull', 'kills'):
                assert type(d[key]) in (int, float) and math.isfinite(d[key]) and d[key] >= 0
            assert d['fuel'] <= 7 and d['hull'] <= 100
            for key in vars(self):
                setattr(self, key, d[key])
            return True
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            return False


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
        self.win = self.window(b'STAR TRADER - an Elite-inspired Python game', 0x2FFF0000, 0x2FFF0000, W, H, 0)
        self.r = self.renderer(self.win, -1, 2) or self.renderer(self.win, -1, 0)
        if not self.win or not self.r:
            raise RuntimeError('Could not create game window.')
        fonts = ['/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
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
            elif typ in (768,769):
                key = int.from_bytes(raw[20:24], sys.byteorder, signed=True)
                if typ == 769 or raw[13] == 0:
                    yield 'down' if typ == 768 else 'up', key


class Game:
    def __init__(self, display):
        self.d = display
        self.p = Pilot()
        loaded = self.p.load()
        self.mode = 'market'
        self.selected = 0
        self.target = (self.p.system + 1) % 8
        self.keys = set()
        self.shield = 100
        self.speed = 0
        self.station = [0., 0., 1500.]
        self.enemy = None
        self.spawn = 12
        self.cooldown = 0
        self.flash = 0
        self.message = 'Welcome back, Commander.' if loaded else 'Welcome, Commander. Buy cheap, sell high. F1 for flight manual.'
        self.stars = [[random.uniform(-1000,1000),random.uniform(-650,650),random.uniform(20,1800)] for _ in range(180)]
        self.running = True

    def save(self):
        try:
            self.p.save()
        except OSError as e:
            self.message = 'Could not save: ' + str(e)

    def launch(self):
        self.mode = 'flight'
        self.station = [0.,0.,1500.]
        self.speed = 30
        self.enemy = None
        self.spawn = 14
        self.message = 'Station ahead. D to dock within 350 m, centred, speed below 40.'

    def key(self, k):
        if k == 27:
            self.running = False
        elif k == 1073741882:  # F1
            self.mode = 'flight' if self.mode == 'help' else 'help' if self.mode == 'flight' else 'help_docked' if self.mode != 'help_docked' else 'market'
        elif self.mode == 'dead':
            if k == ord('n'):
                self.p = Pilot()
                self.shield = 100
                self.mode = 'market'
                self.save()
        elif self.mode in ('help','help_docked'):
            return
        elif k == ord('g'):
            if self.mode == 'map':
                self.mode = self.map_return
            else:
                self.map_return = self.mode
                self.mode = 'map'
        elif self.mode == 'map':
            if k in (1073741904,1073741906): self.target = (self.target-1)%8
            if k in (1073741903,1073741905): self.target = (self.target+1)%8
            if k == ord('h'):
                cost = distance(self.p.system,self.target)
                if self.target == self.p.system:
                    self.message = 'Select another system.'
                elif cost > self.p.fuel:
                    self.message = 'Not enough fuel. Refuel at a station.'
                elif self.map_return != 'flight':
                    self.message = 'Launch before engaging hyperspace.'
                else:
                    self.p.fuel = round(self.p.fuel-cost,2)
                    self.p.system = self.target
                    self.launch()
                    self.station = [random.uniform(-80,80),random.uniform(-50,50),2200.]
                    self.message = 'Hyperspace complete. Welcome to '+SYSTEMS[self.p.system][0]+'.'
        elif self.mode == 'market':
            if k == 1073741906: self.selected = (self.selected-1)%6
            if k == 1073741905: self.selected = (self.selected+1)%6
            if k in (ord('b'),ord('s')):
                self.message = self.p.trade(self.selected,k==ord('b'))
                self.save()
            if k == ord('l'): self.launch()
            if k == ord('r'):
                cost = math.ceil((7-self.p.fuel)*3 + (100-self.p.hull)*0.5)
                if self.p.credits >= cost:
                    self.p.credits -= cost
                    self.p.fuel,self.p.hull,self.shield = 7.,100,100
                    self.message = 'Ship fuelled and repaired.'
                    self.save()
                else: self.message = f'Service costs {cost} credits.'
        elif self.mode == 'flight' and k == ord('d'):
            x,y,z = self.station
            if z < 350 and abs(x) < 60 and abs(y) < 60 and self.speed < 40 and not self.enemy:
                self.mode = 'market'
                self.shield = 100
                self.message = 'Docking complete. Progress saved.'
                self.save()
            else: self.message = 'Dock: range <350m, centred, speed <40, no hostile nearby.'

    def update(self, dt):
        if self.mode != 'flight': return
        self.cooldown = max(0,self.cooldown-dt)
        self.flash = max(0,self.flash-dt)
        self.speed = max(0,min(180,self.speed + ((ord('w') in self.keys)-(ord('s') in self.keys))*70*dt))
        dx = ((1073741903 in self.keys)-(1073741904 in self.keys))*210*dt
        dy = ((1073741905 in self.keys)-(1073741906 in self.keys))*160*dt
        self.station[0] -= dx
        self.station[1] -= dy
        self.station[2] = max(110,self.station[2]-self.speed*dt)
        for s in self.stars:
            s[0] -= dx*0.5
            s[1] -= dy*0.5
            s[2] -= (self.speed+12)*dt
            if s[2] < 10 or abs(s[0]) > 1800 or abs(s[1]) > 1200:
                s[:] = [random.uniform(-1000,1000),random.uniform(-650,650),1800]
        self.spawn -= dt
        if self.spawn <= 0 and not self.enemy and self.station[2] > 450:
            self.enemy = [random.uniform(-160,160),random.uniform(-90,90),850.,3,0.]
            self.message = 'Hostile contact! Centre target and fire SPACE.'
        if self.enemy:
            e = self.enemy
            e[0] += (math.sin(time.monotonic()*1.7)*35*dt-dx)
            e[1] += (math.cos(time.monotonic()*1.3)*25*dt-dy)
            e[2] = max(250,e[2]-35*dt)
            e[4] += dt
            if e[4] > 2.0:
                e[4] = 0
                damage = 7 if abs(e[0]) < 250 and abs(e[1]) < 180 else 2
                absorbed = min(self.shield,damage)
                self.shield -= absorbed
                self.p.hull -= damage-absorbed
                self.flash = 0.12
            if 32 in self.keys and self.cooldown <= 0:
                self.cooldown = 0.24
                if abs(e[0]*500/e[2]) < 40 and abs(e[1]*500/e[2]) < 30:
                    e[3] -= 1
                    if e[3] <= 0:
                        self.enemy = None
                        self.p.credits += 35
                        self.p.kills += 1
                        self.spawn = 22
                        self.message = 'Hostile destroyed. Bounty: 35 credits.'
        elif 32 in self.keys and self.cooldown <= 0:
            self.cooldown = 0.24
        self.shield = min(100,self.shield+dt*1.5)
        if self.p.hull <= 0:
            self.p.hull = 0
            self.mode = 'dead'

    def draw(self):
        d,p = self.d,self.p
        d.color(d.r,4,9,18,255)
        d.clear(d.r)
        d.text(28,20,'S T A R   T R A D E R', (93,255,192))
        d.text(660,20,f'{SYSTEMS[p.system][0]}   CR {p.credits}   KILLS {p.kills}')
        d.line(25,52,W-25,52)
        if self.mode in ('help','help_docked'):
            lines = ['FLIGHT MANUAL', '', 'You are an independent trader with a 20-tonne cargo hold.',
                     'Buy local exports; sell them where demand is higher.',
                     'Agricultural worlds export food, textiles and ore.',
                     'Industrial worlds export machinery, medicine and computers.', '',
                     'DOCKED   Up/Down select   B buy   S sell   R service   L launch',
                     'FLIGHT   Arrows steer    W/S throttle    SPACE fire lasers',
                     '         D dock: <350 m, centred, speed <40, no hostile',
                     'GALAXY   G opens/closes chart   Arrows select   H hyperspace',
                     '         Jump fuel equals distance. Full tank = 7 light years.', '',
                     'Pirates pay a 35-credit bounty. Shields regenerate in flight.',
                     'Dock and trade to save. Quitting in space preserves last dock.',
                     'F1 returns to game. ESC quits. New pilots begin with 150 credits.', '',
                     'Original tribute; no original Elite code or assets included.']
            for i,line in enumerate(lines): d.text(40,85+i*29,line)
        elif self.mode == 'market':
            d.text(40,85,'ORBITAL EXCHANGE / '+SYSTEMS[p.system][1].upper())
            d.text(40,130,'COMMODITY           PRICE       ABOARD')
            for i,g in enumerate(GOODS):
                d.text(40,175+i*43,f'{">" if i==self.selected else " "} {g:<17} {price(p.system,i):>4} cr       {p.cargo[i]:>2} t', (255,206,113) if i==self.selected else (160,225,213))
            d.text(650,160,'COMMANDER STATUS')
            for i,t in enumerate([f'Cargo    {sum(p.cargo)}/20 t', f'Fuel     {p.fuel:.1f}/7 LY', f'Hull     {p.hull:.0f}%',f'Service  {math.ceil((7-p.fuel)*3+(100-p.hull)*0.5)} cr']): d.text(650,210+i*42,t)
            d.text(40,505,'UP/DOWN select   B buy   S sell   R refuel + repair')
            d.text(40,545,'L launch   G galaxy chart   F1 manual   ESC quit')
        elif self.mode == 'map':
            d.text(40,80,'GALAXY CHART / ARROWS select / H jump / G return')
            for i,(name,econ,x,y) in enumerate(SYSTEMS):
                sx,sy = 65+x*600,125+y*410
                d.rect(sx-5,sy-5,10,10,(255,204,100) if i==self.target else (68,227,182))
                d.text(sx+12,sy-10,name)
                if i == p.system: d.text(sx+12,sy+12,'YOU')
            cost = distance(p.system,self.target)
            d.text(765,180,SYSTEMS[self.target][0],(255,204,100))
            d.text(765,220,SYSTEMS[self.target][1])
            d.text(765,270,f'Distance {cost:.1f} LY')
            d.text(765,310,f'Fuel     {p.fuel:.1f} LY')
            d.text(40,580,'Dock at destination to save your journey.')
        elif self.mode == 'dead':
            d.text(350,250,'SHIP DESTROYED',(255,110,100))
            d.text(230,300,'N starts a new pilot. ESC keeps your last saved game.')
        else:
            for x,y,z in self.stars:
                sx,sy = W/2+x*500/z,330+y*500/z
                if 25<sx<W-25 and 65<sy<575: d.line(sx,sy,sx+1,sy+1,(110,145,160))
            self.object(self.station,False)
            if self.enemy: self.object(self.enemy,True)
            d.line(530,330,542,330)
            d.line(558,330,570,330)
            d.line(550,310,550,322)
            d.line(550,338,550,350)
            if self.cooldown > 0.15:
                d.line(160,570,550,330,(255,100,90))
                d.line(940,570,550,330,(255,100,90))
            if self.flash: d.rect(26,65,W-52,510,(255,65,65))
            d.text(40,590,f'STATION {self.station[2]:.0f} m   SPEED {self.speed:.0f}   FUEL {p.fuel:.1f} LY')
            for i,(label,value) in enumerate([('SHIELD',self.shield),('HULL',p.hull)]):
                x = 40+i*340
                d.text(x,630,f'{label} {value:.0f}%')
                d.rect(x+135,632,150,18)
                for j in range(int(value*1.46)): d.line(x+137+j,635,x+137+j,647)
            d.text(40,669,'Arrows steer  W/S speed  SPACE fire  D dock  G chart  F1 help')
        d.line(25,710,W-25,710)
        d.text(28,725,self.message[:94],(255,206,113))
        d.present(d.r)

    def object(self,obj,enemy):
        x,y,z = obj[:3]
        sx,sy = W/2+x*500/z,330+y*500/z
        scale = 500/z
        if not (0 < sx < W and 70 < sy < 560): return
        if enemy:
            pts = [(-65,10),(-20,-15),(0,-5),(20,-15),(65,10),(0,28)]
            edges = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,0),(0,4),(2,5)]
            color = (255,112,100)
        else:
            a = time.monotonic()*0.15
            pts = [(math.cos(a+i*math.pi/4)*100,math.sin(a+i*math.pi/4)*100) for i in range(8)]
            pts += [(-25,-25),(25,-25),(25,25),(-25,25)]
            edges = [(i,(i+1)%8) for i in range(8)] + [(8,9),(9,10),(10,11),(11,8)] + [(i,8+i//2) for i in range(8)]
            color = (68,227,182)
        for a,b in edges:
            ax,ay = pts[a]; bx,by = pts[b]
            self.d.line(sx+ax*scale,sy+ay*scale,sx+bx*scale,sy+by*scale,color)
        self.d.text(max(30,min(W-200,sx-70)),max(75,min(540,sy+110*scale)), 'PIRATE' if enemy else 'CORIOLIS STATION',color)


def self_test():
    p = Pilot()
    initial = p.credits
    assert p.trade(0,True) == 'Cargo purchased.' and p.cargo[0] == 1
    p.trade(0,False)
    assert p.credits == initial and p.cargo[0] == 0
    p.cargo = [20,0,0,0,0,0]
    p.trade(0,True)
    assert sum(p.cargo) == 20
    assert price(0,0) < price(1,0) and price(1,5) < price(0,5)
    assert distance(0,0) == 0 and 0 < distance(0,1) < 7
    print('Economy, cargo capacity and navigation checks passed.')


def main():
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
