"""Optional private progress sync; offline saves remain independent."""
import hashlib
import ipaddress
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class Conflict(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a player's bearer credential to a redirect target.


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_bytes(data)
    temp.chmod(0o600)
    temp.replace(path)


def check_server(url, allow_lan=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Server must be an http(s) origin, e.g. http://192.168.1.20:8765')
    if parsed.scheme == 'http':
        try:
            address = ipaddress.ip_address(parsed.hostname)
            permitted = address.is_loopback or (allow_lan and (address in ipaddress.ip_network('192.168.0.0/16') or address in ipaddress.ip_network('10.0.0.0/8') or address in ipaddress.ip_network('172.16.0.0/12')))
        except ValueError:
            permitted = parsed.hostname == 'localhost' or (allow_lan and parsed.hostname.endswith('.local'))
        if not permitted: raise ValueError('HTTP is limited to localhost or --allow-lan private addresses; use HTTPS elsewhere')
    return url.rstrip('/')


def signup(url, name, email='', allow_lan=False):
    """Create a pilot account on the server and return its new private token."""
    url = check_server(url,allow_lan)
    raw = canonical(dict(name=name.strip(),email=email.strip() or None))
    req = urllib.request.Request(url+'/v1/signup',data=raw,method='POST',headers={'Content-Type':'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(req,timeout=8) as response: data = json.loads(response.read(4096))
    except urllib.error.HTTPError as error:
        try: message = json.loads(error.read(4096)).get('error')
        except (ValueError,AttributeError): message = None
        error.close()
        raise RuntimeError(message if type(message) is str else f'Server returned HTTP {error.code}') from None
    token = data.get('token') if type(data) is dict else None
    if type(token) is not str or not 20 <= len(token) <= 200 or any(c.isspace() for c in token): raise RuntimeError('Server sent an invalid sign-up reply')
    return token


class RemoteSave:
    def __init__(self, url, token_file, root, allow_lan=False):
        self.url = check_server(url,allow_lan)
        self.token = Path(token_file).read_text().strip()
        if not 20 <= len(self.token) <= 200 or any(c.isspace() for c in self.token): raise ValueError('Invalid token file')
        # The slot follows the login, not the address, so a server that changes IP keeps your progress.
        slot = digest(('account\n'+self.token).encode())[:24]
        legacy = Path(root)/'servers'/digest((self.url+'\n'+self.token).encode())[:24]
        if legacy.is_dir() and not (Path(root)/'servers'/slot).exists(): legacy.rename(Path(root)/'servers'/slot)
        self.save_path = Path(root)/'servers'/slot/'save.json'
        self.meta_path = self.save_path.with_name('sync.json')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.revision = 0
        self.player_name = None
        self.status = 'Server: connecting'
        self.pending = None
        self.condition = threading.Condition()
        self.stopping = False
        self.conflicted = False
        self.thread = None

    def request(self, data=None, endpoint='/v1/save'):
        raw = canonical(data) if data is not None else None
        req = urllib.request.Request(self.url+endpoint,data=raw,method='PUT' if raw else 'GET',headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=5) as response:
                raw = response.read(300000)
                if len(raw) >= 300000: raise ValueError('Server response too large')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            error.close()
            if error.code == 409 and endpoint != '/v1/save': raise RuntimeError('This player is already online on another computer') from None
            if error.code == 409: raise Conflict('Server save changed on another computer. Local progress retained; reconnect to resolve.') from None
            if error.code == 401: raise RuntimeError('Server rejected the player token') from None
            raise RuntimeError(f'Server returned HTTP {error.code}') from None

    def metadata(self, saved_hash):
        atomic(self.meta_path,canonical(dict(revision=self.revision,hash=saved_hash)))

    def prepare(self, import_path=None, restore=False, offline=False):
        meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else None
        local = json.loads(self.save_path.read_text()) if self.save_path.exists() else None
        try: remote = self.request()
        except (OSError,RuntimeError,ValueError):
            if not offline or local is None or meta is None: raise
            self.revision = meta['revision']
            self.status = 'Server: unavailable; saving locally, retrying'
            return
        self.revision = remote['revision']
        if type(remote.get('player')) is str and 0 < len(remote['player']) <= 32: self.player_name = remote['player']
        remote_save = remote['save']
        local_hash = digest(canonical(local)) if local is not None else None
        remote_hash = digest(canonical(remote_save)) if remote_save is not None else None
        if local is not None and not restore:
            if local_hash == remote_hash:
                self.metadata(local_hash)
            elif meta is None or (meta['revision'] != self.revision and local_hash != meta['hash']):
                raise Conflict('Local and server saves differ. Local progress is untouched. Use --restore-server-save to back up the local copy and load the server save.')
            elif meta['revision'] == self.revision:
                self.status = 'Server: local progress waiting to upload'
                return
        if restore and local is not None:
            backup = self.save_path.with_name(f'save.before-restore-{time.time_ns()}.json')
            atomic(backup,self.save_path.read_bytes())
        if remote_save is not None:
            atomic(self.save_path,canonical(remote_save))
            self.metadata(remote_hash)
        elif local is not None and not restore:
            # Known unsynced local progress against an unchanged server revision.
            return
        else:
            if restore and self.save_path.exists(): self.save_path.unlink()
            if import_path is not None and Path(import_path).exists():
                atomic(self.save_path,Path(import_path).read_bytes())
            self.metadata(None)
        self.status = 'Server: connected'

    def start(self):
        self.thread = threading.Thread(target=self.run,name='save-sync',daemon=True)
        self.thread.start()

    def offer(self, data):
        with self.condition:
            self.pending = json.loads(canonical(data))
            self.condition.notify()

    def run(self):
        next_attempt = 0
        while True:
            with self.condition:
                while not self.stopping and (self.pending is None or time.monotonic() < next_attempt):
                    self.condition.wait(max(.05,next_attempt-time.monotonic()) if self.pending else None)
                if self.conflicted: return
                data = self.pending
                if data is None and self.stopping: return
                self.pending = None
            try:
                response = self.request(dict(revision=self.revision,save=data))
                self.revision = response['revision']
                self.metadata(digest(canonical(data)))
                self.status = 'Server: progress saved'
            except Conflict:
                self.conflicted = True
                self.status = 'Server: CONFLICT — local save retained; reconnect'
                return
            except (OSError,RuntimeError,ValueError,KeyError):
                self.status = 'Server: unavailable — progress saved locally'
                with self.condition:
                    if self.pending is None: self.pending = data
                    if self.stopping: return
            next_attempt = time.monotonic()+5
            if self.stopping:
                next_attempt = 0

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify()
        if self.thread: self.thread.join(timeout=7)


class FeedbackUploader:
    """Sends logged bug reports and suggestions, oldest first, deleting each once the server has it."""
    def __init__(self, remote, outbox, interval=30):
        self.remote,self.outbox,self.interval = remote,Path(outbox),interval
        self.stop = threading.Event()
        self.thread = None
        self.sent = 0

    def start(self):
        self.thread = threading.Thread(target=self.run,name='feedback',daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            self.send_all()
            self.stop.wait(self.interval)

    def send_all(self):
        try: paths = sorted(self.outbox.glob('*.json'),key=lambda path:path.stat().st_mtime)
        except OSError: return
        for path in paths:
            if self.stop.is_set(): return
            try: entry = json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):
                try: path.rename(path.with_suffix('.unreadable'))
                except OSError: pass
                continue
            try: self.remote.request(entry,endpoint='/v1/feedback')
            except RuntimeError as error:
                if 'HTTP 400' in str(error):
                    # The server rejected this entry outright; keep it aside rather than retrying forever.
                    try: path.rename(path.with_suffix('.rejected'))
                    except OSError: pass
                    continue
                return
            except (OSError,ValueError): return
            try: path.unlink()
            except OSError: pass
            self.sent += 1

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=7)
