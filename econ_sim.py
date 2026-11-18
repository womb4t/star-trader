"""Run the station economy for simulated days and measure whether commanders can make money.

Drives the real market, economy and bot traders on simulated time, with a few simulated commanders
who trade greedily (best profit within a full tank). Every simulated hour it records, per station,
how many legal goods can be bought there and sold within range for a real margin.

    python3 econ_sim.py --days 5 --players 2
"""
import argparse
import math
import os
import random
from collections import defaultdict

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import star_trader as st
from market import Market

HOUR = 3600.
MARGIN = .10          # a trade worth making: sell at least 10% above the buy price
HOLD = 20             # tonnes a commander carries
DOCK_TIME = 180.      # seconds spent docked, trading and refuelling


def in_range(i):
    here = st.coordinates(i)
    return [j for j in range(len(st.SYSTEMS)) if j != i and
            st.hyperspace_cost(st.galactic_distance(here, st.coordinates(j))) <= st.FUEL_CAPACITY]


RANGE = {i: in_range(i) for i in range(len(st.SYSTEMS))}
LEGAL = [g for g in range(len(st.GOODS)) if g not in st.ILLEGAL]


def quote(market, system, good, buy=True):
    """The exchange's quote: the market price with the game's 8% spread, plus the station's trade tax."""
    base = round(market.price(system, good))
    tax = round(base*market.tax(system))
    return base+max(1, math.ceil(base*.08))+tax if buy else max(1, base-math.ceil(base*.08)-tax)


# The bank (prototype): loans secured against the ship, priced off the Council's rate.
LTV = .5              # borrow up to half the ship's value
BANK_MARGIN = .03     # over the galactic rate
REPAY_SHARE = .25     # of every sale, until the loan is clear
FORECLOSE = .6        # repossessed if debt passes this share of the ship's value
RATE_PERIOD = 7*24*HOUR   # the galactic rate is quoted per game week
HULL_VALUE, PER_TONNE = 6000, 400
# Credit rating (approved design): five weighted factors, an affordability check and the legal record.
TIERS = [('A', .80, .60, .02), ('B', .65, .50, .03), ('C', .50, .40, .05), ('D', .35, .25, .08)]   # name, min score, max LTV, margin
MARK_DAYS = 30        # a repossession weighs on the rating for this many game days
DAY = 24*HOUR
AFFORD = 3.           # a loan may be at most this many days of recent trading income (repayments ~1/3 of income)
RATE_CAP = .20        # the bank never charges more than this, whatever the rating
WANTED_DECAY = 12*HOUR
CONTRABAND_RISK = .25 # chance a contraband sale raises the wanted level
SMUGGLERS = .3        # share of commanders who trade contraband
# The bank's own money is limited: it can lend LEVERAGE times its capital. Capital grows with the
# number of active ships (their deposits and business) and with interest earned, and shrinks when
# a default leaves debt the ship's sale doesn't cover. Near the limit it rations credit.
BANK_START, PER_SHIP, LEVERAGE = 20000., 8000., 4.
RATIONING = [(.95, 'A'), (.85, 'B'), (.70, 'C')]   # above this share lent out, only these ratings and better
CRUNCH_MARGIN = .04   # extra margin when the bank is more than 85% lent out
# The bank sets its own margin to maximise profit (interest earned minus bad debts), testing a nudge
# up or down each review and keeping whichever paid; RATE_CAP is the Council's limit on it.
MARGIN_STEP, MARGIN_RANGE, BANK_REVIEW = .0025, (0., .10), 12*HOUR
# A used ship has faults: a cramped hold and tired engines.
USED_HOLD, USED_SLOWDOWN = 15, 1.2
UPGRADE_COST, UPGRADE_STEP, MAX_HOLD = 5000, 10, 60
# Losses and the road back.
SHIP_LOSS = 1/6       # share of pirate attacks that also destroy the ship, not just the cargo
INSURED = .8          # share of commanders who keep their policy paid
EXCESS = .10          # insurance excess, as a share of the ship's value
BASIC_SHIP = 6000     # a basic 20 t ship at a shipyard
HITCH_FARE, HITCH_TONNES = 60, 1
# Station jobs as the game has them: 4-6 shifts per station per day (now shared by everyone docked
# there, more on bigger worlds), 15-40 cr each, a minute or so of work.
SHIFTS_PER_DAY = 5
SHIFT_PAY = 30
# Ways back being tested (off = the game as it is):
WAYS_BACK = dict(work_passage=False, courier=False, used_ship=None)
PASSAGE_WAGE = 40     # crewing a freighter or liner instead of paying the fare
COURIER_FEE = (80, 160)   # a 1 t parcel to the next world


class JobBoards:
    """Shared shifts per station, refilled through the day."""
    def __init__(self): self.left, self.at = {}, {}

    def take(self, market, system, now):
        per_day = SHIFTS_PER_DAY*market.depth(system)
        left = self.left.get(system, per_day)+per_day*(now-self.at.get(system, now))/(24*HOUR)
        self.at[system] = now
        n = int(min(left, per_day))
        self.left[system] = min(left, per_day)-n
        return n


def loss_risk(market, a, b):
    """Chance a run between two worlds is hit: the Council's policing where there is one."""
    import council
    if 'council' in market.state: return (council.risk(market, a)+council.risk(market, b))/2
    lawless = lambda s: st.PROFILES[s][0] in ('Anarchy', 'Feudal')
    return ((.05 if lawless(a) else .02)+(.05 if lawless(b) else .02))/2


def opportunities(market, i, goods=LEGAL):
    """(margin, good, dest) for every good that can be bought at i and sold in range at a profit."""
    out = []
    for g in goods:
        if market.stock[i][g] < 1: continue
        buy = quote(market, i, g)
        sell, dest = max((quote(market, j, g, False), j) for j in RANGE[i])
        out.append(((sell-buy)/buy, g, dest))
    return sorted(out, reverse=True)


class Commander:
    def __init__(self, name, system, rng, loans=False):
        self.name, self.system, self.rng, self.loans = name, system, rng, loans
        self.busy_until = 0.
        self.cargo = None   # (good, n, paid, dest)
        self.earned = 0.
        self.credits, self.hold, self.debt, self.defaults, self.borrowed = 1500., HOLD, 0., 0, 0.
        self.last = None
        self.tax_paid = 0.
        self.insured = rng.random() < INSURED
        self.smuggler = rng.random() < SMUGGLERS
        self.shipless_since = None
        self.lost_cargo = self.lost_ships = self.wipeouts = 0
        self.recoveries = []      # hours from wipe-out to a ship again
        self.first_seen = None
        self.income = []          # (time, profit) of each sale
        self.loan_times, self.marks = [], []   # when loans were taken; when ships were repossessed
        self.wanted, self.wanted_at = 0, 0.
        self.refusals = defaultdict(int)
        self.convictions = []
        self.slowdown = 1.
        self.worth_it = rng.uniform(.06, .18)   # the dearest rate this commander thinks a loan is worth
        self.rating_log = []      # rating at each loan decision

    def ship_value(self):
        return HULL_VALUE+PER_TONNE*self.hold+sum(self.upgrade_cost(h) for h in range(HOLD, self.hold, UPGRADE_STEP))*.6

    def upgrade_cost(self, hold=None):
        """Each bigger hold costs more than the last: 5k, 20k, 45k, 80k for 30, 40, 50, 60 t."""
        hold = self.hold if hold is None else hold
        return UPGRADE_COST*((hold-HOLD)//UPGRADE_STEP+1)**2

    def score(self, now):
        """0-1 from the five factors: repayment record 35%, debt against ship 30%, history 15%,
        recent borrowing 10%, trading record 10%."""
        marks = [t for t in self.marks if now-t < MARK_DAYS*DAY]
        convictions = [t for t in self.convictions if now-t < MARK_DAYS*DAY]   # convictions leave a mark too
        repayment = max(0., 1-.6*len(marks)-.25*len(convictions))
        owed = 1-min(1., self.debt/max(1., .6*self.ship_value()))
        history = min(1., (now-(self.first_seen or now))/(7*DAY))
        recent = 1-min(1., sum(1 for t in self.loan_times if now-t < 2*DAY)/6)
        trading = min(1., self.recent_income(now)/20000)
        return .35*repayment+.30*owed+.15*history+.10*recent+.10*trading

    def recent_income(self, now):
        return sum(p for t, p in self.income if now-t < DAY)

    def rating(self, now):
        score = self.score(now)
        tier = next((i for i, (_, low, _, _) in enumerate(TIERS) if score >= low), None)
        if tier is not None and self.wanted: tier += 1     # wanted 1-2 (or a recent conviction): a tier down
        return TIERS[tier] if tier is not None and tier < len(TIERS) else None

    def apply(self, market, now, amount, why):
        """Ask the bank for a loan; returns what it will lend (maybe less, maybe nothing) and records refusals."""
        if self.wanted >= 3: self.refusals['wanted'] += 1; return 0., 0.
        if self.debt and self.recent_income(now) <= 0 and self.loan_times and now-self.loan_times[-1] > DAY:
            self.refusals['in arrears'] += 1; return 0., 0.
        tier = self.rating(now)
        if tier is None: self.refusals['rating E'] += 1; return 0., 0.
        name, _, ltv, margin = tier
        bank = market.bank_state(now)
        for use, worst in RATIONING:   # a bank short of money only lends to the best risks
            if bank['use'] > use and name > worst: self.refusals['bank short of money'] += 1; return 0., 0.
        margin += bank['margin']+(CRUNCH_MARGIN if bank['use'] > .85 else 0.)
        rate = min(RATE_CAP, market.state.get('council', {}).get('rate', .05)+margin)
        if rate > self.worth_it: self.refusals['declined: too dear'] += 1; return 0., rate   # the commander walks away
        room = ltv*self.ship_value()-self.debt
        afford = AFFORD*self.recent_income(now)-self.debt if self.first_seen and now-self.first_seen > DAY else 4000.   # newcomers: a small starter loan
        offer = max(0., min(amount, room, afford, bank['capacity']-bank['lent']))
        self.rating_log.append(name)
        if offer < amount:
            self.refusals['lower amount: ' + ('ship value' if room <= afford else 'affordability')] += 1
            if offer < .5*amount: return 0., rate      # not enough to be worth it
        self.debt += offer; self.credits += offer; self.borrowed += offer; self.loan_times.append(now)
        market.state['bank']['loans'] = market.state['bank'].get('loans', 0)+1
        return offer, rate

    def bank(self, market, now):
        if self.first_seen is None: self.first_seen = now
        if self.wanted and now-self.wanted_at > WANTED_DECAY: self.wanted -= 1; self.wanted_at = now
        tier = self.rating(now)
        margin = (tier[3] if tier else TIERS[-1][3])+market.state['bank']['margin']
        rate = min(RATE_CAP, market.state.get('council', {}).get('rate', .05)+margin)
        if self.last is not None and self.debt:
            interest = self.debt*rate*(now-self.last)/RATE_PERIOD
            self.debt += interest; market.state['bank']['interest'] += interest
        self.last = now
        if self.shipless_since is None and self.debt > FORECLOSE*self.ship_value():   # repossessed: no free ship
            self.defaults += 1; self.marks.append(now)
            market.state['bank']['losses'] += max(0., self.debt-self.ship_value()*.7)   # what the ship's sale doesn't cover
            self.debt = 0.
            self.wipe(now)
            return
        if self.loans and self.credits < 1500:                  # working capital to fill the hold
            self.apply(market, now, 2500-self.credits, 'cargo')
        if self.hold < MAX_HOLD:                               # grow the business, but not on top of heavy debt
            short = self.upgrade_cost()+1000-self.credits
            if short > 0 and self.loans and rate < .12 and self.debt < .25*self.ship_value():
                self.apply(market, now, short, 'upgrade')
            if self.credits >= self.upgrade_cost()+1000:
                self.credits -= self.upgrade_cost(); self.hold += UPGRADE_STEP

    def wipe(self, now):
        self.shipless_since, self.hold, self.cargo, self.wipeouts = now, 0, None, self.wipeouts+1

    def hitch(self, market, now):
        """No ship: take whatever station shifts are free, hitch on with a tonne of the best trade (or a
        courier parcel), and buy a ship when able."""
        shifts = market.jobs.take(market, self.system, now)
        wage = shifts*SHIFT_PAY
        if self.debt: pay = min(self.debt, wage*REPAY_SHARE); self.debt -= pay; wage -= pay
        self.credits += wage
        if self.cargo:
            g, n, paid, _ = self.cargo
            self.credits += n*quote(market, self.system, g, False); self.earned += n*quote(market, self.system, g, False)-paid
            trade(market, self.system, g, n, self.name, now); self.cargo = None
        price = WAYS_BACK['used_ship'] or BASIC_SHIP
        if self.credits >= price+300:
            self.credits -= price; self.hold = HOLD
            if WAYS_BACK['used_ship']: self.hold, self.slowdown = USED_HOLD, USED_SLOWDOWN   # a used ship's faults
            self.recoveries.append((now-self.shipless_since)/HOUR); self.shipless_since = None
            return
        best = [o for o in opportunities(market, self.system) if o[0] >= .2]
        dest = best[0][2] if best else self.rng.choice(RANGE[self.system])
        if WAYS_BACK['courier']:   # carry a parcel instead of trading the tonne
            self.credits += self.rng.randint(*COURIER_FEE)
        elif best and self.credits >= HITCH_FARE+quote(market, self.system, best[0][1]):
            g = best[0][1]; paid = quote(market, self.system, g)
            self.credits -= paid; trade(market, self.system, g, -HITCH_TONNES, self.name, now); self.cargo = (g, HITCH_TONNES, paid, dest)
        if WAYS_BACK['work_passage']: self.credits += PASSAGE_WAGE
        elif self.credits >= HITCH_FARE: self.credits -= HITCH_FARE
        else:   # can't afford a ride: stay and wait for shifts
            self.busy_until = now+2*HOUR
            return
        self.busy_until = now+DOCK_TIME*3+st.trader_travel_time(self.system, dest)   # waiting for a berth, then the ride
        self.system = dest

    def act(self, market, now):
        if now < self.busy_until: return
        if self.shipless_since is not None: return self.hitch(market, now)
        if self.cargo and self.rng.random() < loss_risk(market, self.came_from, self.system):   # pirates
            self.lost_cargo += 1; self.earned -= self.cargo[2]; self.cargo = None
            if self.rng.random() < SHIP_LOSS:
                self.lost_ships += 1
                if self.insured:   # the policy pays the rest; an excess you can't cover goes on your bank debt
                    self.credits -= EXCESS*self.ship_value()
                    if self.credits < 0: self.debt += -self.credits; self.credits = 0.
                else:
                    self.debt = max(0., self.debt-max(0., self.credits)); self.wipe(now); self.last_tick = now
                    return
        if self.cargo:   # arrived: sell
            g, n, paid, _ = self.cargo
            takings = n*quote(market, self.system, g, False)
            self.earned += takings-paid
            self.income.append((now, takings-paid)); self.income = self.income[-200:]
            if g in st.ILLEGAL and self.rng.random() < CONTRABAND_RISK and st.PROFILES[self.system][0] not in ('Anarchy', 'Feudal'):
                self.wanted = min(5, self.wanted+1); self.wanted_at = now; self.convictions.append(now)
            self.credits += takings
            if self.debt:
                pay = min(self.debt, REPAY_SHARE*takings); self.debt -= pay; self.credits -= pay
            self.tax_paid += n*market.price(self.system, g)*market.tax(self.system)
            market.pay_tax(self.system, n*market.price(self.system, g))
            trade(market, self.system, g, n, self.name, now)
            self.cargo = None
        self.bank(market, now)
        best = [o for o in opportunities(market, self.system, range(len(st.GOODS)) if self.smuggler else LEGAL) if o[0] >= .05]
        n = 0
        if best:
            margin, g, dest = best[0]
            n = min(self.hold, market.stock[self.system][g], int(self.credits//max(1, quote(market, self.system, g))))
        if n > 0:
            paid = n*quote(market, self.system, g)
            self.credits -= paid
            self.tax_paid += n*market.price(self.system, g)*market.tax(self.system)
            market.pay_tax(self.system, n*market.price(self.system, g))
            trade(market, self.system, g, -n, self.name, now)
            self.cargo = (g, n, paid, dest)
        else:
            dest = self.rng.choice(RANGE[self.system])   # nothing here: fly on empty and look elsewhere
        self.busy_until = now+DOCK_TIME+st.trader_travel_time(self.system, dest)*self.slowdown
        self.came_from, self.system = self.system, dest


def trade(market, system, good, delta, ship, now):
    while delta:
        step = max(-10, min(10, delta))
        market.apply([(system, good, step)], ship=ship, system=system, now=now)
        delta -= step


def quirk(system, good):
    """The station's own +/-10% on a good's base price, as in star_trader.static_price."""
    return random.Random(system*97+good*13).uniform(.9, 1.1)


def make_market(seed, adaptive=False):
    import economy, council
    economy.ADAPTIVE = adaptive
    market = Market(st.NORMAL_STOCK, st.static_price, st.trader_travel_time, None, seed=seed, profiles=st.ECONOMY_PROFILES)
    if adaptive:
        market.adaptive_base = lambda s, g: st.BASE[g]*quirk(s, g)
        market.contraband = st.ILLEGAL
        names, goods = [s[0] for s in st.SYSTEMS], st.GOODS
        market.council = lambda m, now: council.review(m, now, RANGE, st.ILLEGAL, names, goods)
    return market


def run(days=5, players=2, seed='sim', start=1.8e9, setup=None, quiet=False, adaptive=False, sample=HOUR, loans=False, force_wipe=0):
    market = make_market(seed, adaptive)
    if setup: setup(market)
    rng = random.Random(seed)
    crew = [Commander(f'cmdr{k}', rng.randrange(len(st.SYSTEMS)), rng, loans) for k in range(players)]
    market.crew = crew
    market.jobs = JobBoards()
    market.state['bank'] = dict(interest=0., losses=0., use=0., lent=0., capacity=0., margin=.02,
                                step=MARGIN_STEP, reviewed=start, last_profit=None, margins=[])
    def bank_state(now, market=market):
        """Capital grows with active ships and interest and falls with losses; the margin chases profit."""
        b = market.state['bank']
        active = sum(1 for c in crew if c.shipless_since is None)
        capital = BANK_START+PER_SHIP*active+.5*b['interest']-b['losses']
        b['capacity'] = max(0., capital*LEVERAGE)
        b['lent'] = sum(c.debt for c in crew)
        b['use'] = b['lent']/b['capacity'] if b['capacity'] else 1.
        if now-b['reviewed'] >= BANK_REVIEW:   # price by demand and scarcity, a small step at a time
            declined = sum(c.refusals['declined: too dear'] for c in crew)
            turned_away, made = declined-b.get('declined', 0), b.get('loans', 0)-b.get('loans_seen', 0)
            asked = turned_away+made
            lo, hi = MARGIN_RANGE
            if b['use'] > .7: b['margin'] += MARGIN_STEP                         # money is scarce: charge more
            elif asked and turned_away/asked > .5: b['margin'] -= MARGIN_STEP    # most walk away: too dear
            elif asked and turned_away/asked < .2: b['margin'] += MARGIN_STEP/2  # nearly everyone accepts: room to charge more
            b['margin'] = max(lo, min(hi, b['margin']))
            b['declined'], b['loans_seen'], b['reviewed'] = declined, b.get('loans', 0), now
            b['margins'].append(b['margin'])
        return b
    market.bank_state = bank_state
    rates = []
    stats = defaultdict(list)
    t, end, next_sample = start, start+days*24*HOUR, start+sample
    while t < end:
        market.advance(t)
        market.bank_state(t)
        if force_wipe and t >= start+24*HOUR:   # test the road back: some commanders lose everything on day 1
            for c in crew[:force_wipe]: c.credits, c.debt, c.recoveries = 0., 0., []; c.wipe(t); c.forced = True
            force_wipe = 0
        for c in crew: c.act(market, t)
        if t >= next_sample:
            rates.append(market.state.get('council', {}).get('rate', .05))
            for i in range(len(st.SYSTEMS)):
                ops = [o for o in opportunities(market, i) if o[0] >= MARGIN]
                stats[i].append((len(ops), ops[0][0] if ops else 0.))
            next_sample += sample
        t += 30.
    result = {}
    for i, rows in stats.items():
        result[st.SYSTEMS[i][0]] = dict(
            dead=sum(1 for n, _ in rows if n == 0)/len(rows),
            mean_ops=sum(n for n, _ in rows)/len(rows),
            best=sorted(m for _, m in rows)[len(rows)//2])
    earned = sum(c.earned for c in crew)/max(1, players)/(days*24)
    market.rates = rates
    if not quiet:
        print(f'{"station":10} {"economy":13} {"dead hours":>10} {"good trades":>11} {"median best margin":>19}')
        for i, (name, r) in enumerate(result.items()):
            print(f'{name:10} {st.SYSTEMS[i][1]:13} {r["dead"]:>9.0%} {r["mean_ops"]:>11.1f} {r["best"]:>18.0%}')
        print(f'commander earnings: {earned:,.0f} cr per hour each ({players} commanders, {days} days)')
    return result, earned, market


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=float, default=5)
    ap.add_argument('--players', type=int, default=2)
    ap.add_argument('--seed', default='sim')
    ap.add_argument('--adaptive', action='store_true')
    a = ap.parse_args()
    run(a.days, a.players, a.seed, adaptive=a.adaptive)
