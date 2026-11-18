#!/usr/bin/env python3
"""Extract the per-phase timings of generate-proof from raw_run.log of a run_phases.sh run.
usage: python phases_extract.py <phases_folder>
Writes <folder>/phases.csv (one row per circuit, replicate and phase) and prints, per circuit, the median over the measured
replicates (replicate 0 is the warm-up) of the proving time, the share of each group of phases and how much of the time the phases cover."""
import sys, os, re, csv, statistics as st
ARK = {'front-end': ['g16.synthesis', 'g16.finalize', 'wm.to_matrices'], 'evaluation': ['wm.eval_ab', 'wm.eval_c'],
       'FFT': ['wm.fft_ab', 'wm.fft_c_and_h'], 'MSM': ['g16.msm_h', 'g16.msm_l', 'g16.msm_a', 'g16.msm_b_g1', 'g16.msm_b_g2'],
       'I/O': ['cli.witness_read', 'zok.public_inputs', 'zok.pk_deserialize']}
ARK_LEAVES = sum(ARK.values(), []) + ['wm.alloc_assignment', 'g16.h_to_repr', 'g16.aux_to_repr', 'g16.misc_before_a']
# bellman builds the constraint system and evaluates it in one pass (bm.synthesis) and runs its multi-scalar
# multiplications concurrently, so they are timed together (bm.msm_all); it also verifies its own proof (zok.self_verify).
BELLMAN = {'front-end': ['bm.synthesis'], 'evaluation': [], 'FFT': ['bm.fft'], 'MSM': ['bm.msm_all'],
           'I/O': ['cli.witness_read', 'zok.pk_deserialize']}
BELLMAN_LEAVES = sum(BELLMAN.values(), []) + ['bm.h_to_repr', 'zok.self_verify']
# cached-matrix prover: the front end is reading the stored matrices and building the assignment
FAST = {'front-end': ['fast.load_matrices', 'fast.assignment'], 'evaluation': ['wm.eval_ab', 'wm.eval_c'],
        'FFT': ['wm.fft_ab', 'wm.fft_c_and_h'], 'MSM': ['g16.msm_h', 'g16.msm_l', 'g16.msm_a', 'g16.msm_b_g1', 'g16.msm_b_g2'],
        'I/O': ['cli.witness_read', 'zok.public_inputs', 'zok.pk_deserialize']}
FAST_LEAVES = sum(FAST.values(), []) + ['g16.h_to_repr', 'g16.aux_to_repr', 'g16.misc_before_a']
def main(folder):
    rows, cur, order = [], None, []
    head = re.compile(r'^\[(\w+) pass (-?\d+), circuit \d+/\d+, elapsed [^\]]*\] (\S+):')
    proof = re.compile(r'^\s+--- proof: host ([0-9.]+) s, inside ([0-9.]*) s')
    zkt = re.compile(r'^\s+ZKT (\S+) ([0-9.]+)\s*$')
    with open(os.path.join(folder, 'raw_run.log'), errors='replace') as f:
        for line in f:
            line = line.rstrip('\r\n')
            m = head.match(line)
            if m: cur = (m.group(3), int(m.group(2)), m.group(1)); continue
            if cur is None: continue
            m = proof.match(line)
            if m and m.group(2): rows.append((cur[0], cur[1], 'inner.generate_proof', float(m.group(2)))); continue
            m = zkt.match(line)
            if m: rows.append((cur[0], cur[1], m.group(1), float(m.group(2))))
    with open(os.path.join(folder, 'phases.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['circuit', 'replicate', 'phase', 'seconds']); w.writerows(rows)
    data = {}
    for cid, rep, ph, v in rows:
        if cid not in data: order.append(cid)
        data.setdefault(cid, {}).setdefault(ph, {})[rep] = v
    print('%-18s %4s %9s | %9s %10s %6s %6s %6s | %8s' % ('circuit', 'reps', 'proof_s', 'front-end', 'evaluation', 'FFT', 'MSM', 'I/O', 'covered'))
    for cid in order:
        d = data[cid]; tot = d.get('inner.generate_proof', {})
        GROUPS, LEAVES = (BELLMAN, BELLMAN_LEAVES) if 'bm.synthesis' in d else (FAST, FAST_LEAVES) if 'fast.load_matrices' in d else (ARK, ARK_LEAVES)
        reps = [r for r in tot if r >= 1 and all(r in d.get(x, {}) for x in LEAVES)] or [r for r in tot if all(r in d.get(x, {}) for x in LEAVES)]
        if not reps: print('%-18s no complete replicate' % cid); continue
        w = st.median(tot[r] for r in reps)
        sh = {g: st.median(sum(d[x][r] for x in v) / tot[r] for r in reps) for g, v in GROUPS.items()}
        cov = st.median(sum(d[x][r] for x in LEAVES) / tot[r] for r in reps)
        print('%-18s %4d %9.3f | %8.1f%% %9.1f%% %5.1f%% %5.1f%% %5.1f%% | %7.1f%%' % (cid, len(reps), w, 100*sh['front-end'], 100*sh['evaluation'], 100*sh['FFT'], 100*sh['MSM'], 100*sh['I/O'], 100*cov))
    print('rows written to', os.path.join(folder, 'phases.csv'))
if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
