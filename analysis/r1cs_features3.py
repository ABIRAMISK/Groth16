"""Structure features of one compiled ZoKrates circuit from out.r1cs (iden3 R1CS) and out.wtns (iden3 witness).
usage: python3 -I r1cs_features.py <folder with out.r1cs [and out.wtns]> [--check N]  -> one JSON object on stdout
Deterministic: depends only on circuit and input, never on the machine or on timings.
Window model = ark-ec 0.3.0 VariableBaseMSM, the default Groth16 backend of ZoKrates 0.8.7 (ark-groth16 0.3.0):
c = 3 if size<32 else floor(ceil(log2 size)*69/100)+2 ("ln_without_floats"+2), ceil(254/c) windows, scalar 0 skipped, scalar 1 added once in window 0,
a mixed addition per non-zero c-bit digit, bucket reduction by running sums (full addition per non-empty bucket and per index below the highest non-empty bucket),
(nwin-1)*c doublings. Vector lengths: A and B (G1 and G2): n_wires-1 (public wires included), L: n_aux, H: domain-1. Wires absent from A (B) have identity bases and cost nothing."""
import struct, sys, json, math
import numpy as np
P = 21888242871839275222246405745257275088548364400416034343698204186575808495617
PM1 = np.frombuffer((P - 1).to_bytes(32, 'little'), dtype=np.uint8)
def sections(buf, magic):
    assert buf[:4] == magic, buf[:4]
    ver, n = struct.unpack_from('<II', buf, 4); off = 12; s = {}
    for _ in range(n):
        t, sz = struct.unpack_from('<IQ', buf, off); off += 12; s[t] = (off, sz); off += sz
    return s
def bitlens(rows):
    nz = rows != 0; anynz = nz.any(axis=1)
    last = 31 - np.argmax(nz[:, ::-1], axis=1)
    top = rows[np.arange(len(rows)), last].astype(np.int64)
    bl = 8 * last + (np.floor(np.log2(np.maximum(top, 1))).astype(np.int64) + 1)
    return np.where(anynz, bl, 0)
def ark_log2(x):
    return 0 if x == 0 else ((x.bit_length() - 1) if (x & (x - 1)) == 0 else x.bit_length())
def ln_wf(a): return (ark_log2(a) * 69) // 100
def msm_stats(W, n_vec, expected_random=False):
    """W: (N,4) uint64 little-endian limbs of the scalars whose bases take part; n_vec: length of the full exponent vector (sets c)."""
    c = 3 if n_vec < 32 else ln_wf(n_vec) + 2; nwin = math.ceil(254 / c)
    zero = ~W.any(axis=1); one = (W[:, 0] == 1) & ~W[:, 1:].any(axis=1); nt = ~(zero | one); Wn = W[nt]
    mixed = int(one.sum()); full = 0; nzw = 0; mask = np.uint64((1 << c) - 1); wm = []; wf = []
    for k in range(nwin):
        sh = k * c; w = sh // 64; s = sh % 64
        d = Wn[:, w] >> np.uint64(s)
        if s + c > 64 and w + 1 < 4: d = d | (Wn[:, w + 1] << np.uint64(64 - s))
        cnt = np.bincount((d & mask).astype(np.int64), minlength=1 << c)[1:]
        nk = int(cnt.sum()); nzw += nk; fk = 0
        if nk: fk = int((cnt > 0).sum()) + int(np.max(np.nonzero(cnt)[0])) + 1
        full += fk; wm.append(nk + (int(one.sum()) if k == 0 else 0)); wf.append(fk)
    return dict(c=c, nwin=nwin, n_vec=int(n_vec), n_dens=int(len(W)), zeros=int(zero.sum()), ones=int(one.sum()), nontrivial=int(nt.sum()),
                mixed=mixed + nzw, full=full, dbl=(nwin - 1) * c, win_mixed=wm, win_full=wf)
def main(d, check=0):
    buf = open(d + '/out.r1cs', 'rb').read(); B = np.frombuffer(buf, dtype=np.uint8)
    S = sections(buf, b'r1cs'); o, _ = S[1]
    n8, = struct.unpack_from('<I', buf, o); o += 4 + n8
    nW, nPO, nPI, nPV, nL, nC = struct.unpack_from('<IIIIQI', buf, o)
    co, cs = S[2]; nlc = 3 * nC
    starts = np.empty(nlc, dtype=np.int64); cnts = np.empty(nlc, dtype=np.int64); up = struct.Struct('<I').unpack_from; off = co
    for i in range(nlc):
        n = up(buf, off)[0]; starts[i] = off + 4; cnts[i] = n; off += 4 + 36 * n
    assert off == co + cs, (off, co + cs)
    used = [np.zeros(nW, bool) for _ in range(3)]; cls = np.zeros(12, dtype=np.int64)       # per matrix: other, +1, -1, zero coefficient
    cum = np.cumsum(cnts); a = 0
    while a < nlc:
        b = int(np.searchsorted(cum, (cum[a - 1] if a else 0) + 2_000_000, side='right')); b = max(b, a + 1); b = min(b, nlc)
        c_ = cnts[a:b]; Tb = int(c_.sum())
        if Tb:
            lcix = np.repeat(np.arange(a, b), c_); first = np.cumsum(c_) - c_
            k = np.arange(Tb) - np.repeat(first, c_); ofs = starts[lcix] + 36 * k
            ids = (B[ofs].astype(np.int64) | (B[ofs + 1].astype(np.int64) << 8) | (B[ofs + 2].astype(np.int64) << 16) | (B[ofs + 3].astype(np.int64) << 24))
            coef = B[ofs[:, None] + 4 + np.arange(32)]
            is1 = (coef[:, 0] == 1) & ~coef[:, 1:].any(axis=1); ism = (coef == PM1).all(axis=1); isz = ~coef.any(axis=1)
            cl = np.where(is1, 1, np.where(ism, 2, np.where(isz, 3, 0))); mt = lcix % 3
            cls += np.bincount(mt * 4 + cl, minlength=12)
            for m in range(3): used[m][ids[mt == m]] = True
        a = b
    nnz = [int(cls[4 * m:4 * m + 4].sum()) for m in range(3)]
    n_inst = 1 + nPO + nPI; n_aux = nW - n_inst; m_dom = 1
    while m_dom < nC + n_inst: m_dom *= 2
    f = dict(n_wires=nW, n_pub_out=nPO, n_pub_in=nPI, n_prv_in=nPV, n_constraints=nC, n_instance=n_inst, n_aux=n_aux, domain=m_dom,
             nnz_A=nnz[0], nnz_B=nnz[1], nnz_C=nnz[2],
             nnz_other={m: int(cls[4 * i]) for i, m in enumerate('ABC')}, nnz_unit={m: int(cls[4 * i + 1] + cls[4 * i + 2]) for i, m in enumerate('ABC')},
             wires_in_A=int(used[0].sum()), wires_in_B=int(used[1].sum()), wires_in_C=int(used[2].sum()),
             aux_in_A=int(used[0][n_inst:].sum()), aux_in_B=int(used[1][n_inst:].sum()))
    try: wb = open(d + '/out.wtns', 'rb').read()
    except FileNotFoundError: wb = None
    if wb is not None:
        Wd = sections(wb, b'wtns'); wo, _ = Wd[1]; wn8, = struct.unpack_from('<I', wb, wo); nwit, = struct.unpack_from('<I', wb, wo + 4 + wn8)
        do, _ = Wd[2]; rows = np.frombuffer(wb, dtype=np.uint8, count=32 * nwit, offset=do).reshape(nwit, 32)
        assert nwit == nW, (nwit, nW)
        bl = bitlens(rows); aux = bl[n_inst:]
        f['aux_bitlen_hist'] = {'0': int((aux == 0).sum()), '1': int((aux == 1).sum()), '2-8': int(((aux >= 2) & (aux <= 8)).sum()),
                                '9-64': int(((aux >= 9) & (aux <= 64)).sum()), '65-200': int(((aux >= 65) & (aux <= 200)).sum()), '201-254': int((aux >= 201).sum())}
        f['aux_bitlen_mean'] = round(float(aux.mean()), 2)
        auxrows = rows[n_inst:]; uA = used[0][n_inst:]; uB = used[1][n_inst:]
        limbs = lambda r: np.ascontiguousarray(r).view('<u8').reshape(-1, 4)
        pubrows = rows[1:n_inst]; uBp = used[1][1:n_inst]; n_vecAB = nW - 1
        scA = np.concatenate([limbs(pubrows), limbs(auxrows[uA])]) if len(pubrows) else limbs(auxrows[uA])
        scB = np.concatenate([limbs(pubrows[uBp]), limbs(auxrows[uB])]) if len(pubrows) else limbs(auxrows[uB])
        msm = {'A': msm_stats(scA, n_vecAB), 'B': msm_stats(scB, n_vecAB), 'L': msm_stats(limbs(auxrows), n_aux)}
        def rand_scalars(n, seed):                                   # uniform in [0, p) up to the lowest limbs; deterministic
            rg = np.random.default_rng(seed); X = rg.integers(0, 2 ** 64, size=(n, 4), dtype=np.uint64)
            X[:, 3] = rg.integers(0, 0x30644e72e131a029, size=n, dtype=np.uint64); return X
        msm['H'] = msm_stats(rand_scalars(m_dom - 1, 12345), m_dom - 1)
        # the same three aux multiexps if every scalar were a random full-width field element (what the R1CS shape alone would predict)
        for kk, nd, sd, nv in (('A', len(scA), 1, n_vecAB), ('B', len(scB), 2, n_vecAB), ('L', n_aux, 3, n_aux)):
            msm[kk]['full_equiv'] = msm_stats(rand_scalars(nd, 1000 + sd), nv)
        f['msm'] = msm
        f['g1_mixed'] = sum(msm[k]['mixed'] for k in 'ABLH'); f['g1_full'] = sum(msm[k]['full'] for k in 'ABLH'); f['g2_mixed'] = msm['B']['mixed']; f['g2_full'] = msm['B']['full']
        if check:
            rs = np.random.default_rng(7); smp = rs.choice(nC, size=min(check, nC), replace=False); bad = 0
            def lc(i):
                n = int(cnts[i]); s = int(starts[i]); arr = B[s:s + 36 * n].reshape(n, 36)
                return [(int.from_bytes(arr[j, :4].tobytes(), 'little'), int.from_bytes(arr[j, 4:].tobytes(), 'little')) for j in range(n)]
            wv = lambda i: int.from_bytes(rows[i].tobytes(), 'little')
            for kk in smp:
                v = [sum(cf * wv(i) for i, cf in lc(3 * int(kk) + m)) % P for m in range(3)]
                bad += (v[0] * v[1] - v[2]) % P != 0
            f['check'] = dict(sampled=int(len(smp)), violated=int(bad))
    print(json.dumps(f))
if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[sys.argv.index('--check') + 1]) if '--check' in sys.argv else 0)
