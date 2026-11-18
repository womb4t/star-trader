"""One simulation run with optional constant overrides; prints a JSON line of metrics."""
import sys, json, time
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import econ_sim as E, council as C, economy as EC, market as M
players, seed, days = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
over = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
mods = dict(E=E, C=C, EC=EC, M=M)
for k, v in over.items():
    mod, name = k.split('.', 1); setattr(mods[mod], name, v)
E.WAYS_BACK.update(work_passage=True, courier=True, used_ship=3000)
t0 = time.time()
res, earned, m = E.run(days=days, players=players, adaptive=True, loans=True, quiet=True, sample=300, seed=seed)
c, b = m.state['council'], m.state['bank']; ms = b['margins']
ms = ms or [b["margin"]]
half = ms[len(ms)//2:]
tl = m.treasury_log
out = dict(players=players, seed=seed, days=days, secs=round(time.time()-t0),
    earned=round(earned), dead={k: round(r['dead'], 4) for k, r in res.items()},
    worst=max(r['dead'] for r in res.values()),
    margin_end=ms[-1], margin_half_lo=min(half), margin_half_hi=max(half),
    interest=round(b['interest']), losses=round(b['losses']), loss_events=b.get('events', [])[:20],
    use=round(b['use'], 3), lent=round(b['lent']), capacity=round(b['capacity']),
    treasury_end=round(c['treasury']), target_end=round(c.get('target', 0)),
    treasury_max=round(max(x[1] for x in tl)), treasury_min=round(min(x[1] for x in tl)),
    treasury_series=[round(x[1]) for x in tl[::288]], target_series=[round(x[2]) for x in tl[::288]],
    spent={k: round(v) for k, v in c['spent'].items()}, fund=round(c.get('fund', 0)), base_tax=c.get('base_tax'), expected_loss=b.get('expected_loss'), premium=b.get('premium'), refusals={k: sum(x.refusals[k] for x in m.crew) for k in set().union(*[x.refusals for x in m.crew])}, house=round(c['house']),
    tax=sorted(set(round(v, 3) for v in c['tax'].values())), rate=c['rate'], rate_lo=min(m.rates), rate_hi=max(m.rates),
    decrees=[d.get('text', d['kind']) for d in c['decrees']], grants=sum(1 for d in c['decrees'] if d['kind'] == 'grant'),
    wiped=sum(x.wipeouts for x in m.crew), repossessed=sum(x.defaults for x in m.crew),
    borrowed=round(sum(x.borrowed for x in m.crew)), debt_end=round(sum(x.debt for x in m.crew)),
    lost_ships=sum(x.lost_ships for x in m.crew), population=round(sum(v["population"] for v in m.state["stations"].values()), 2), use_max=round(max(b.get("use_log", [b["use"]])), 3))
print(json.dumps(out))
