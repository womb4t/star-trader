"""First shared-universe test stage: authenticated live player presence, not PvP authority."""
import math
import threading
import time
import uuid


class PresenceBusy(RuntimeError): pass


class SharedPresence:
    def __init__(self):
        self.lock = threading.Lock()
        self.players = {}

    def exchange(self, player_id, name, data):
        if type(data) is not dict: raise ValueError('Presence object required')
        system,mode = data.get('system'),data.get('mode')
        session,sequence,epoch = data.get('session'),data.get('sequence'),data.get('epoch')
        if type(system) is not int or not 0 <= system < 8: raise ValueError('Unknown system')
        if mode not in ('flight','docked','transit','deep-space','destroyed'): raise ValueError('Unknown mode')
        if any(type(v) is not str or len(v) != 32 or any(c not in '0123456789abcdef' for c in v) for v in (session,epoch)): raise ValueError('Invalid session')
        if type(sequence) is not int or sequence < 0: raise ValueError('Invalid sequence')
        position,velocity = data.get('position'),data.get('velocity')
        for vector,limit in ((position,1000000),(velocity,400)):
            if type(vector) is not list or len(vector) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector): raise ValueError('Invalid vector')
            if math.sqrt(sum(v*v for v in vector)) > limit: raise ValueError('Vector outside testing limits')
        now = time.monotonic()
        with self.lock:
            old = self.players.get(player_id)
            if old and now-old['seen'] < 10:
                if old['session'] != session: raise PresenceBusy('This player is already online on another computer')
                if sequence <= old['sequence']: raise ValueError('Out of order update')
                if old['system'] == system and old['epoch'] == epoch and old['mode'] == mode == 'flight':
                    maximum = (now-old['seen'])*400+100
                    if math.dist(position,old['position']) > maximum: raise ValueError('Movement update too large')
            self.players[player_id] = dict(id=player_id,name=name,system=system,mode=mode,
                position=list(position),velocity=list(velocity) if mode == 'flight' else [0.,0.,0.],
                session=session,sequence=sequence,epoch=epoch,seen=now)
            self.players = {key:value for key,value in self.players.items() if now-value['seen'] < 10}
            public = []
            for player in self.players.values():
                item = {key:player[key] for key in ('id','name','system','mode','position','velocity')}
                age = min(.75,max(0,now-player['seen']))
                item['position'] = [p+v*age for p,v in zip(player['position'],player['velocity'])]
                public.append(item)
            return dict(protocol=1,you=player_id,players=public)


class PresenceClient:
    def __init__(self, remote):
        self.remote = remote
        self.session = uuid.uuid4().hex
        self.sequence = 0
        self.snapshot = dict(players=[],you=None)
        self.status = 'Universe: connecting'
        self.pending = None
        self.condition = threading.Condition()
        self.stopping = False
        self.thread = threading.Thread(target=self.run,name='shared-presence',daemon=True)
        self.thread.start()

    def offer(self, state):
        with self.condition:
            self.pending = state
            self.condition.notify()

    def run(self):
        next_send = 0
        while True:
            with self.condition:
                while not self.stopping and (self.pending is None or time.monotonic() < next_send):
                    self.condition.wait(max(.02,next_send-time.monotonic()) if self.pending else None)
                if self.stopping: return
                state,self.pending = self.pending,None
            self.sequence += 1
            state = dict(state,session=self.session,sequence=self.sequence)
            try:
                result = self.remote.request(state,endpoint='/v1/presence')
                if result.get('protocol') != 1 or type(result.get('players')) is not list or len(result['players']) > 8: raise ValueError('Invalid presence response')
                self.snapshot = result
                self.status = f'Universe: {len(result["players"])}/8 players connected'
            except (OSError,RuntimeError,ValueError,KeyError):
                self.snapshot = dict(players=[],you=None)
                self.status = 'Universe unavailable — check server update/connection'
            next_send = time.monotonic()+.25

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify()
        self.thread.join(timeout=6)
