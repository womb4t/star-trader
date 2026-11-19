"""The Galactic Council: reviews every world's trade and steps in where a world can't make a living.

It has three tools, and a budget:
  * Trade tax, per world, on every purchase and sale at the exchange. Struggling worlds get cuts to
    draw traders in; busy, safe worlds pay more (lawless worlds collect none). Tax fills the treasury.
  * The galactic interest rate. Cheap money speeds up building new industry (economy.investment);
    the Council raises the rate when shortages push prices up across the galaxy and cuts it when
    worlds stagnate. The same rate prices the bank's loans.
  * Decrees, paid from the treasury: a licence for a new industry where a world has too few
    profitable exports (chosen from what its neighbours pay most for), and relief convoys of food
    and medicine where people are going without. At most one decree per world per COOLDOWN.
Nothing happens in the first WARM_UP, while prices settle. Everything is kept in the market state,
so every commander sees the same tax, rate and decrees (and a guide can report them).
"""
import economy as E

REVIEW_EVERY = 6*E.HOUR
WARM_UP = 12*E.HOUR
COOLDOWN = 24*E.HOUR
MIN_EXPORTS = 2
SPREAD = .08          # the exchange's buy/sell spread each way
WORTH_IT = 1.10       # a trade is worth a commander's while at 10% over spreads and tax
NEW_LINE = .5         # a licensed industry starts at half a typical factory
RELIEF = (E.FOOD, E.MEDICINE)
KEEP = 60             # decrees remembered
TAX_RANGE = (0., .10)
TAX_START = {'Anarchy': 0., 'Feudal': 0.}   # everyone else starts at DEFAULT_TAX
DEFAULT_TAX = .04
TAX_STEP = .01
RATE_RANGE = (.005, .15)
RATE_STEP = .005
LICENCE_COST = 2500.
RELIEF_COST = 3000.
START_TREASURY = 20000.
# The budget, per review (6 hours), scaled by each world's population:
UPKEEP = 400.        # running the station: docks, life support, the exchange
POLICE_FULL = 1000.   # police spending that makes a world as safe as it gets
SAFEST = .85          # the share of piracy risk full policing removes
RISK = .02            # chance a cargo run through unpoliced lawful space is lost
LAWLESS_RISK = .05    # and through lawless space
# How safe each kind of government keeps its space (share of POLICE_FULL it funds), whatever the tax.
SAFETY_TARGET = {'Dictatorship': .9, 'Communist': .85, 'Corporate state': .8, 'Confederacy': .7, 'Democracy': .75}
RESERVE_REVIEWS = 4   # the treasury aims to hold a day of spending
HOUSE_SHARE = .10     # the house's cut of every tax credit (Kenton's bank)
# Fiscal rule: one tax rate for every lawful world (struggling worlds get a discount), steered each review
# towards a treasury of RESERVE_AIM x the reserve target, like a central bank's feedback rule.
RESERVE_AIM = 1.5
TAX_GAIN = .01        # tax change per review for a gap of one reserve target (limited to TAX_STEP)
STRUGGLING_DISCOUNT = .02
# Development (cohesion) fund: a share of all tax, plus anything over SURPLUS x the reserve target,
# is set aside and spent as grants on the weakest worlds, where transfers do most good.
DEV_SHARE = .15
SURPLUS = 3
GRANT_COST = 8000.
GRANT_SKILL = .10     # a grant lifts a licensed line's efficiency by this much (up to economy.LEARNED+.05)...
GRANT_CAPACITY = .25  # ...or, where there is none to lift, adds this much capacity to the world's best export line
WEAK = MIN_EXPORTS+1  # worlds with this few worthwhile exports or fewer can get grants
# Infrastructure: a hyperspace beacon cuts the fuel for jumps to and from a world, bringing more markets in
# reach; built from the treasury's surplus for a world weak for a day, where it would open new routes.
BEACON_COST = 50000.
BEACON_SAVING = .10
BEACON_WEAK_REVIEWS = 4
FUND_CAP = 8*GRANT_COST   # what the fund can't spend goes back to the treasury (and so to lower tax)
DIVERSIFY = False     # grants fund a promising new line first (industrial policy), then efficiency, then capacity
TAYLOR_PRICES = .5    # rate rise per unit of inflation (prices up 4% in a day: 2 points on the rate)


def council_state(market, now):
    state = market.state.setdefault('council', {})
    state.setdefault('started', now)
    state.setdefault('window', None)
    state.setdefault('decrees', [])
    state.setdefault('last', {})
    state.setdefault('rate', E.BASE_INTEREST)
    state.setdefault('treasury', START_TREASURY)
    state.setdefault('tax', {str(i): TAX_START.get(p['government'], DEFAULT_TAX) for i, p in enumerate(market.profiles)})
    state.setdefault('safety', {str(i): 0. for i in range(len(market.profiles))})
    state.setdefault('house', 0.)
    state.setdefault('house_share', HOUSE_SHARE)
    state.setdefault('spent', dict(upkeep=0., police=0., licences=0., relief=0., grants=0.))
    state.setdefault('fund', 0.)
    state.setdefault('base_tax', DEFAULT_TAX)
    return state


def risk(market, system):
    """Chance a cargo run touching this world is lost to pirates: police make lawful worlds safer."""
    if market.profiles[system]['government'] in E.LAWLESS: return LAWLESS_RISK
    safety = market.state.get('council', {}).get('safety', {}).get(str(system), 0.)
    return RISK*(1-safety)


def exports(market, system, neighbours, contraband=()):
    """Legal goods this world makes that sell somewhere in range for a worthwhile profit after tax."""
    station = market.economy.station(system, market.economy.state['stations'].get(str(system), {}).get('last', 0))
    out = []
    for g, capacity in enumerate(market.economy.industry(system, station)):
        if capacity < .2 or g in contraband: continue
        buy = market.price(system, g)*(1+SPREAD+market.tax(system))
        sell = max(market.price(j, g)*(1-SPREAD-market.tax(j)) for j in neighbours[system])
        if sell >= buy*WORTH_IT: out.append(g)
    return out


def collect(market, system, value):
    """Tax on a trade worth `value` credits at this station goes to the treasury."""
    state = market.state.get('council')
    if state: state['treasury'] += value*market.tax(system)


def review(market, now, neighbours, contraband=(), names=None, goods=None):
    state = council_state(market, now)
    window = int(now//REVIEW_EVERY)
    if state['window'] == window or now-state['started'] < WARM_UP: return []
    state['window'] = window
    economy, made = market.economy, []
    legal = [g for g in range(len(market.stock[0])) if g not in contraband]

    # Interest rate: shortages everywhere mean an overheated economy; many idle worlds mean stagnation.
    pressure = sum(E.scarcity(market.levels[i][g], market.normal[i][g]) for i in range(len(market.stock)) for g in legal)
    pressure /= len(market.stock)*len(legal)
    counts = {i: len(exports(market, i, neighbours, contraband)) for i in range(len(market.stock))}
    struggling = sum(1 for n in counts.values() if n < MIN_EXPORTS)
    lo, hi = RATE_RANGE
    lending = market.state.get('bank', {}).get('use', 0.)       # how much of the banks' capacity is lent out
    # A Taylor rule: the neutral rate, plus more for inflation (less in deflation), plus more if credit runs
    # short; approached a step per review (gradualism). Money works through demand (economy.spending) and
    # investment. Struggling worlds are the treasury's job (tax discounts, grants), not the rate's: cutting
    # the rate for them builds factories everywhere and deepens the gluts that leave them without trade.
    slack = sum(max(0, WEAK-n) for n in counts.values())/(WEAK*len(counts))
    # Inflation: how far a galactic price index (every legal good everywhere, against its base) moved in a day.
    index = sum(market.price(i, g)/max(1e-9, market.static_price(i, g)) for i in range(len(market.stock)) for g in legal)
    index /= len(market.stock)*len(legal)
    log = [(t, x) for t, x in state.get('index_log', []) if now-t <= (24*E.HOUR)+REVIEW_EVERY]+[(now, index)]
    state['index_log'] = log
    inflation = index/log[0][1]-1 if now-log[0][0] >= (24*E.HOUR)/2 else 0.
    state['inflation'] = inflation
    aim = E.BASE_INTEREST+TAYLOR_PRICES*inflation+(.02 if lending > .85 else 0.)
    aim = max(lo, min(hi, aim))
    state['rate_aim'], state['pressure'], state['slack'] = aim, pressure, slack
    state['rate'] += max(-RATE_STEP, min(RATE_STEP, aim-state['rate']))

    # The budget: every world's upkeep, and police wherever there is law, before anything else.
    spend = 0.
    for system in range(len(market.stock)):
        key, depth = str(system), market.depth(system)
        upkeep = UPKEEP*depth
        lawless = market.profiles[system]['government'] in E.LAWLESS
        police = 0. if lawless else POLICE_FULL*depth*SAFETY_TARGET.get(market.profiles[system]['government'], .75)
        cost = upkeep+police
        if state['treasury'] < cost:   # can't pay in full: police are cut first
            police = max(0., state['treasury']-upkeep); cost = upkeep+police
        state['treasury'] -= cost; spend += cost
        state['spent']['upkeep'] += upkeep; state['spent']['police'] += police
        state['safety'][key] = 0. if lawless else SAFEST*min(1., police/(POLICE_FULL*depth))
    # Development fund: its share of the tax taken since the last review, and any surplus over the ceiling.
    target = RESERVE_REVIEWS*spend
    state['target'] = target
    revenue = state.get('revenue', 0.)-state.get('revenue_seen', 0.); state['revenue_seen'] = state.get('revenue', 0.)
    put = DEV_SHARE*max(0., revenue)+max(0., state['treasury']-SURPLUS*target)
    put = max(0., min(put, state['treasury'], FUND_CAP-state.get('fund', 0.)))
    state['treasury'] -= put; state['fund'] = state.get('fund', 0.)+put
    # Fiscal rule: steer the tax rate towards the reserve aim.
    tlo, thi = TAX_RANGE
    base = state.get('base_tax', DEFAULT_TAX)
    base += max(-TAX_STEP, min(TAX_STEP, TAX_GAIN*(RESERVE_AIM*target-state['treasury'])/max(1., target)))
    state['base_tax'] = base = max(tlo, min(thi, base))
    for system in range(len(market.stock)):
        key = str(system)
        if market.profiles[system]['government'] in E.LAWLESS: state['tax'][key] = 0.; continue
        state['tax'][key] = max(tlo, base-(STRUGGLING_DISCOUNT if counts[system] < MIN_EXPORTS else 0.))

    for system in range(len(market.stock)):
        key = str(system)

        if now-state['last'].get(key, -1e18) < COOLDOWN: continue
        station = economy.station(system, now)
        decree = None
        if station['prosperity'] < .35 and state['treasury'] >= RELIEF_COST:
            for g in RELIEF: market.change(system, g, market.normal[system][g]*.5)
            state['treasury'] -= RELIEF_COST; state['spent']['relief'] += RELIEF_COST
            decree = dict(kind='relief', good=None)
        elif counts[system] < MIN_EXPORTS and state['treasury'] >= LICENCE_COST:
            industry = economy.industry(system, station)
            choice = new_line(market, system, station, neighbours, legal)
            if choice is not None:
                industry[choice] = max(industry[choice], NEW_LINE)
                state['treasury'] -= LICENCE_COST; state['spent']['licences'] += LICENCE_COST
                decree = dict(kind='industry', good=choice)
        if decree: record(state, decree, system, now, names, goods, made)
    # Infrastructure: a beacon for a world that has been weak for a day, if it would open new routes.
    weak = state.setdefault('weak_streak', {})
    for system in range(len(market.stock)):
        key = str(system)
        weak[key] = weak.get(key, 0)+1 if counts[system] <= WEAK else 0
    beacons = state.setdefault('beacons', [])
    reach = getattr(market, 'reach', None)
    if reach and state['treasury']-BEACON_COST >= RESERVE_AIM*target:
        import econ_sim
        for system in sorted(range(len(market.stock)), key=lambda i: (counts[i], -weak[str(i)])):
            if system in beacons or weak[str(system)] < BEACON_WEAK_REVIEWS: continue
            if not set(econ_sim.in_range(system, beacons+[system]))-set(neighbours[system]): continue   # nothing new in reach
            beacons.append(system); reach(beacons)
            state['treasury'] -= BEACON_COST; state['spent']['beacons'] = state['spent'].get('beacons', 0.)+BEACON_COST
            record(state, dict(kind='beacon', good=None), system, now, names, goods, made)
            break
    # Grants from the development fund, weakest worlds first (their own cooldown, apart from decrees).
    for system in sorted(range(len(market.stock)), key=lambda i: (counts[i], economy.station(i, now)['prosperity'])):
        key = 'grant:'+str(system)
        if state.get('fund', 0.) < GRANT_COST or counts[system] > WEAK: continue
        if now-state['last'].get(key, -1e18) < COOLDOWN: continue
        station = economy.station(system, now)
        industry, kind = economy.industry(system, station), market.profiles[system]['economy']
        skill = station.setdefault('skill', [E.OFF_SPECIALITY]*len(industry))
        lines = [g for g in legal if industry[g] >= .2 and g not in E.NATIVE[kind] and skill[g] < E.LEARNED+.05]
        fresh = new_line(market, system, station, neighbours, legal) if DIVERSIFY else None
        if fresh is not None:   # diversify: a new line in something the neighbours pay well for
            g = fresh
            industry[g] = max(industry[g], NEW_LINE)
        elif lines:   # make a licensed line competitive
            g = max(lines, key=lambda g: industry[g])
            skill[g] = min(E.LEARNED+.05, skill[g]+GRANT_SKILL)
        else:       # a capital grant to the line whose goods fetch most next door, for what they cost here
            lines = [g for g in legal if industry[g] >= .2 and industry[g] < E.INDUSTRY_RANGE[1]]
            if not lines: continue
            g = max(lines, key=lambda g: max(market.price(j, g) for j in neighbours[system])/market.price(system, g))
            industry[g] = min(E.INDUSTRY_RANGE[1], industry[g]+GRANT_CAPACITY)
        state['fund'] -= GRANT_COST; state['spent']['grants'] = state['spent'].get('grants', 0.)+GRANT_COST
        state['last'][key] = now
        record(state, dict(kind='grant', good=g), system, now, names, goods, made)
    return made


def new_line(market, system, station, neighbours, legal, best=1.15):
    """The good this world doesn't make that would pay best: what it fetches next door against what it
    would cost to make here (None if nothing clears `best`)."""
    economy, kind = market.economy, market.profiles[system]['economy']
    industry, choice = economy.industry(system, station), None
    for g in legal:
        if industry[g] >= .2: continue
        here = market.price(system, g)/max(.5, economy.price_adjust(system, g))*.8/E.productivity(kind, g, station)
        there = max(market.price(j, g) for j in neighbours[system])
        if there/here > best: best, choice = there/here, g
    return choice


def record(state, decree, system, now, names, goods, made):
    """Log a decree (with its news line) in the Council's record."""
    decree.update(system=system, at=now)
    if names and goods:
        world, good = names[system], goods[decree['good']] if decree.get('good') is not None else ''
        decree['text'] = {'relief': f'Relief convoy sent to {world}',
                          'beacon': f'Council builds a hyperspace beacon at {world}',
                          'grant': f"Council funds {world}'s {good.lower()} industry",
                          'industry': f'{world} licensed to produce {good}'}[decree['kind']]
    state['decrees'] = (state['decrees']+[decree])[-KEEP:]
    if decree['kind'] != 'grant': state['last'][str(system)] = now
    made.append(decree)
