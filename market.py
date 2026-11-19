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
# Contraband carries a risk premium: where smugglers lose cargo to customs or pirates, the goods that do
# get through fetch more (the "risks and prices" view of illicit markets: price compensates for losses).
SMUGGLING_HALF_LIFE = 6*3600.   # seconds for the record of losses and deliveries to halve
SMUGGLING_PRIOR = 20.           # tonnes of experience the expected risk counts for, so one seizure isn't a price shock
RISK_PREMIUM_CAP = 3.           # covers customs' full 55% search with the reward below (1.25/0.45 = 2.8)
REPORT_CAP = 40.                # tonnes one commander's reports count for, per world per half-life (a hold is <= 35 t)
RISK_REWARD = .25               # smuggling must pay more than honest trade on average, or nobody would take the risk


def quote_price(base, tax=0., buy=True, premium=None, loss=0., fine=25):
    """The exchange's quote on a station price `base`: an 8% spread and the station's trade tax each way. A world
    pays smugglers `premium` on contraband brought in, plus the expected customs `fine` for the `loss` share seized."""
    spread, tax = math.ceil(base*.08), round(base*tax)
    if buy: return base+max(1, spread)+tax
    if premium is None: return max(1, base-spread-tax)
    return max(1, round(base*premium+fine*loss/(1-loss))-spread-tax)


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
            council['turnover'] = council.get('turnover', 0.)+value   # all trade, for the Tally's output
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

    def smuggling(self, system, good, lost=0., delivered=0., now=None):
        """Record contraband seized or destroyed on its way to a world, or delivered there; returns the record."""
        now = getattr(self, 'clock', 0.) if now is None else now
        books = self.state.setdefault('smuggling', {}).setdefault(str(system), {})
        record = books.get(str(good), [0., 0., now])
        keep = .5**(max(0., now-record[2])/SMUGGLING_HALF_LIFE)
        record = [record[0]*keep+lost, record[1]*keep+delivered, now]
        self.state['contraband_lost'] = self.state.get('contraband_lost', 0.)+lost   # for the Tally
        books[str(good)] = record
        return record

    def allowance(self, ship, system, lost, delivered, now):
        """Trim one commander's reports to REPORT_CAP tonnes per world per half-life, so nobody can flood the premium."""
        now = getattr(self, 'clock', 0.) if now is None else now
        quota = self.state.setdefault('report_quota', {})
        for key in [k for k, (n, t) in quota.items() if n*.5**((now-t)/SMUGGLING_HALF_LIFE) < .5]: del quota[key]
        used, at = quota.get(f'{ship}:{system}', (0., now))
        used *= .5**(max(0., now-at)/SMUGGLING_HALF_LIFE)
        room = max(0., REPORT_CAP-used)
        lost = min(lost, room); delivered = min(delivered, room-lost)
        quota[f'{ship}:{system}'] = (used+lost+delivered, now)
        return lost, delivered

    def risk_premium(self, system, good):
        """Contraband price multiplier: what a smuggler needs to break even after the share of cargo lost here, capped."""
        expected = self.contraband_risk(system) if getattr(self, 'contraband_risk', None) else 0.
        record = self.state.get('smuggling', {}).get(str(system), {}).get(str(good))
        lost = delivered = 0.
        if record:
            keep = .5**(max(0., getattr(self, 'clock', record[2])-record[2])/SMUGGLING_HALF_LIFE)
            lost, delivered = record[0]*keep, record[1]*keep
        # the expected risk counts as SMUGGLING_PRIOR tonnes of experience; real losses and deliveries outweigh it
        share = (lost+SMUGGLING_PRIOR*expected)/(lost+delivered+SMUGGLING_PRIOR)
        return min(RISK_PREMIUM_CAP, (1+RISK_REWARD)/(1-share))

    def loss_share(self, system, good):
        """The share of contraband expected to be lost bringing it here (as priced into the premium)."""
        return 1-(1+RISK_REWARD)/self.risk_premium(system, good) if self.risk_premium(system, good) > 1+RISK_REWARD else 0.

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
        self.clock = now
        self.reconcile()
        if self.economy:
            for system in range(len(self.stock)):
                caps = [self.cap(system, g) for g in range(len(self.stock[system]))]
                self.economy.advance(system, self.levels[system], caps, now, self.in_flight(system))
            self.sync()
            if getattr(self, 'council', None):
                self.council(self, now)
                import tally
                tally.publish(self, now)
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

    def apply(self, trades=(), intercepts=(), ship=None, system=None, now=None, smuggling=()):
        """Player activity: stock changes from buying and selling (each pays the station's trade tax), traders
        destroyed in flight, and contraband reports [system, good, tonnes lost, tonnes delivered] for the risk premium.
        `ship` and `system` say who is at which station, for its traffic."""
        if type(smuggling) not in (list, tuple) or len(smuggling) > 10: raise ValueError('Invalid smuggling report')
        for report in smuggling:
            if type(report) not in (list, tuple) or len(report) != 4 or any(type(n) is not int for n in report): raise ValueError('Invalid smuggling report')
            where, good, lost, delivered = report
            if not (0 <= where < len(self.stock) and good in getattr(self, 'contraband', ()) and 0 <= lost <= 50 and 0 <= delivered <= 50):
                raise ValueError('Invalid smuggling report')
        trades = list(trades)[:MAX_OPS]
        for trade in trades:
            if type(trade) not in (list, tuple) or len(trade) != 3: raise ValueError('Invalid trade')
            system_, good, delta = trade
            if type(system_) is not int or type(good) is not int or type(delta) is not int: raise ValueError('Invalid trade')
            if not (0 <= system_ < len(self.stock) and 0 <= good < len(self.stock[0]) and -10 <= delta <= 10): raise ValueError('Invalid trade')
        self.reconcile()
        for system_, good, delta in trades:
            self.pay_tax(system_, abs(delta)*self.price(system_, good))
            self.change(system_, good, delta)
            if ship is not None and now is not None: self.visit(system_, ship, now)
        if ship is not None and now is not None and system is not None: self.visit(system, ship, now)
        for where, good, lost_, delivered in smuggling:
            if ship is not None and system is not None and where != system: continue   # docked: only your own station
            if ship is not None: lost_, delivered = self.allowance(ship, where, lost_, delivered, now)
            if lost_ or delivered: self.smuggling(where, good, lost=lost_, delivered=delivered, now=now)
        lost = set(i for i in list(intercepts)[:10] if type(i) is str)
        self.state['shipments'] = [s for s in self.state['shipments'] if s['id'] not in lost]

    def snapshot(self, now):
        snap = dict(protocol=1, now=now, stock=[row[:] for row in self.stock],
                    shipments=[dict(s) for s in self.state['shipments']])
        if self.economy:
            snap['economy'] = [self.economy.report(i, self.levels[i], now) for i in range(len(self.stock))]
        council = self.state.get('council')
        if council:   # the Council's view, for prices, tax, customs, beacons and news in the game
            worlds = range(len(self.stock))
            snap['council'] = dict(
                tax=[council.get('tax', {}).get(str(i), 0.) for i in worlds], rate=float(council.get('rate', .05)),
                safety=[council.get('safety', {}).get(str(i), 0.) for i in worlds], beacons=list(council.get('beacons', [])),
                decrees=[dict(id=d.get('id', f"{d['kind']}-{d['system']}-{int(d['at'])}"), at=d['at'], kind=d['kind'],
                              system=d['system'], text=d.get('text', d['kind'])) for d in council.get('decrees', [])[-10:]])
        if self.state.get('tally'): snap['tally'] = {k: v for k, v in self.state['tally'].items() if k != 'previous'}
        if self.economy and getattr(self, 'contraband', None):
            snap['prices'] = dict(depth=[self.depth(i) for i in range(len(self.stock))], adjust=[[self.economy.price_adjust(i, g) for g in range(len(self.stock[i]))] for i in range(len(self.stock))],
                                  contraband=[[[self.risk_premium(i, g), self.loss_share(i, g)] for g in self.contraband] for i in range(len(self.stock))])
        return snap


class MarketClient:
    """Keeps the game's copy of the shared market in step with the server, in the background."""
    def __init__(self, remote, interval=3):
        import threading
        self.remote, self.interval = remote, interval
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.trades, self.intercepts, self.smuggling = [], [], []
        self.fresh = None
        self.here = None  # the station this commander is at, for its traffic
        self.status = 'Market: connecting'
        self.thread = threading.Thread(target=self.run, name='market', daemon=True)
        self.thread.start()

    def queue_trade(self, system, good, delta):
        with self.lock: self.trades.append([system, good, delta])

    def report_smuggling(self, system, good, lost=0, delivered=0):
        """Contraband seized or lost on the way to `system`, or sold there: the server's risk premium learns from it."""
        with self.lock: self.smuggling.append([system, good, int(lost), int(delivered)])

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
                trades, intercepts, smuggling = self.trades[:MAX_OPS], self.intercepts[:10], self.smuggling[:10]
            try:
                request = dict(trades=trades, intercepts=intercepts)
                if smuggling: request['smuggling'] = smuggling
                if self.here is not None: request['system'] = self.here
                snap = self.remote.request(request, endpoint='/v1/market')
                if snap.get('protocol') != 1 or type(snap.get('stock')) is not list or type(snap.get('shipments')) is not list: raise ValueError('Invalid market')
                with self.lock:
                    del self.trades[:len(trades)]
                    del self.intercepts[:len(intercepts)]
                    del self.smuggling[:len(smuggling)]
                    self.fresh = snap
                self.status = 'Market: shared'
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                self.status = 'Market: offline, using local prices'
            self.stop.wait(self.interval)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=6)
