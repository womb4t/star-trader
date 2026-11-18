"""Station market shared by every commander: stock, supply-and-demand prices and bot trader shipments.

The progress server runs one Market for everyone; the game runs its own copy when offline.
Bot traders buy a commodity where it is cheap and ship it to where it is dear. The cargo leaves
the source station when they launch and only reaches the destination when they dock, so a
trader destroyed on the way never delivers. Stations slowly produce goods back to their normal level.
"""
import math
import random
import uuid

TRADER_NAMES = ('Hullbridge', 'Drift Crow', 'Freewake', 'Lantern', 'Cobalt Mule', 'Saffron', 'Ironbark',
                'Kestrel', 'Long Haul', 'Tallow', 'Quillon', 'Brass Heron')
TRADE_INTERVAL = (8, 16)    # seconds between bot trades somewhere in the galaxy
MAX_CATCH_UP = 400          # bot steps simulated after the market has been idle
MAX_SHIPMENTS = 40
MAX_OPS = 50                # player stock changes accepted per request


def demand_factor(stock, normal):
    """Scarce goods cost more and gluts sell cheap: 1.5x when sold out, 1x at normal stock, 0.75x at 1.5x normal."""
    ratio = stock/max(1, normal)
    return max(.75, min(1.5, 1+.5*(1-ratio)))


class Market:
    def __init__(self, normal, static_price, travel_time, state=None, seed=None):
        """normal: normal stock per [system][good]; static_price(system, good) before supply and demand;
        travel_time(source, dest) in seconds."""
        self.normal, self.static_price, self.travel_time = normal, static_price, travel_time
        self.state = state or dict(stock=[row[:] for row in normal], shipments=[], next_trade=None, seq=0,
                                   seed=seed if seed is not None else uuid.uuid4().hex)

    @property
    def stock(self):
        return self.state['stock']

    def cap(self, system, good):
        return 3*self.normal[system][good]+10

    def price(self, system, good):
        return self.static_price(system, good)*demand_factor(self.stock[system][good], self.normal[system][good])

    def advance(self, now):
        state = self.state
        if state['next_trade'] is None: state['next_trade'] = now
        # After a long idle spell, simulate only the most recent stretch.
        earliest = now-MAX_CATCH_UP*sum(TRADE_INTERVAL)/2
        if state['next_trade'] < earliest: state['next_trade'] = earliest
        while state['next_trade'] <= now:
            t = state['next_trade']
            self.deliver(t)
            rng = random.Random(f"{state['seed']}:{state['seq']}")
            state['seq'] += 1
            self.restock(rng)
            self.bot_trade(rng, t)
            state['next_trade'] = t+rng.uniform(*TRADE_INTERVAL)
        self.deliver(now)

    def deliver(self, now):
        for shipment in [s for s in self.state['shipments'] if s['arrive'] <= now]:
            self.state['shipments'].remove(shipment)
            dest, good = shipment['dest'], shipment['good']
            self.stock[dest][good] = min(self.cap(dest, good), self.stock[dest][good]+shipment['n'])

    def restock(self, rng):
        """Stations produce: a random line below its normal level gains a little."""
        system, good = rng.randrange(len(self.stock)), rng.randrange(len(self.stock[0]))
        if self.stock[system][good] < self.normal[system][good]: self.stock[system][good] += rng.randint(1, 2)

    def bot_trade(self, rng, now):
        if len(self.state['shipments']) >= MAX_SHIPMENTS: return None
        systems = list(range(len(self.stock)))
        good = rng.randrange(len(self.stock[0]))
        offers = rng.sample(systems, 4)
        sources = [s for s in offers if self.stock[s][good] >= 2]
        if not sources: return None
        source = min(sources, key=lambda s: self.price(s, good))
        dest = max((s for s in offers if s != source), key=lambda s: self.price(s, good))
        if self.price(dest, good) < self.price(source, good)*1.08: return None  # no margin worth the trip
        n = min(self.stock[source][good]//2, rng.randint(1, 2) if self.normal[source][good] <= 6 else rng.randint(2, 6))
        if n <= 0: return None
        self.stock[source][good] -= n
        shipment = dict(id=f"{self.state['seed'][:8]}-{self.state['seq']}", name=rng.choice(TRADER_NAMES),
                        source=source, dest=dest, good=good, n=n, depart=now, arrive=now+self.travel_time(source, dest))
        self.state['shipments'].append(shipment)
        return shipment

    def apply(self, trades=(), intercepts=()):
        """Player activity: stock changes from buying and selling, and traders destroyed in flight."""
        for system, good, delta in list(trades)[:MAX_OPS]:
            if type(system) is not int or type(good) is not int or type(delta) is not int: raise ValueError('Invalid trade')
            if not (0 <= system < len(self.stock) and 0 <= good < len(self.stock[0]) and -10 <= delta <= 10): raise ValueError('Invalid trade')
            self.stock[system][good] = max(0, min(self.cap(system, good), self.stock[system][good]+delta))
        lost = set(i for i in list(intercepts)[:10] if type(i) is str)
        self.state['shipments'] = [s for s in self.state['shipments'] if s['id'] not in lost]

    def snapshot(self, now):
        return dict(protocol=1, now=now, stock=[row[:] for row in self.stock],
                    shipments=[dict(s) for s in self.state['shipments']])


class MarketClient:
    """Keeps the game's copy of the shared market in step with the server, in the background."""
    def __init__(self, remote, interval=3):
        import threading
        self.remote, self.interval = remote, interval
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.trades, self.intercepts = [], []
        self.fresh = None
        self.status = 'Market: connecting'
        self.thread = threading.Thread(target=self.run, name='market', daemon=True)
        self.thread.start()

    def queue_trade(self, system, good, delta):
        with self.lock: self.trades.append([system, good, delta])

    def intercept(self, shipment_id):
        with self.lock: self.intercepts.append(shipment_id)

    def take(self):
        """The newest snapshot (once), with stock changes not yet sent re-applied on top."""
        with self.lock:
            snap, self.fresh = self.fresh, None
            if snap is None: return None
            for system, good, delta in self.trades: snap['stock'][system][good] = max(0, snap['stock'][system][good]+delta)
            lost = set(self.intercepts)
            snap['shipments'] = [s for s in snap['shipments'] if s['id'] not in lost]
            return snap

    def run(self):
        while not self.stop.is_set():
            with self.lock:
                trades, intercepts = self.trades[:MAX_OPS], self.intercepts[:10]
            try:
                snap = self.remote.request(dict(trades=trades, intercepts=intercepts), endpoint='/v1/market')
                if snap.get('protocol') != 1 or type(snap.get('stock')) is not list or type(snap.get('shipments')) is not list: raise ValueError('Invalid market')
                with self.lock:
                    del self.trades[:len(trades)]
                    del self.intercepts[:len(intercepts)]
                    self.fresh = snap
                self.status = 'Market: shared'
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                self.status = 'Market: offline, using local prices'
            self.stop.wait(self.interval)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=6)
