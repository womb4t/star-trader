"""Station economies: people who consume, workers who produce, and ships that make it all move faster.

Each station is advanced lazily, only when someone looks at it, and in closed form rather than by
ticking: between updates every stock line follows
    ds/dt = rate * (target - s)        =>   s(t) = target + (s0 - target) * exp(-rate * t)
where the target comes from what the population consumes and the factories produce, and the rate
grows with how many ships use the station. Untouched stations cost nothing, which is what an
unbounded galaxy needs. Long gaps are split into a few sub-steps so prosperity and events can feed
back into the targets.

Goods (index): 0 Food, 1 Textiles, 2 Ore, 3 Machinery, 4 Medicine, 5 Computers,
               6 Narcotics, 7 Unlicensed Arms, 8 Gold, 9 Silver
"""
import math
import random

HOUR = 3600.
GOODS = 10
FOOD, TEXTILES, ORE, MACHINERY, MEDICINE, COMPUTERS, NARCOTICS, ARMS, GOLD, SILVER = range(GOODS)

# What people use, per head relative to an average world. Comforts and luxuries are only bought
# as prosperity allows (needs tiers, as in Victoria 3).
BASIC = {FOOD: 1.0, MEDICINE: .5}
COMFORT = {TEXTILES: .7, COMPUTERS: .5, MACHINERY: .3}
LUXURY = {NARCOTICS: .4, GOLD: .25, SILVER: .3, ARMS: .2}

# Factories by economy: output per good, and the input they need to run (X4-style workforce
# boosts output; missing inputs stall it).
FACTORIES = {
    'Agricultural': dict(output={FOOD: 1.4, TEXTILES: 1.0, NARCOTICS: .6}, inputs={MACHINERY: .5}),
    'Industrial': dict(output={MACHINERY: 1.3, COMPUTERS: 1.0, MEDICINE: .8, ARMS: .6}, inputs={ORE: 1.0, FOOD: .4}),
    'Frontier': dict(output={ORE: 1.4, GOLD: .7, SILVER: .9, ARMS: .3}, inputs={MACHINERY: .6, FOOD: .3}),
}
LAWLESS = ('Anarchy', 'Feudal')

BASE_RATE = 1/(50*60)       # how fast stock settles towards its target with no ships about (per second)
TARGET_GAIN = .32           # how far production minus consumption pushes the target from normal stock
TARGET_RANGE = (.3, 1.65)   # target stock as a share of normal stock
PROSPERITY_TIME = 3*HOUR    # prosperity follows how well needs are met over a few hours
POPULATION_DRIFT = .03/(24*HOUR)  # population share change per second at full boom or bust
POPULATION_RANGE = (.8, 1.25)
VISIT_WINDOW = 30*60        # a ship counts towards traffic for this long after it trades or docks
MAX_STEPS = 24
MIN_STEP = 300.

# ---------- adaptive economy (prototype, off unless ADAPTIVE) ----------
# Real-economy behaviour: industries grow where their goods are scarce and dear and shrink in a glut
# (supply responds to price); people buy less of what is expensive (demand responds to price); and a
# world's prices come from what it actually makes and uses, so a new industry changes its prices.
ADAPTIVE = False
ADAPT_RATE = .10/(24*HOUR)      # industry growth per second at the scarcest prices (10% a day)
INDUSTRY_RANGE = (0., 2.5)      # capacity of one industry line, as a share of a typical factory
ELASTICITY = {g: .1 for g in range(10)}   # how much consumption falls as price rises (basics barely)
ELASTICITY.update({1: .5, 3: .4, 5: .6, 6: .3, 7: .3, 8: .8, 9: .8})
NATIVE = {e: set(f['output']) for e, f in FACTORIES.items()}
OFF_SPECIALITY = .6             # a licensed line outside the economy's speciality starts this efficient...
LEARNED = .9                    # ...and learns towards this while it runs (learning by doing)
LEARN_RATE = .05/(24*HOUR)      # efficiency gained per second of running (5 points a day)
TRAFFIC_TIME = 6*HOUR           # how long a station's remembered traffic takes to follow the present
PER_COMMANDER = .3              # each commander regularly at a station supports this much more population
SETTLE = 1/(2*24*HOUR)          # population closes on its supportable size over about two days
GROWTH = .04/(24*HOUR)         # population change per second for a busy, thriving world (adaptive)
GROWTH_RANGE = (.8, 8.)         # population as a share of the founding population (adaptive)
BASE_INTEREST = .05             # the galactic rate at which industries invest at the normal pace
SPENDING_GAIN, SPENDING_RANGE = .4, (.8, 1.3)   # demand: +20% at a 2.5% rate, -20% at 7.5%
PRICE_POWER = .45                # base price = BASE * (use / make) ** PRICE_POWER, within PRICE_RANGE
PRICE_RANGE = (.65, 1.45)


def productivity(economy, good, station=None):
    """How efficient a line is: native specialities 1.0; licensed lines start lower and learn."""
    if good in NATIVE[economy]: return 1.
    if station is not None and 'skill' in station: return station['skill'][good]
    return OFF_SPECIALITY


def investment(rate):
    """Cheap money builds factories faster: 2x at 2%, 1x at 5%, a quarter at 11%."""
    return 2**((BASE_INTEREST-rate)/.03)


def spending(rate):
    """Cheap money lifts what people buy (credit is easy), dear money damps it: 1x at the neutral rate."""
    return max(SPENDING_RANGE[0], min(SPENDING_RANGE[1], 1+SPENDING_GAIN*(BASE_INTEREST-rate)/BASE_INTEREST))


def scarcity(level, normal):
    """The market's supply-and-demand factor (same curve as market.demand_factor)."""
    ratio = level/max(1, normal)
    return max(.75, min(1.5, 1+.5*(1-ratio)))


# Demand events: a seeded schedule, the same for every commander without storing anything.
EVENT_WINDOW = 3*HOUR
EVENTS = {
    # kind: (headline, consumption multipliers, production multipliers, economies it can hit)
    'famine': ('Famine', {FOOD: 3., MEDICINE: 1.5}, {}, ('Industrial', 'Frontier')),
    'plague': ('Plague outbreak', {MEDICINE: 4.}, {}, ('Agricultural', 'Industrial', 'Frontier')),
    'boom': ('Mining boom', {MACHINERY: 2., FOOD: 1.5}, {ORE: 2.5, GOLD: 2.5, SILVER: 2.5}, ('Frontier',)),
    'strike': ('Factory strike', {}, {MACHINERY: .2, COMPUTERS: .2, MEDICINE: .4}, ('Industrial',)),
    'harvest': ('Bumper harvest', {}, {FOOD: 2.5, TEXTILES: 1.8}, ('Agricultural',)),
    'festival': ('Festival season', {TEXTILES: 2.5, GOLD: 2.5, SILVER: 2.5, NARCOTICS: 2.}, {}, ('Agricultural', 'Industrial', 'Frontier')),
    'war': ('Local war', {ARMS: 4., MEDICINE: 2., FOOD: 1.5}, {}, ('Frontier', 'Agricultural')),
}
HEADLINES = {
    'famine': 'food and medicine in desperate demand',
    'plague': 'medicine needed urgently',
    'boom': 'ore and precious metals flooding out; machinery wanted',
    'strike': 'machinery and computers scarce',
    'harvest': 'food and textiles cheap',
    'festival': 'textiles, gold, silver and luxuries wanted',
    'war': 'arms, medicine and food in demand',
}


def window_events(window, profiles):
    """The demand events of one EVENT_WINDOW: up to two, each 1-2.5 hours, at systems that fit."""
    rng = random.Random(f'economy-event-{window}')
    events = []
    for n in range(rng.choice((0, 1, 1, 2))):
        kind = rng.choice(sorted(EVENTS))
        _, _, _, economies = EVENTS[kind]
        systems = [i for i, p in enumerate(profiles) if p['economy'] in economies
                   and (kind != 'war' or p['government'] in LAWLESS or p['economy'] == 'Frontier')]
        system = rng.choice(systems) if systems else None
        start = window*EVENT_WINDOW+rng.uniform(0, EVENT_WINDOW*.6)
        end = start+rng.uniform(1, 2.5)*HOUR
        if system is not None and all(e['system'] != system for e in events):
            events.append(dict(id=f'{window}-{n}', kind=kind, system=system, start=start, end=end,
                               title=EVENTS[kind][0], effect=HEADLINES[kind]))
    return events


def events_at(now, profiles):
    """Events running at this moment (an event can spill over from the previous window)."""
    window = int(now//EVENT_WINDOW)
    return [e for w in (window-1, window) for e in window_events(w, profiles) if e['start'] <= now < e['end']]


def traffic_factor(ships):
    """More ships, more trade: up to 4x the flow, with diminishing returns."""
    return 1+3*(1-math.exp(-max(0., ships)/6))


class Economy:
    """Population, prosperity and stock targets for every station. `levels` are the stock lines
    (floats, so slow flows are not lost to rounding); the market keeps whole-number stock beside them."""

    def __init__(self, profiles, normal, state):
        self.profiles, self.normal, self.state = profiles, normal, state
        state.setdefault('stations', {})
        state.setdefault('visitors', {})

    def station(self, system, now):
        stations = self.state['stations']
        key = str(system)
        if key not in stations: stations[key] = dict(population=1., prosperity=.6, last=now)
        station = stations[key]
        if ADAPTIVE and 'industry' not in station:
            station['industry'] = [0.]*GOODS
            for good, out in FACTORIES[self.profiles[system]['economy']]['output'].items(): station['industry'][good] = out
        return station

    def industry(self, system, station):
        """Output capacity per good: the economy type's factories, or what the station has grown into."""
        if ADAPTIVE: return station['industry']
        out = [0.]*GOODS
        for good, n in FACTORIES[self.profiles[system]['economy']]['output'].items(): out[good] = n
        return out

    # ---------- traffic ----------
    def visit(self, system, ship, now):
        visitors = self.state['visitors'].setdefault(str(system), {})
        visitors[str(ship)[:40]] = now
        if len(visitors) > 64:
            for name in sorted(visitors, key=visitors.get)[:len(visitors)-64]: del visitors[name]

    def ships(self, system, now, in_flight=0):
        """Ships using a station: recent visitors plus half of the traders flying to or from it."""
        visitors = self.state['visitors'].get(str(system), {})
        for name in [n for n, t in visitors.items() if now-t > VISIT_WINDOW]: del visitors[name]
        return len(visitors)+.5*in_flight

    def commanders(self, system, now):
        """Player ships that used this station lately (bot traders don't count)."""
        visitors = self.state['visitors'].get(str(system), {})
        return sum(1 for n, t in visitors.items() if not n.startswith('bot:') and now-t <= VISIT_WINDOW)

    # ---------- needs and production ----------
    def flows(self, system, levels, station, events):
        """Consumption and production of every good, as shares of a typical world's flow."""
        profile = self.profiles[system]
        normal = self.normal[system]
        people = profile['population']/4.0*station['population']
        prosperity = station['prosperity']
        consume = [0.]*GOODS
        produce = [0.]*GOODS
        for good, need in BASIC.items(): consume[good] += people*need
        for good, need in COMFORT.items(): consume[good] += people*need*(.4+.6*prosperity)
        for good, need in LUXURY.items(): consume[good] += people*need*prosperity
        if profile['government'] in LAWLESS: consume[ARMS] += .3*people
        factory = FACTORIES[profile['economy']]
        supplied = min([1.]+[min(1., .3+levels[g]/(.5*max(1, normal[g]))) for g in factory['inputs']])
        workforce = (.6+.6*prosperity)*(station['population'] if ADAPTIVE else 1.)   # more people, more output
        industry = self.industry(system, station)
        base_total = sum(factory['output'].values())
        scale = sum(industry)/base_total if base_total else 1.   # a bigger industrial base needs more inputs
        for good, out in enumerate(industry):
            produce[good] += out*workforce*supplied*(productivity(profile['economy'], good, station) if ADAPTIVE else 1.)
        for good, use in factory['inputs'].items(): consume[good] += use*workforce*scale
        if ADAPTIVE:   # dear goods are bought less
            spend = spending(self.state.get('council', {}).get('rate', BASE_INTEREST))
            for g in range(GOODS): consume[g] *= spend*scarcity(levels[g], normal[g])**-ELASTICITY[g]
        for event in events:
            if event['system'] != system: continue
            _, more, made, _ = EVENTS[event['kind']]
            for good, factor in more.items(): consume[good] *= factor
            for good, factor in made.items(): produce[good] *= factor
        return consume, produce

    def targets(self, system, levels, station, events):
        consume, produce = self.flows(system, levels, station, events)
        low, high = TARGET_RANGE
        depth = self.depth(system)
        return [self.normal[system][g]*depth*max(low, min(high, 1+TARGET_GAIN*(produce[g]-consume[g])/depth)) for g in range(GOODS)]

    def depth(self, system):
        """How deep a station's market is: a bigger population keeps more stock (adaptive economy)."""
        if not ADAPTIVE: return 1.
        station = self.state['stations'].get(str(system))
        return station['population'] if station else 1.

    def needs_met(self, system, levels):
        """How well the people are supplied: basics weigh most."""
        normal = [n*self.depth(system) for n in self.normal[system]]
        def met(goods): return sum(min(1., levels[g]/(.5*max(1, normal[g]))) for g in goods)/len(goods)
        return .7*met(BASIC)+.3*met(COMFORT)

    # ---------- time ----------
    def advance(self, system, levels, cap, now, in_flight=0):
        """Bring one station up to `now` in closed form. `levels` (floats) is updated in place."""
        station = self.station(system, now)
        gap = now-station['last']
        if gap <= 0: return station
        rate = BASE_RATE*traffic_factor(self.ships(system, now, in_flight))
        steps = max(1, min(MAX_STEPS, math.ceil(gap/MIN_STEP)))
        dt = gap/steps
        for n in range(steps):
            moment = station['last']+(n+.5)*dt
            events = events_at(moment, self.profiles)
            target = self.targets(system, levels, station, events)
            keep = math.exp(-rate*dt)
            for g in range(GOODS):
                levels[g] = max(0., min(cap[g], target[g]+(levels[g]-target[g])*keep))
            if ADAPTIVE: self.adapt(system, levels, station, dt)
            follow = 1-math.exp(-dt/PROSPERITY_TIME)
            station['prosperity'] += (self.needs_met(system, levels)-station['prosperity'])*follow
            if ADAPTIVE:   # people move to where the work is: a size set by regular traffic and prosperity
                low, high = GROWTH_RANGE
                station['traffic'] = station.get('traffic', 0.)+(self.commanders(system, moment)-station.get('traffic', 0.))*(1-math.exp(-dt/TRAFFIC_TIME))
                size = max(low, min(high, (1+PER_COMMANDER*station['traffic'])*(.8+.4*station['prosperity'])))
                station['population'] *= math.exp(SETTLE*math.log(size/station['population'])*dt)
            else:
                low, high = POPULATION_RANGE
                station['population'] = max(low, min(high, station['population']+(station['prosperity']-.5)*2*POPULATION_DRIFT*dt))
        station['last'] = now
        if ADAPTIVE: self.reprice(system, levels, station, events_at(now, self.profiles))
        return station

    def adapt(self, system, levels, station, dt):
        """Supply follows price: a line grows while its good is scarce here and shrinks in a glut."""
        industry, normal = station['industry'], [n*self.depth(system) for n in self.normal[system]]
        skill = station.setdefault('skill', [OFF_SPECIALITY]*GOODS)
        for g in range(GOODS):   # learning by doing: a running licensed line gets better at it
            if industry[g] >= .2: skill[g] = min(LEARNED, skill[g]+LEARN_RATE*dt)
        low, high = INDUSTRY_RANGE
        for g in range(GOODS):
            if industry[g] <= 0: continue
            pull = (scarcity(levels[g], normal[g])-1)/.5      # +1 at the scarcest, -0.5 in the worst glut
            if pull > 0: pull *= investment(self.state.get('council', {}).get('rate', BASE_INTEREST))
            industry[g] = max(low, min(high, industry[g]*math.exp(ADAPT_RATE*pull*dt)))
            if industry[g] < .05: industry[g] = 0.            # a line this small has closed

    def reprice(self, system, levels, station, events):
        """Base prices from what the station makes and uses: plenty makes a good cheap here."""
        consume, produce = self.flows(system, levels, station, events)
        low, high = PRICE_RANGE
        station['adjust'] = [max(low, min(high, ((consume[g]+.15)/(produce[g]+.15))**PRICE_POWER)) for g in range(GOODS)]

    def price_adjust(self, system, good):
        station = self.state['stations'].get(str(system))
        return station['adjust'][good] if station and 'adjust' in station else 1.

    def report(self, system, levels, now):
        """What a commander sees: people, mood, traffic and which goods are wanted or in surplus."""
        station = self.station(system, now)
        events = [e for e in events_at(now, self.profiles) if e['system'] == system]
        target = self.targets(system, levels, station, events)
        normal = self.normal[system]
        return dict(population=round(self.profiles[system]['population']*station['population'], 2),
                    prosperity=round(station['prosperity'], 3),
                    ships=round(self.ships(system, now), 1),
                    wanted=[g for g in range(GOODS) if target[g] < .8*normal[g] or levels[g] < .5*normal[g]],
                    surplus=[g for g in range(GOODS) if (target[g] > 1.2*normal[g] or levels[g] > 1.5*normal[g])
                             and not (target[g] < .8*normal[g] or levels[g] < .5*normal[g])])


def prosperity_label(prosperity):
    return 'Thriving' if prosperity >= .8 else 'Comfortable' if prosperity >= .6 else 'Struggling' if prosperity >= .4 else 'Destitute'
