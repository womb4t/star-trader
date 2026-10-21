#!/usr/bin/env python3
"""Private testing progress server. No graphics or third-party Python packages required."""
import argparse
from contextlib import contextmanager
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl
import time
import urllib.parse
from star_trader import VERSION
from presence import SharedPresence, PresenceBusy

MAX_SAVE = 256 * 1024
MAX_PLAYERS = 8
EMAIL = re.compile(r'[^@\s]{1,64}@[^@\s]+\.[^@\s]+')


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def validate_save(data):
    def walk(value, depth=0):
        if depth > 14: raise ValueError('Save nesting too deep')
        if value is None or type(value) in (str, bool): return
        if type(value) in (int, float):
            if not math.isfinite(value): raise ValueError('Non-finite number')
        elif type(value) is list:
            if len(value) > 1000: raise ValueError('List too large')
            for item in value: walk(item, depth+1)
        elif type(value) is dict:
            if len(value) > 200: raise ValueError('Object too large')
            for item in value.values(): walk(item, depth+1)
        else: raise ValueError('Unsupported save value')
    walk(data)
    if type(data) is not dict or not {'credits','cargo','system','fuel','hull','kills','commander_id'} <= data.keys():
        raise ValueError('Missing pilot data')
    from star_trader import Pilot
    pilot = Pilot()
    for key in vars(pilot):
        if key in data: setattr(pilot, key, data[key])
    pilot.validate()
    session = data.get('_session')
    if session is not None:
        if type(session) is not dict or session.get('schema') != 1 or session.get('commander') != pilot.commander_id:
            raise ValueError('Invalid session identity')
        if session.get('mode') not in ('market','flight','cruise','hyperspace','dead') or type(session.get('state')) is not dict:
            raise ValueError('Invalid session state')
    if len(encode(data)) > MAX_SAVE: raise ValueError('Save too large')


class NameTaken(ValueError):
    pass


class PlayerLimit(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0, save TEXT, updated REAL);
                CREATE TABLE IF NOT EXISTS history (
                player INTEGER, revision INTEGER, save TEXT, updated REAL,
                PRIMARY KEY(player, revision));''')
            # Added for sign-up: an optional email, kept only for players who ask for game news.
            columns = {row[1] for row in db.execute('PRAGMA table_info(players)')}
            if 'email' not in columns: db.execute('ALTER TABLE players ADD COLUMN email TEXT')
            if 'created' not in columns: db.execute('ALTER TABLE players ADD COLUMN created REAL')
            db.executescript('''CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY, player TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
                details TEXT NOT NULL, created REAL, received REAL NOT NULL, status TEXT NOT NULL DEFAULT 'new');
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);''')
        os.chmod(path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db: yield db
        finally: db.close()

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def create_player(self, name, token, email=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', name): raise ValueError('Name: 1–32 letters, numbers, _ or -')
        if email is not None:
            email = email.strip().lower()
            if not email: email = None
            elif len(email) > 254 or not EMAIL.fullmatch(email): raise ValueError('That email address does not look right.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM players').fetchone()[0] >= MAX_PLAYERS: raise PlayerLimit('All pilot places on this server are taken.')
            if db.execute('SELECT 1 FROM players WHERE lower(name)=lower(?)',(name,)).fetchone(): raise NameTaken('That pilot name is taken. Choose another.')
            db.execute('INSERT INTO players(name,token_hash,email,created) VALUES (?,?,?,?)', (name,self.token_hash(token),email,time.time()))

    def add_feedback(self, player, entry):
        if type(entry) is not dict: raise ValueError('Invalid feedback')
        if type(entry.get('id')) is not str or not re.fullmatch(r'[0-9a-f]{32}',entry['id']): raise ValueError('Invalid feedback id')
        if entry.get('kind') not in ('bug','suggestion'): raise ValueError('Invalid feedback kind')
        text = entry.get('text')
        if type(text) is not str or not text.strip() or len(text) > 1500: raise ValueError('Invalid feedback text')
        details = {key:entry[key] for key in ('version','platform','screen','system') if type(entry.get(key)) is str and len(entry[key]) <= 60}
        created = entry.get('created') if type(entry.get('created')) in (int,float) and math.isfinite(entry['created']) else None
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM feedback WHERE player=? AND received>?',(player,now-86400)).fetchone()[0] >= 50:
                raise ValueError('Feedback limit reached for today')
            # The client's id makes a resend after a lost reply harmless.
            db.execute('INSERT OR IGNORE INTO feedback(id,player,kind,text,details,created,received) VALUES (?,?,?,?,?,?,?)',
                       (entry['id'],player,entry['kind'],text.strip(),encode(details).decode(),created,now))

    def feedback(self, status=None):
        with self.connect() as db:
            rows = db.execute('SELECT id,player,kind,text,details,created,received,status FROM feedback'
                              +(' WHERE status=?' if status else '')+' ORDER BY received',(status,) if status else ()).fetchall()
        return [dict(id=r[0],player=r[1],kind=r[2],text=r[3],details=json.loads(r[4]),created=r[5],received=r[6],status=r[7]) for r in rows]

    def set_feedback_status(self, feedback_id, status):
        if status not in ('new','seen','done'): raise ValueError('Status must be new, seen or done')
        with self.connect() as db:
            return db.execute('UPDATE feedback SET status=? WHERE id=?',(status,feedback_id)).rowcount

    def set_admin_token(self, token):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('admin_token_hash',?)",(self.token_hash(token),))

    def is_admin(self, token):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='admin_token_hash'").fetchone()
        return row is not None and secrets.compare_digest(row[0],self.token_hash(token))

    def news_list(self):
        with self.connect() as db:
            return db.execute('SELECT name,email FROM players WHERE email IS NOT NULL ORDER BY name').fetchall()

    def remove_email(self, email):
        with self.connect() as db:
            return db.execute('UPDATE players SET email=NULL WHERE email=?',(email.strip().lower(),)).rowcount

    def read(self, token):
        with self.connect() as db:
            row = db.execute('SELECT name,revision,save FROM players WHERE token_hash=?',(self.token_hash(token),)).fetchone()
        if row is None: raise PermissionError('Invalid token')
        return dict(player=row[0], revision=row[1], save=json.loads(row[2]) if row[2] else None)

    def write(self, token, revision, data):
        validate_save(data)
        payload = encode(data).decode()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,revision,save FROM players WHERE token_hash=?',(self.token_hash(token),)).fetchone()
            if row is None: raise PermissionError('Invalid token')
            player, current, old = row
            if old == payload: return current  # A lost response can safely be retried.
            if revision != current: return None
            now = time.time()
            db.execute('UPDATE players SET revision=?,save=?,updated=? WHERE id=?',(current+1,payload,now,player))
            db.execute('INSERT INTO history VALUES (?,?,?,?)',(player,current+1,payload,now))
            db.execute('DELETE FROM history WHERE player=? AND revision<=?',(player,current+1-20))
            return current+1


class Handler(BaseHTTPRequestHandler):
    server_version = 'StarTraderSave/1'
    def log_message(self, fmt, *args):
        pass  # Do not log credentials or save contents.

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def reply(self, status, value):
        raw = encode(value)
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

    def token(self):
        auth = self.headers.get('Authorization','')
        if not auth.startswith('Bearer ') or not 20 <= len(auth[7:]) <= 200: raise PermissionError('Token required')
        return auth[7:]

    def do_GET(self):
        try:
            if self.path == '/health': return self.reply(200,dict(service='star-trader-saves',protocol=1,version=VERSION))
            if self.path.startswith('/v1/admin/feedback'):
                if not self.server.store.is_admin(self.token()): raise PermissionError('Admin only')
                status = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('status',[None])[0]
                return self.reply(200,dict(feedback=self.server.store.feedback(status)))
            if self.path != '/v1/save': return self.reply(404,dict(error='Not found'))
            self.reply(200,self.server.store.read(self.token()))
        except PermissionError: self.reply(401,dict(error='Invalid or missing player token'))

    def do_POST(self):
        try:
            if self.path == '/v1/admin/feedback/status':
                if not self.server.store.is_admin(self.token()): raise PermissionError('Admin only')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096: return self.reply(413,dict(error='Request too large or empty'))
                data = json.loads(self.rfile.read(length))
                if type(data) is not dict or type(data.get('ids')) is not list or not all(type(i) is str for i in data['ids']): raise ValueError('Invalid request')
                changed = sum(self.server.store.set_feedback_status(i,data.get('status')) for i in data['ids'][:200])
                return self.reply(200,dict(changed=changed))
            if self.path != '/v1/signup': return self.reply(404,dict(error='Not found'))
            if not self.server.signup: return self.reply(403,dict(error='Sign-up is closed on this server. Ask the host for an invite.'))
            if self.server.signup == 'lan' and not home_network(self.client_address[0]):
                # Internet visitors (including Tailscale Funnel, which arrives via loopback) need an invite.
                return self.reply(403,dict(error='Sign-up is only open on the host\'s home network. Ask the host for an invite code.'))
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 2048: return self.reply(413,dict(error='Request too large or empty'))
            data = json.loads(self.rfile.read(length))
            if type(data) is not dict or type(data.get('name')) is not str or type(data.get('email','')) not in (str,type(None)): raise ValueError('Invalid sign-up')
            token = secrets.token_urlsafe(32)
            self.server.store.create_player(data['name'],token,data.get('email'))
            self.reply(201,dict(player=data['name'],token=token))
        except PermissionError: self.reply(401,dict(error='Invalid or missing admin token'))
        except NameTaken as error: self.reply(409,dict(error=str(error)))
        except PlayerLimit as error: self.reply(403,dict(error=str(error)))
        except ValueError as error: self.reply(400,dict(error=str(error) if str(error)[:1].isupper() else 'Invalid sign-up'))
        except (KeyError,TypeError,AttributeError,RecursionError): self.reply(400,dict(error='Invalid sign-up'))
        except sqlite3.Error: self.reply(503,dict(error='Server storage temporarily unavailable'))

    def do_PUT(self):
        try:
            if self.path not in ('/v1/save','/v1/presence','/v1/feedback'): return self.reply(404,dict(error='Not found'))
            token = self.token()
            self.server.store.read(token)
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= MAX_SAVE+1024: return self.reply(413,dict(error='Save too large or empty'))
            data = json.loads(self.rfile.read(length))
            if self.path == '/v1/feedback':
                self.server.store.add_feedback(self.server.store.read(token)['player'],data)
                return self.reply(201,dict(received=data['id']))
            if self.path == '/v1/presence':
                with self.server.store.connect() as db:
                    player_id,name = db.execute('SELECT id,name FROM players WHERE token_hash=?',(self.server.store.token_hash(token),)).fetchone()
                return self.reply(200,self.server.presence.exchange(player_id,name,data))
            if type(data) is not dict or type(data.get('revision')) is not int or data['revision'] < 0: raise ValueError('Invalid revision')
            revision = self.server.store.write(token,data['revision'],data['save'])
            if revision is None: return self.reply(409,dict(error='A newer save exists. Reconnect to resolve the conflict.'))
            self.reply(200,dict(revision=revision))
        except PermissionError: self.reply(401,dict(error='Invalid or missing player token'))
        except PresenceBusy: self.reply(409,dict(error='This player is already online on another computer'))
        except (ValueError,KeyError,TypeError,AttributeError,OverflowError,RecursionError): self.reply(400,dict(error='Invalid save'))
        except sqlite3.Error: self.reply(503,dict(error='Save storage temporarily unavailable'))


def home_network(address):
    try: ip = ipaddress.ip_address(address)
    except ValueError: return False
    if getattr(ip,'ipv4_mapped',None): ip = ip.ipv4_mapped
    return ip.is_private and not ip.is_loopback and ip not in ipaddress.ip_network('100.64.0.0/10')


def make_server(store, host='127.0.0.1', port=8765, signup='lan'):
    server = ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads = True
    server.signup = signup
    server.store = store
    server.presence = SharedPresence()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',action='version',version=VERSION)
    parser.add_argument('--db',type=Path,default=Path.home()/'.star-trader-server/progress.sqlite3')
    sub = parser.add_subparsers(dest='command',required=True)
    create = sub.add_parser('create-player')
    create.add_argument('name')
    create.add_argument('--token-file',type=Path,required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--host',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=8765)
    serve.add_argument('--lan',action='store_true',help='Allow unencrypted private-LAN testing')
    serve.add_argument('--cert',type=Path)
    serve.add_argument('--key',type=Path)
    serve.add_argument('--no-signup',action='store_true',help='Only admin-created players and invites; no in-game sign-up')
    serve.add_argument('--public-signup',action='store_true',help='Allow in-game sign-up from the internet too (default: home network only)')
    sub.add_parser('news-list',help='Print name and email of players who asked for game news')
    listing = sub.add_parser('feedback-list',help='Print bug reports and suggestions')
    listing.add_argument('--status',choices=('new','seen','done'))
    mark = sub.add_parser('feedback-mark',help='Set a report to new, seen or done')
    mark.add_argument('id'); mark.add_argument('status',choices=('new','seen','done'))
    admin = sub.add_parser('admin-token',help='Create (or replace) the admin key used to read feedback remotely')
    admin.add_argument('--token-file',type=Path,required=True)
    remove = sub.add_parser('news-remove',help='Stop game news to an email address and forget it')
    remove.add_argument('email')
    invite = sub.add_parser('invite',help='Write an invite code file for a player to paste into Connection settings')
    invite.add_argument('--server',required=True,help='Address players use, e.g. http://192.168.1.45:8766')
    invite.add_argument('--token-file',type=Path,required=True)
    invite.add_argument('--out',type=Path,required=True)
    backup = sub.add_parser('backup')
    backup.add_argument('destination',type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    store = Store(args.db)
    if args.command == 'create-player':
        token = secrets.token_urlsafe(32)
        args.token_file.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation prevents overwriting another player's credential.
        with args.token_file.open('x') as out:
            try: store.create_player(args.name,token)
            except Exception:
                args.token_file.unlink()
                raise
            out.write(token+'\n')
        print(f'Created {args.name}. Private token file: {args.token_file}. Keep it private.')
    elif args.command == 'invite':
        from startup import make_invite
        token = args.token_file.read_text().strip()
        name = store.read(token)['player']
        with args.out.open('x') as out: out.write(make_invite(args.server,name,token)+'\n')
        print(f'Invite for {name} written to {args.out}. It works like a password: send it privately, then delete it.')
    elif args.command == 'feedback-list':
        for item in store.feedback(args.status):
            when = time.strftime('%Y-%m-%d %H:%M',time.localtime(item['received']))
            print(f"[{item['status']}] {item['id'][:8]} {when} {item['player']} {item['kind'].upper()}: {item['text']}")
    elif args.command == 'feedback-mark':
        matches = [i['id'] for i in store.feedback() if i['id'].startswith(args.id)]
        if len(matches) != 1: parser.error('Give a unique report id (or its first characters)')
        store.set_feedback_status(matches[0],args.status)
        print(f'Marked {matches[0][:8]} {args.status}.')
    elif args.command == 'admin-token':
        token = secrets.token_urlsafe(32)
        args.token_file.parent.mkdir(parents=True,exist_ok=True)
        with args.token_file.open('w') as out: out.write(token+'\n')
        args.token_file.chmod(0o600)
        store.set_admin_token(token)
        print(f'Admin key written to {args.token_file}. Keep it private; it can read all feedback.')
    elif args.command == 'news-list':
        for name,email in store.news_list(): print(f'{name}\t{email}')
    elif args.command == 'news-remove':
        print(f'Removed {store.remove_email(args.email)} address(es).')
    elif args.command == 'backup':
        if args.destination.resolve() == args.db.resolve() or args.destination.exists(): parser.error('Choose a new backup file')
        with store.connect() as source:
            target = sqlite3.connect(args.destination)
            try: source.backup(target)
            finally: target.close()
        print(f'Backup saved to {args.destination}')
    else:
        if bool(args.cert) != bool(args.key): parser.error('--cert and --key must be used together')
        if args.host not in ('127.0.0.1','localhost','::1') and not (args.lan or args.cert): parser.error('Use --lan for private network testing or configure --cert and --key')
        if args.no_signup and args.public_signup: parser.error('Choose --no-signup or --public-signup')
        server = make_server(store,args.host,args.port,signup=False if args.no_signup else True if args.public_signup else 'lan')
        if args.cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(args.cert,args.key)
            server.socket = context.wrap_socket(server.socket,server_side=True)
        print(f'Star Trader progress server listening on {args.host}:{args.port}. Ctrl+C stops it.',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()


if __name__ == '__main__':
    main()
