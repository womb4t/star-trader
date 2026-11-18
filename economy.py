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
        return stations[key]

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
        workforce = .6+.6*prosperity
        for good, out in factory['output'].items(): produce[good] += out*workforce*supplied
        for good, use in factory['inputs'].items(): consume[good] += use*workforce
        for event in events:
            if event['system'] != system: continue
            _, more, made, _ = EVENTS[event['kind']]
            for good, factor in more.items(): consume[good] *= factor
            for good, factor in made.items(): produce[good] *= factor
        return consume, produce

    def targets(self, system, levels, station, events):
        consume, produce = self.flows(system, levels, station, events)
        low, high = TARGET_RANGE
        return [self.normal[system][g]*max(low, min(high, 1+TARGET_GAIN*(produce[g]-consume[g]))) for g in range(GOODS)]

    def needs_met(self, system, levels):
        """How well the people are supplied: basics weigh most."""
        normal = self.normal[system]
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
            follow = 1-math.exp(-dt/PROSPERITY_TIME)
            station['prosperity'] += (self.needs_met(system, levels)-station['prosperity'])*follow
            low, high = POPULATION_RANGE
            station['population'] = max(low, min(high, station['population']+(station['prosperity']-.5)*2*POPULATION_DRIFT*dt))
        station['last'] = now
        return station

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
