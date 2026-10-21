"""One entry point for offline and private-server play. Stores paths, never tokens."""
import ctypes as C
import gzip
import base64
import json
import os
from pathlib import Path
import re
import shlex
import time
import urllib.parse

# The one community server for now; an invite code fills in everything else.
DEFAULT_SERVER = 'http://192.168.1.45:8766'
INVITE_PREFIX = 'STAR-TRADER-INVITE:'


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'star-trader/connection.json'


def load_connection():
    defaults = dict(server=DEFAULT_SERVER,token_file=str(config_path().with_name('player.token')),allow_lan=True,import_local_save=True,last_mode='')
    try:
        saved = json.loads(config_path().read_text())
        for key in defaults:
            if type(saved.get(key)) is type(defaults[key]): defaults[key] = saved[key]
    except (OSError,ValueError,AttributeError): pass
    return defaults


def save_connection(config):
    path = config_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(config,indent=2)+'\n')
    temp.chmod(0o600)
    temp.replace(path)


def make_invite(server, name, token):
    """One pasteable code holding the server and a player's token. It is a password: send it privately."""
    data = json.dumps(dict(v=1,server=server.rstrip('/'),name=name,token=token),separators=(',',':')).encode()
    return INVITE_PREFIX+base64.urlsafe_b64encode(data).decode().rstrip('=')


def read_invite(code):
    code = ''.join(code.split())
    if not code.startswith(INVITE_PREFIX): raise ValueError('That is not a Star Trader invite code.')
    try:
        raw = code[len(INVITE_PREFIX):]
        data = json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        server,name,token = data['server'],data['name'],data['token']
    except (ValueError,KeyError,TypeError): raise ValueError('The invite code is incomplete. Copy all of it and try again.') from None
    parsed = urllib.parse.urlsplit(server) if type(server) is str else None
    if not parsed or parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/'):
        raise ValueError('The invite code has an invalid server address.')
    if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',name): raise ValueError('The invite code has an invalid player name.')
    if type(token) is not str or not 20 <= len(token) <= 200 or any(c.isspace() for c in token): raise ValueError('The invite code has an invalid token.')
    return dict(server=server.rstrip('/'),name=name,token=token)


def store_account(config, server, name, token):
    token_file = config_path().with_name(name.lower()+'.token')
    token_file.parent.mkdir(parents=True,exist_ok=True)
    fd = os.open(token_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out: out.write(token+'\n')
    token_file.chmod(0o600)
    config.update(server=server,token_file=str(token_file),allow_lan=True,import_local_save=True)
    save_connection(config)


def apply_invite(config, code):
    invite = read_invite(code)
    store_account(config,invite['server'],invite['name'],invite['token'])
    return invite['name']


def migrate_online_launcher(script):
    """Read the old launcher as data; never execute shell text."""
    if config_path().exists() or not script.exists(): return False
    try:
        words = shlex.split(script.read_text().replace('\\\n',' '),comments=True)
        config = load_connection()
        for flag,key in (('--server','server'),('--token-file','token_file')):
            config[key] = os.path.expandvars(words[words.index(flag)+1])
        config['allow_lan'] = '--allow-lan' in words
        config['import_local_save'] = '--import-local-save' in words
        save_connection(config)
        return True
    except (OSError,ValueError,IndexError): return False


class StartScreen:
    def __init__(self, display, config, error=''):
        self.d,self.config,self.error = display,dict(config),error
        self.selected = 0
        self.settings = False
        self.signup = None
        # Players who last played online go straight back in unless they press something.
        ready = self.config.get('last_mode') == 'online' and self.config['server'] and Path(self.config['token_file']).expanduser().is_file()
        self.auto_at = time.monotonic()+2.5 if ready and not error else None
        self.field = 0
        self.replace_field = False
        self.texture = None
        asset = Path(__file__).resolve().parent/'assets/star-trader-splash.bmp.gz'
        try:
            raw = gzip.decompress(asset.read_bytes())
            buffer = C.create_string_buffer(raw)
            from star_trader import bind
            rw = bind(display.sdl,'SDL_RWFromConstMem',C.c_void_p,[C.c_void_p,C.c_int])(buffer,len(raw))
            surface = bind(display.sdl,'SDL_LoadBMP_RW',C.c_void_p,[C.c_void_p,C.c_int])(rw,1) if rw else None
            if surface:
                self.texture = display.texture(display.r,surface)
                display.free(surface)
        except (OSError,ValueError,EOFError): pass

    def close(self):
        if self.texture:
            self.d.destroy(self.texture)
            self.texture = None

    def activate(self, index):
        if index == 0:
            if not self.config['server']:
                self.settings = True
                self.error = 'Enter your server address and private token file path.'
                return None
            if not Path(self.config['token_file']).expanduser().is_file():
                self.open_signup('New pilot? Sign up below, or paste an invite in Connection settings.')
                return None
            return 'online'
        if index == 1: return 'offline'
        self.settings = True
        self.error = ''
        return None

    def open_signup(self, message=''):
        self.signup = dict(name='',email='')
        self.settings = False
        self.field,self.replace_field = 0,False
        self.error = message

    def submit_signup(self):
        from save_sync import signup
        name,email = self.signup['name'].strip(),self.signup['email'].strip()
        if not name: self.error = 'Choose a pilot name: letters, numbers, _ or -.'; return None
        self.error = 'Signing up...'
        self.draw()
        try:
            token = signup(self.config['server'],name,email,allow_lan=True)
            store_account(self.config,self.config['server'].rstrip('/'),name,token)
        except (RuntimeError,ValueError) as error: self.error = str(error); return None
        except OSError: self.error = 'Could not reach the server. Check your connection, or play offline.'; return None
        self.signup = None
        self.error = f'Welcome aboard, {name}! Choose Online play.'
        return None

    def form_event(self, kind, value, record, keys, limits):
        if kind == 'down':
            if value == 9: self.field = (self.field+1)%len(keys); self.replace_field = False
            elif value == 8:
                key = keys[self.field]
                record[key] = '' if self.replace_field else record[key][:-1]
                self.replace_field = False
            else: return False
            return True
        if kind == 'clipboard' and value == 'select_all': self.replace_field = True; return True
        if kind == 'text' or (kind == 'clipboard' and value == 'paste'):
            try: text = value if kind == 'text' else self.d.clipboard_text()
            except RuntimeError: self.error = 'Clipboard unavailable.'; return True
            key = keys[self.field]
            record[key] = (('' if self.replace_field else record[key])+text.replace('\n','').replace('\r',''))[:limits[self.field]]
            self.replace_field = False
            return True
        return False

    def event(self, kind, value):
        from star_trader import UP,DOWN,LEFT,RIGHT
        if kind == 'quit' or (kind == 'down' and value == 27): return 'quit'
        if kind in ('down','click','text'): self.auto_at = None
        if self.signup is not None:
            if kind == 'click':
                x,y = value
                if 70 <= x <= 1030 and 200 <= y <= 244: self.field,self.replace_field = 0,False
                elif 70 <= x <= 1030 and 295 <= y <= 339: self.field,self.replace_field = 1,False
                elif 70 <= x <= 370 and 550 <= y <= 596: return self.submit_signup()
                elif 730 <= x <= 1030 and 550 <= y <= 596: self.signup = None; self.error = ''
            elif kind == 'down' and value == 13: return self.submit_signup()
            else: self.form_event(kind,value,self.signup,('name','email'),(32,254))
            return None
        if self.settings:
            keys = ('server','token_file')
            if kind == 'click':
                x,y = value
                if 70 <= x <= 1030 and 200 <= y <= 244: self.field,self.replace_field = 0,False
                elif 70 <= x <= 1030 and 295 <= y <= 339: self.field,self.replace_field = 1,False
                elif 70 <= x <= 1030 and 380 <= y <= 414: self.config['allow_lan'] = not self.config['allow_lan']
                elif 70 <= x <= 1030 and 435 <= y <= 469: self.config['import_local_save'] = not self.config['import_local_save']
                elif 70 <= x <= 370 and 550 <= y <= 596: self.save_settings()
                elif 390 <= x <= 710 and 550 <= y <= 596: self.paste_invite()
                elif 70 <= x <= 500 and 495 <= y <= 529: self.open_signup()
                elif 730 <= x <= 1030 and 550 <= y <= 596: self.settings = False; self.error = ''
            elif kind == 'down':
                if value == 9: self.field = 1-self.field; self.replace_field = False
                elif value == 8:
                    key = keys[self.field]
                    self.config[key] = '' if self.replace_field else self.config[key][:-1]
                    self.replace_field = False
                elif value == 13: self.save_settings()
            elif kind == 'clipboard' and value == 'select_all': self.replace_field = True
            elif kind == 'text' or (kind == 'clipboard' and value == 'paste'):
                try: text = value if kind == 'text' else self.d.clipboard_text()
                except RuntimeError: self.error = 'Clipboard unavailable.'; return None
                if text.strip().startswith(INVITE_PREFIX): return self.paste_invite(text)
                key = keys[self.field]
                self.config[key] = (('' if self.replace_field else self.config[key])+text.replace('\n','').replace('\r',''))[:1024]
                self.replace_field = False
            return None
        if kind == 'down':
            if value in (UP,LEFT): self.selected = (self.selected-1)%3
            elif value in (DOWN,RIGHT,9): self.selected = (self.selected+1)%3
            elif value in (13,32): return self.activate(self.selected)
            elif value == ord('o'): return self.activate(0)
            elif value == ord('f'): return self.activate(1)
        elif kind == 'click':
            x,y = value
            for index in range(3):
                if 110+index*300 <= x <= 390+index*300 and 615 <= y <= 663:
                    self.selected = index
                    return self.activate(index)
        return None

    def paste_invite(self, code=None):
        try:
            if code is None: code = self.d.clipboard_text() or ''
            name = apply_invite(self.config,code)
        except RuntimeError: self.error = 'Clipboard unavailable.'; return None
        except ValueError as error: self.error = str(error); return None
        except OSError: self.error = 'Could not save the invite. Check folder permissions.'; return None
        self.settings = False
        self.error = f'Invite accepted: you are {name}. Choose Online play.'
        return None

    def save_settings(self):
        self.config['server'] = self.config['server'].strip().rstrip('/')
        self.config['token_file'] = str(Path(os.path.expandvars(self.config['token_file'].strip())).expanduser())
        try:
            save_connection(self.config)
            self.settings = False
            self.error = ''
        except OSError: self.error = 'Could not save connection settings.'

    def draw(self):
        from star_trader import W,H,GOLD,GREEN,RED
        d = self.d
        d.color(d.r,0,0,0,255); d.clear(d.r)
        if self.texture:
            # Fit the entire 16:9 artwork; black bars preserve its edges and title.
            width,height = C.c_int(),C.c_int()
            d.query(self.texture,None,None,C.byref(width),C.byref(height))
            scale = min(W/width.value,600/height.value)
            w,h = int(width.value*scale),int(height.value*scale)
            rect = (C.c_int*4)((W-w)//2,(600-h)//2,w,h)
            d.copy(d.r,self.texture,None,rect)
        else: d.text(420,250,'STAR TRADER',GOLD)
        if self.signup is not None:
            d.fill(40,90,1020,545,(5,15,25))
            d.text(70,110,'NEW PILOT SIGN-UP / '+self.config['server'],GOLD)
            d.text(70,155,'Pilot name (letters, numbers, _ or -). Other pilots see this name.')
            d.text(70,250,'Email for Star Trader news (optional)')
            for i,key in enumerate(('name','email')):
                y = 200+i*95
                d.rect(70,y,960,44,GOLD if self.field == i else GREEN)
                text = self.signup[key][-81:]
                if self.field == i:
                    if self.replace_field and text: d.fill(76,y+6,len(text)*11+8,32,(20,65,70))
                    d.text(80,y+10,text+('_' if int(time.monotonic()*2)%2 == 0 else ''),GOLD)
                else: d.text(80,y+10,text or ('(click to enter)' if i == 0 else '(leave blank for no news)'))
            d.text(70,380,'Your email is only used to send game news. Leave it blank to skip.')
            d.text(70,420,'Your private login is saved on this computer automatically.')
            d.text(70,495,'Click a field or TAB. Enter signs up. ESC closes.')
            for x,w,label in ((70,300,'Sign up'),(730,300,'Back')):
                d.rect(x,550,w,46,GREEN); d.text(x+15,562,label,GREEN)
        elif self.settings:
            d.fill(40,90,1020,545,(5,15,25))
            d.text(70,110,'ONLINE CONNECTION',GOLD)
            d.text(70,155,'Server address')
            d.text(70,250,'Private token FILE path — paste the path, not the token itself')
            for i,key in enumerate(('server','token_file')):
                y = 200+i*95
                d.rect(70,y,960,44,GOLD if self.field == i else GREEN)
                if self.field == i:
                    # The focused field shows its text and a blinking cursor, never the placeholder.
                    text = self.config[key][-81:]
                    if self.replace_field and text: d.fill(76,y+6,len(text)*11+8,32,(20,65,70))
                    d.text(80,y+10,text+('_' if int(time.monotonic()*2)%2 == 0 else ''),GOLD)
                else: d.text(80,y+10,self.config[key][-82:] or '(click to enter)')
            for y,key,label in ((380,'allow_lan','Allow HTTP on a trusted home network'),(435,'import_local_save','Import offline pilot only if this server account is empty')):
                d.text(70,y,('[X] ' if self.config[key] else '[ ] ')+label,GREEN)
            d.rect(70,490,430,40,GREEN); d.text(85,500,'New pilot? Sign up',GREEN)
            d.text(520,500,'Or copy an invite and Paste invite.')
            for x,w,label in ((70,300,'Save settings'),(390,320,'Paste invite'),(730,300,'Back')):
                d.rect(x,550,w,46,GREEN); d.text(x+15,562,label,GREEN)
        else:
            for index,label in enumerate(('Online play','Offline play','Connection settings')):
                x = 110+index*300
                d.rect(x,615,280,48,GOLD if index == self.selected else GREEN)
                d.text(x+15,630,label,GOLD if index == self.selected else GREEN)
            if self.auto_at: d.text(110,685,f'Connecting to online play in {max(0,self.auto_at-time.monotonic()):.0f}s - press any key to choose',GOLD)
            else: d.text(110,685,'Arrows choose / Enter opens / Click to play / ESC closes')
        if self.error: d.text(45,727,self.error[:94],GOLD if self.error.startswith(('Welcome','Invite accepted','Signing up')) else RED)
        d.present(d.r)

    def remember(self, mode):
        self.auto_at = None
        if self.config.get('last_mode') == mode: return
        self.config['last_mode'] = mode
        try: save_connection(self.config)
        except OSError: pass

    def choose(self):
        while True:
            for kind,value in self.d.events():
                choice = self.event(kind,value)
                if choice:
                    if choice in ('online','offline'): self.remember(choice)
                    return choice
            if self.auto_at and time.monotonic() >= self.auto_at:
                self.remember('online')
                return 'online'
            self.draw()
            time.sleep(1/60)
