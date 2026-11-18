"""Station market shared by every commander: stock, supply-and-demand prices and bot trader shipments.

The progress server runs one Market for everyone; the game runs its own copy when offline.
Bot traders buy a commodity where it is cheap and ship it to where it is dear. The cargo leaves
the source station when they launch and only reaches the destination when they dock, so a
trader destroyed on the way never delivers. Between trades every station's people consume and its
factories produce (economy.py), faster the more ships use it.
"""
import math
import random
import uuid

from economy import Economy

TRADER_NAMES = ('Hullbridge', 'Drift Crow', 'Freewake', 'Lantern', 'Cobalt Mule', 'Saffron', 'Ironbark',
                'Kestrel', 'Long Haul', 'Tallow', 'Quillon', 'Brass Heron')
TRADE_INTERVAL = (8, 16)    # seconds between bot trades somewhere in the galaxy
MAX_CATCH_UP = 400          # bot steps simulated after the market has been idle
MAX_SHIPMENTS = 40
MAX_OPS = 50                # player stock changes accepted per request
# Bots only haul when the gap is wide, so they smooth extremes but leave margins for commanders.
BOT_MARGIN = 1.6


def demand_factor(stock, normal):
    """Scarce goods cost more and gluts sell cheap: 1.5x when sold out, 1x at normal stock, 0.75x at 1.5x normal."""
    ratio = stock/max(1, normal)
    return max(.75, min(1.5, 1+.5*(1-ratio)))


class Market:
    def __init__(self, normal, static_price, travel_time, state=None, seed=None, profiles=None):
        """normal: normal stock per [system][good]; static_price(system, good) before supply and demand;
        travel_time(source, dest) in seconds; profiles: economy, government and population per system."""
        self.normal, self.static_price, self.travel_time = normal, static_price, travel_time
        self.state = state or dict(stock=[row[:] for row in normal], shipments=[], next_trade=None, seq=0,
                                   seed=seed if seed is not None else uuid.uuid4().hex)
        # Whole-number stock is what commanders trade; `levels` keeps the fractions slow flows add up to.
        if 'levels' not in self.state: self.state['levels'] = [[float(n) for n in row] for row in self.stock]
        self.profiles = profiles
        self.economy = Economy(profiles, normal, self.state) if profiles else None

    @property
    def stock(self):
        return self.state['stock']

    @property
    def levels(self):
        return self.state['levels']

    def cap(self, system, good):
        return 3*self.normal[system][good]*self.depth(system)+10

    def pay_tax(self, system, value):
        council = self.state.get('council')
        if council:
            tax, share = value*self.tax(system), council.get('house_share', 0.)
            council['treasury'] = council.get('treasury', 0.)+tax*(1-share)
            council['revenue'] = council.get('revenue', 0.)+tax*(1-share)
            council['house'] = council.get('house', 0.)+tax*share

    def tax(self, system):
        """The station's trade tax (set by the Galactic Council in the adaptive economy; none otherwise)."""
        return self.state.get('council', {}).get('tax', {}).get(str(system), 0.)

    def price(self, system, good):
        base = self.static_price(system, good)
        # Adaptive economy (prototype): legal goods are priced from what the station makes and uses.
        if self.economy and getattr(self, 'adaptive_base', None) and good not in getattr(self, 'contraband', ()):
            from economy import ADAPTIVE
            if ADAPTIVE: base = self.adaptive_base(system, good)*self.economy.price_adjust(system, good)
        return base*demand_factor(self.stock[system][good], self.normal[system][good]*self.depth(system))

    def depth(self, system):
        return self.economy.depth(system) if self.economy else 1.

    def reconcile(self):
        """Whole-number stock changed directly (a trade in the game) carries over into the levels."""
        for row, levels in zip(self.stock, self.levels):
            for g, n in enumerate(row):
                if n != round(levels[g]): levels[g] += n-round(levels[g])

    def sync(self):
        for row, levels in zip(self.stock, self.levels):
            row[:] = [round(level) for level in levels]

    def change(self, system, good, delta):
        level = self.levels[system][good]
        self.levels[system][good] = max(0., min(self.cap(system, good), level+delta))
        self.stock[system][good] = round(self.levels[system][good])

    def in_flight(self, system):
        return sum(1 for s in self.state['shipments'] if system in (s['source'], s['dest']))

    def visit(self, system, ship, now):
        if self.economy and type(system) is int and 0 <= system < len(self.stock): self.economy.visit(system, ship, now)

    def advance(self, now):
        state = self.state
        self.reconcile()
        if self.economy:
            for system in range(len(self.stock)):
                caps = [self.cap(system, g) for g in range(len(self.stock[system]))]
                self.economy.advance(system, self.levels[system], caps, now, self.in_flight(system))
            self.sync()
            if getattr(self, 'council', None): self.council(self, now)
        if state['next_trade'] is None: state['next_trade'] = now
        # After a long idle spell, simulate only the most recent stretch.
        earliest = now-MAX_CATCH_UP*sum(TRADE_INTERVAL)/2
        if state['next_trade'] < earliest: state['next_trade'] = earliest
        while state['next_trade'] <= now:
            t = state['next_trade']
            self.deliver(t)
            rng = random.Random(f"{state['seed']}:{state['seq']}")
            state['seq'] += 1
            if not self.economy: self.restock(rng)
            self.bot_trade(rng, t)
            state['next_trade'] = t+rng.uniform(*TRADE_INTERVAL)
        self.deliver(now)

    def deliver(self, now):
        for shipment in [s for s in self.state['shipments'] if s['arrive'] <= now]:
            self.state['shipments'].remove(shipment)
            self.change(shipment['dest'], shipment['good'], shipment['n'])
            self.pay_tax(shipment['dest'], shipment['n']*self.price(shipment['dest'], shipment['good']))
            self.visit(shipment['dest'], 'bot:'+shipment['id'], shipment['arrive'])

    def restock(self, rng):
        """Without an economy, stations simply produce: a random line below its normal level gains a little."""
        system, good = rng.randrange(len(self.stock)), rng.randrange(len(self.stock[0]))
        if self.stock[system][good] < self.normal[system][good]: self.change(system, good, rng.randint(1, 2))

    def bot_trade(self, rng, now):
        if len(self.state['shipments']) >= MAX_SHIPMENTS: return None
        systems = list(range(len(self.stock)))
        good = rng.randrange(len(self.stock[0]))
        offers = rng.sample(systems, 4)
        sources = [s for s in offers if self.stock[s][good] >= 2]
        if not sources: return None
        source = min(sources, key=lambda s: self.price(s, good))
        dest = max((s for s in offers if s != source), key=lambda s: self.price(s, good))
        if self.price(dest, good)*(1-self.tax(dest)) < self.price(source, good)*(1+self.tax(source))*BOT_MARGIN: return None  # not worth a freighter's trip
        n = min(self.stock[source][good]//2, rng.randint(1, 2) if self.normal[source][good] <= 6 else rng.randint(2, 6))
        if n <= 0: return None
        self.change(source, good, -n)
        self.pay_tax(source, n*self.price(source, good))
        shipment = dict(id=f"{self.state['seed'][:8]}-{self.state['seq']}", name=rng.choice(TRADER_NAMES),
                        source=source, dest=dest, good=good, n=n, depart=now, arrive=now+self.travel_time(source, dest))
        self.state['shipments'].append(shipment)
        self.visit(source, 'bot:'+shipment['id'], now)
        return shipment

    def apply(self, trades=(), intercepts=(), ship=None, system=None, now=None):
        """Player activity: stock changes from buying and selling, and traders destroyed in flight.
        `ship` and `system` say who is at which station, for its traffic."""
        trades = list(trades)[:MAX_OPS]
        for trade in trades:
            if type(trade) not in (list, tuple) or len(trade) != 3: raise ValueError('Invalid trade')
            system_, good, delta = trade
            if type(system_) is not int or type(good) is not int or type(delta) is not int: raise ValueError('Invalid trade')
            if not (0 <= system_ < len(self.stock) and 0 <= good < len(self.stock[0]) and -10 <= delta <= 10): raise ValueError('Invalid trade')
        self.reconcile()
        for system_, good, delta in trades:
            self.change(system_, good, delta)
            if ship is not None and now is not None: self.visit(system_, ship, now)
        if ship is not None and now is not None and system is not None: self.visit(system, ship, now)
        lost = set(i for i in list(intercepts)[:10] if type(i) is str)
        self.state['shipments'] = [s for s in self.state['shipments'] if s['id'] not in lost]

    def snapshot(self, now):
        snap = dict(protocol=1, now=now, stock=[row[:] for row in self.stock],
                    shipments=[dict(s) for s in self.state['shipments']])
        if self.economy:
            snap['economy'] = [self.economy.report(i, self.levels[i], now) for i in range(len(self.stock))]
        return snap


class MarketClient:
    """Keeps the game's copy of the shared market in step with the server, in the background."""
    def __init__(self, remote, interval=3):
        import threading
        self.remote, self.interval = remote, interval
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.trades, self.intercepts = [], []
        self.fresh = None
        self.here = None  # the station this commander is at, for its traffic
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
                request = dict(trades=trades, intercepts=intercepts)
                if self.here is not None: request['system'] = self.here
                snap = self.remote.request(request, endpoint='/v1/market')
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
