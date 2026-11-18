"""Run 2/8/16 commanders x seeds in parallel and judge every economy test.
usage: python3 sim/matrix.py TAG DAYS [JSON overrides, e.g. {\"C.DEV_SHARE\": .2}] [seeds, e.g. final,b]"""
import sys, json, subprocess, os
S = os.path.dirname(os.path.abspath(__file__))
import tempfile; RUNS = os.environ.get('SIM_RUNS', tempfile.mkdtemp(prefix='econ-runs-'))
tag, days = sys.argv[1], sys.argv[2]
over = sys.argv[3] if len(sys.argv) > 3 else '{}'
seeds = sys.argv[4].split(',') if len(sys.argv) > 4 else ['final', 'b']
cwd = os.path.dirname(S)
procs = {}
for seed in seeds:
    for p in (2, 8, 16):
        f = open(f'{RUNS}/{tag}-{p}-{seed}.json', 'w')
        procs[(p, seed)] = (subprocess.Popen(['python3', f'{S}/one_run.py', str(p), seed, days, over], cwd=cwd, stdout=f, stderr=subprocess.STDOUT), f)
R = {}
for k, (pr, f) in procs.items():
    pr.wait(); f.close()
    try: R[k] = json.load(open(f.name))
    except Exception: print('FAILED', k, open(f.name).read()[-2000:]); sys.exit(1)
fails = []
def check(name, ok, detail): print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail); ok or fails.append(name)
for seed in seeds:
    print(f'--- seed {seed}')
    for p in (2, 8, 16):
        r = R[(p, seed)]
        worst = max(r['dead'], key=r['dead'].get)
        print(f'  {p:2} cmdrs: {r["earned"]:,} cr/h | worst {worst} {r["worst"]:.1%} | bank margin end {r["margin_end"]:.2%} (2nd half {r["margin_half_lo"]:.2%}-{r["margin_half_hi"]:.2%}) EL {r["expected_loss"] or 0:.2%} prem {r["premium"] or 0:.2%} | interest {r["interest"]:,} losses {r["losses"]:,} | treasury {r["treasury_end"]:,} target {r["target_end"]:,} max {r["treasury_max"]:,} fund {r["fund"]:,} grants {r["grants"]} spent {r["spent"].get("grants",0):,} | tax {r["base_tax"]:.3f} | rate {r["rate"]:.3f} | wiped {r["wiped"]} repo {r["repossessed"]} | {r["secs"]}s')
        check(f'{p}/{seed} dead<5%', r['worst'] < .05, f'{worst} {r["worst"]:.1%}')
        check(f'{p}/{seed} bank profitable', r['interest'] > r['losses'], f'{r["interest"]:,} vs {r["losses"]:,}')
        check(f'{p}/{seed} margin stable', r['margin_half_hi']-r['margin_half_lo'] <= .015 and .01 <= r['margin_end'] <= .08, f'{r["margin_half_lo"]:.2%}-{r["margin_half_hi"]:.2%}, end {r["margin_end"]:.2%}')
        ser, tgt = r['treasury_series'], r['target_series']
        late = [a/max(1, b) for a, b in zip(ser[len(ser)//2:], tgt[len(tgt)//2:])]
        check(f'{p}/{seed} treasury not hoarded', max(late) <= 3.5 and r['fund'] <= 4*8000, f'late treasury/target max {max(late):.1f}, fund {r["fund"]:,}')
        check(f'{p}/{seed} treasury solvent', r['treasury_min'] >= 0 and min(late) >= .5, f'min {r["treasury_min"]:,}, late min ratio {min(late):.2f}')
        check(f'{p}/{seed} surplus spent on grants', r['grants'] > 0 or r['treasury_max'] < 3*r['target_end'], f'{r["grants"]} grants')
    e8, e16 = R[(8, seed)]['earned'], R[(16, seed)]['earned']
    p8, p16, p2 = R[(8, seed)]['population'], R[(16, seed)]['population'], R[(2, seed)]['population']
    check(f'{seed} population scales with players', p16 >= 1.2*p8 and p8 >= 1.2*p2, f'{p2} / {p8} / {p16}')
    check(f'{seed} earnings hold at 16', e16 >= .75*e8 and e16 >= 3000, f'{e16:,} vs {e8:,} at 8')
print(f'{len(fails)} failed: {fails}')
