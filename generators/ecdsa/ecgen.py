"""Generator and witness builder for an ECDSA-secp256k1 verifier in ZoKrates 0.8.7 (Groth16 / BN254).

The circuit and its witness are produced by ONE program (a tracer): every gadget call computes its witness values
from concrete numbers and, at the same time, emits the matching ZoKrates call. The ZoKrates text therefore does
not depend on the signature being verified; only the witness vector does.

Non-native arithmetic: an element of F_p (or of Z_n) is K = 5 limbs of 60, 60, 60, 60 and 16 bits, each limb a
BN254 scalar-field element. A modular identity  E0 = 0 (mod m)  is checked as  E0 + S0*m = q*m  over the integers:
limb products are formed in the field, q is supplied by the prover and range-checked, and a carry chain with
range-checked carries (one carry per GRP = 3 limb positions) proves the integer polynomial identity. Every bound
used to rule out wrap-around is computed below (interval arithmetic) and asserted.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ecref as E

RBN = 21888242871839275222246405745257275088548364400416034343698204186575808495617  # BN254 scalar field
W = 60                               # limb size in bits
K = 5                                # limbs per element (4 * 60 + 16 = 256 bits)
GRP = 3                              # one range-checked carry per GRP limb positions
NP = 2 * K - 1                       # coefficient positions of a product
BASE = 1 << W
MASK = BASE - 1
BASEG = BASE ** GRP
INV_BASE = pow(BASE, -1, RBN)
INV_BASEG = pow(BASEG, -1, RBN)
P = E.p
N = E.n
TOP_BITS = 256 - W * (K - 1)         # width of the top limb of a 256-bit element (16)
TOPMAX = (1 << TOP_BITS) - 1
LIM_MAX = [MASK] * (K - 1) + [TOPMAX]
SALT_D = b"zkp-ecdsa-secp256k1/offset-D/v1"
LIMIT = 1 << 251                     # every integer that is compared through the field must stay below this


class Exceptional(Exception):
    """An exceptional case of the incomplete addition (x1 == x2, or a point that cannot be encoded)."""


def limbs(x):
    return [(x >> (W * i)) & MASK for i in range(K - 1)] + [x >> (W * (K - 1))]


# ----------------------------------------------------------------------------------------------------------------
# range checks: one generated function per width
# ----------------------------------------------------------------------------------------------------------------
RCSET = set()


def rcn(L):
    RCSET.add(L)
    return f"rc{L}"


def zok_rc(L):
    flat = " + ".join(f"(b[{i}] ? {2 ** (L - 1 - i)} : 0)" for i in range(L))
    return (f"def rc{L}(field x) -> field {{\n    bool[{L}] b = unpack_e(x);\n    assert({flat} == x);\n    return x;\n}}")


# ----------------------------------------------------------------------------------------------------------------
# linear forms over named ZoKrates variables
# ----------------------------------------------------------------------------------------------------------------
def lin_code(terms, const=0):
    parts = []
    for c, a in terms:
        if c == 0:
            continue
        ac = abs(c)
        parts.append((c > 0, a if ac == 1 else f"{ac} * {a}"))
    if const != 0:
        parts.append((const > 0, str(abs(const))))
    if not parts:
        return "0"
    s = ""
    for i, (pos, txt) in enumerate(parts):
        if i == 0:
            s = txt if pos else f"0 - {txt}"
        else:
            s += (" + " if pos else " - ") + txt
    return s


class LF:
    __slots__ = ("t", "c")

    def __init__(self, t=None, c=0):
        self.t = {k: v for k, v in (t or {}).items() if v != 0}
        self.c = c

    def __add__(self, o):
        if isinstance(o, int):
            return LF(self.t, self.c + o)
        t = dict(self.t)
        for k, v in o.t.items():
            t[k] = t.get(k, 0) + v
        return LF(t, self.c + o.c)

    __radd__ = __add__

    def __neg__(self):
        return LF({k: -v for k, v in self.t.items()}, -self.c)

    def __sub__(self, o):
        return self + (-o)

    def val(self, env):
        return sum(v * env[k] for k, v in self.t.items()) + self.c

    def interval(self, rng):
        lo = hi = self.c
        for k, v in self.t.items():
            a, b = rng[k]
            if v >= 0:
                lo += v * a
                hi += v * b
            else:
                lo += v * b
                hi += v * a
        return lo, hi

    def code(self):
        return lin_code([(v, k) for k, v in self.t.items()], self.c)


def fe_var(name, off=0):
    return [LF({f"{name}[{i + off}]": 1}) for i in range(K)]


def fe_const(v):
    return [LF({}, l) for l in limbs(v)]


def fe_sub(a, b):
    return [a[i] - b[i] for i in range(K)]


def fe_vinterval(fe, rng):
    lo = hi = 0
    for i in range(K):
        a, b = fe[i].interval(rng)
        lo += a * BASE ** i
        hi += b * BASE ** i
    return lo, hi


def imul(x, y):
    c = [x[0] * y[0], x[0] * y[1], x[1] * y[0], x[1] * y[1]]
    return min(c), max(c)


def rng_fe(name, off=0):
    return {f"{name}[{off + i}]": (0, LIM_MAX[i]) for i in range(K)}


def env_fe(name, v, off=0):
    l = limbs(v)
    return {f"{name}[{off + i}]": l[i] for i in range(K)}


def env_pt(name, Pt):
    d = env_fe(name, Pt[0], 0)
    d.update(env_fe(name, Pt[1], K))
    return d


def rng_pt(name):
    d = rng_fe(name, 0)
    d.update(rng_fe(name, K))
    return d


# ----------------------------------------------------------------------------------------------------------------
# one modular identity  sum(coef * A * B) + sum(coef * A)  =  0  (mod m)
# ----------------------------------------------------------------------------------------------------------------
class Ident:
    def __init__(self, name, mod, terms, qname, rng):
        self.name, self.mod, self.terms, self.qn = name, mod, terms, qname
        self.m = limbs(mod)
        lo = hi = 0
        for coef, A, Bf in terms:
            va = fe_vinterval(A, rng)
            v = va if Bf is None else imul(va, va if Bf is A else fe_vinterval(Bf, rng))
            a, b = v[0] * coef, v[1] * coef
            lo += min(a, b)
            hi += max(a, b)
        qmin = lo // mod
        qmax = -((-hi) // mod)
        self.S0 = max(0, -qmin)
        self.qbits_total = max(1, (qmax + self.S0).bit_length())
        assert self.qbits_total > W * (K - 1)
        self.qtop = self.qbits_total - W * (K - 1)
        self.rng = dict(rng)
        for i in range(K - 1):
            self.rng[f"{qname}[{i}]"] = (0, MASK)
        self.rng[f"{qname}[{K - 1}]"] = (0, (1 << self.qtop) - 1)
        self.Sl = limbs(self.S0)
        self.const = [sum(self.Sl[i] * self.m[k - i] for i in range(K) if 0 <= k - i < K) for k in range(NP)]
        clo, chi = [0] * NP, [0] * NP
        for coef, A, Bf in terms:
            if Bf is None:
                for i in range(K):
                    a, b = A[i].interval(self.rng)
                    a, b = a * coef, b * coef
                    clo[i] += min(a, b)
                    chi[i] += max(a, b)
            else:
                sq = A is Bf
                for i in range(K):
                    for j in range(K):
                        if sq and j < i:
                            continue
                        mult = coef * (2 if (sq and i != j) else 1)
                        iv = imul(A[i].interval(self.rng), Bf[j].interval(self.rng))
                        a, b = iv[0] * mult, iv[1] * mult
                        clo[i + j] += min(a, b)
                        chi[i + j] += max(a, b)
        for k in range(NP):
            clo[k] += self.const[k]
            chi[k] += self.const[k]
            for i in range(K):
                j = k - i
                if 0 <= j < K:
                    qa, qb = self.rng[f"{qname}[{i}]"]
                    clo[k] -= self.m[j] * qb
                    chi[k] -= self.m[j] * qa
        self.clo, self.chi = clo, chi
        self.ngroups = (NP + GRP - 1) // GRP
        self.cb, self.carry_bounds, self.worst = [], [], 0
        cl = ch = 0
        for j in range(self.ngroups):
            ks = range(GRP * j, min(NP, GRP * (j + 1)))
            slo = sum(clo[k] * BASE ** (k - GRP * j) for k in ks)
            shi = sum(chi[k] * BASE ** (k - GRP * j) for k in ks)
            if j < self.ngroups - 1:
                lo_c = -((-(slo + cl)) // BASEG)
                hi_c = (shi + ch) // BASEG
                cb = max((-lo_c).bit_length() if lo_c < 0 else 0, hi_c.bit_length() if hi_c > 0 else 0) + 1
                big = max(abs(slo + cl), abs(shi + ch), (1 << (cb - 1)) * BASEG)
                self.worst = max(self.worst, big)
                assert big < LIMIT, f"{name}: carry analysis would wrap ({big.bit_length()} bits)"
                self.cb.append(cb)
                self.carry_bounds.append((lo_c, hi_c))
                cl, ch = lo_c, hi_c
            else:
                big = max(abs(slo + cl), abs(shi + ch))
                self.worst = max(self.worst, big)
                assert big < LIMIT

    # ---- ZoKrates code ----
    def emit(self, ind="    "):
        L = []
        n_ = self.name
        pk = {k: [] for k in range(NP)}
        for ti, (coef, A, Bf) in enumerate(self.terms):
            if Bf is None:
                for i in range(K):
                    pk[i].append((coef, f"({A[i].code()})"))
            else:
                sq = A is Bf
                for i in range(K):
                    for j in range(K):
                        if sq and j < i:
                            continue
                        mult = coef * (2 if (sq and i != j) else 1)
                        nm = f"m_{n_}_{ti}_{i}_{j}"
                        L.append(f"field {nm} = ({A[i].code()}) * ({Bf[j].code()});")
                        pk[i + j].append((mult, nm))
        for k in range(NP):
            terms = list(pk[k])
            for i in range(K):
                j = k - i
                if 0 <= j < K and self.m[j] != 0:
                    terms.append((-self.m[j], f"{self.qn}[{i}]"))
            L.append(f"field {n_}c{k} = {lin_code(terms, self.const[k])};")
        for j in range(self.ngroups):
            ks = list(range(GRP * j, min(NP, GRP * (j + 1))))
            terms = [(BASE ** (k - GRP * j), f"{n_}c{k}") for k in ks]
            if j > 0:
                terms.append((1, f"{n_}k{j - 1}"))
            L.append(f"field {n_}s{j} = {lin_code(terms)};")
            if j < self.ngroups - 1:
                off = 1 << (self.cb[j] - 1)
                L.append(f"field {n_}t{j} = {n_}s{j} * INVG;")
                L.append(f"field {n_}k{j} = {rcn(self.cb[j])}({n_}t{j} + {off}) - {off};")
            else:
                L.append(f"assert({n_}s{j} == 0);")
        return "\n".join(ind + l for l in L)

    # ---- witness ----
    def eval(self, env):
        c = [0] * NP
        for coef, A, Bf in self.terms:
            if Bf is None:
                for i in range(K):
                    c[i] += coef * A[i].val(env)
            else:
                Av = [A[i].val(env) for i in range(K)]
                Bv = [Bf[j].val(env) for j in range(K)]
                for i in range(K):
                    for j in range(K):
                        c[i + j] += coef * Av[i] * Bv[j]
        E0 = sum(c[k] * BASE ** k for k in range(NP))
        if E0 % self.mod != 0:
            raise AssertionError(f"identity {self.name} does not hold")
        q = E0 // self.mod + self.S0
        if not (0 <= q < (1 << self.qbits_total)):
            raise AssertionError(f"identity {self.name}: quotient out of range")
        ql = limbs(q)
        assert ql[K - 1] < (1 << self.qtop)
        ck = [c[k] + self.const[k] - sum(ql[i] * self.m[k - i] for i in range(K) if 0 <= k - i < K) for k in range(NP)]
        carry = 0
        for j in range(self.ngroups):
            ks = range(GRP * j, min(NP, GRP * (j + 1)))
            sj = sum(ck[k] * BASE ** (k - GRP * j) for k in ks) + carry
            if j < self.ngroups - 1:
                assert sj % BASEG == 0
                carry = sj // BASEG
                lo_c, hi_c = self.carry_bounds[j]
                assert lo_c <= carry <= hi_c, f"{self.name}: carry {j} out of bounds"
            else:
                assert sj == 0
        return ql


# ----------------------------------------------------------------------------------------------------------------
# identities
# ----------------------------------------------------------------------------------------------------------------
def _rng_all(*names_fe, pts=()):
    d = {}
    for nm in names_fe:
        d.update(rng_fe(nm))
    for nm in pts:
        d.update(rng_pt(nm))
    return d


X1, Y1 = fe_var("p1", 0), fe_var("p1", K)
X2, Y2 = fe_var("p2", 0), fe_var("p2", K)
LAM, X3, Y3 = fe_var("lam"), fe_var("x3"), fe_var("y3")
RNG_G = _rng_all("lam", "x3", "y3", pts=("p1", "p2"))

ADD_IDS = [
    Ident("A1", P, [(1, LAM, fe_sub(X2, X1)), (-1, fe_sub(Y2, Y1), None)], "q1", RNG_G),
    Ident("A2", P, [(1, LAM, LAM), (-1, X1, None), (-1, X2, None), (-1, X3, None)], "q2", RNG_G),
    Ident("A3", P, [(1, LAM, fe_sub(X1, X3)), (-1, Y1, None), (-1, Y3, None)], "q3", RNG_G),
]
DBL_IDS = [
    Ident("D1", P, [(2, Y1, LAM), (-3, X1, X1)], "q1", RNG_G),
    Ident("D2", P, [(1, LAM, LAM), (-2, X1, None), (-1, X3, None)], "q2", RNG_G),
    Ident("D3", P, [(1, LAM, fe_sub(X1, X3)), (-1, Y1, None), (-1, Y3, None)], "q3", RNG_G),
]
S_ = fe_var("sq")
OC_IDS = [
    Ident("O1", P, [(1, X1, X1), (-1, S_, None)], "q1", _rng_all("sq", pts=("p1",))),
    Ident("O2", P, [(1, Y1, Y1), (-1, S_, X1), (-1, fe_const(7), None)], "q2", _rng_all("sq", pts=("p1",))),
]
AV, WV, UV = fe_var("av"), fe_var("wv"), fe_var("uv")
RNG_N = _rng_all("av", "wv", "uv")
MI_ID = Ident("M1", N, [(1, AV, WV), (-1, fe_const(1), None)], "q1", RNG_N)
MU_ID = Ident("M2", N, [(1, AV, WV), (-1, UV, None)], "q1", RNG_N)

# witness layout sizes
NW_ADD = 7 * K + 2
NW_DBL = 6 * K + 1
NW_OC = 3 * K
NW_MI = 2 * K
NW_MU = 2 * K
NW_RNGN = K + 1
PT = 2 * K                                    # limbs of a point


def lim_line(nm, wbase):
    items = [f"{rcn(W if i < K - 1 else TOP_BITS)}(w[{wbase + i}])" for i in range(K)]
    return f"    field[{K}] {nm} = [{', '.join(items)}];"


def q_line(idn, nm, wbase):
    items = [f"{rcn(W if i < K - 1 else idn.qtop)}(w[{wbase + i}])" for i in range(K)]
    return f"    field[{K}] {nm} = [{', '.join(items)}];"


def canon_expr(v):
    return " + ".join([f"(TOPM - {v}[{K - 1}])"] + [f"(LIMM - {v}[{i}])" for i in range(K - 2, 0, -1)])


def zok_padd():
    L = [f"def padd(field[{PT}] p1, field[{PT}] p2, field[{NW_ADD}] w) -> field[{PT}] {{",
         lim_line("lam", 0), lim_line("x3", K), lim_line("y3", 2 * K),
         q_line(ADD_IDS[0], "q1", 3 * K), q_line(ADD_IDS[1], "q2", 4 * K), q_line(ADD_IDS[2], "q3", 5 * K)]
    for idn in ADD_IDS:
        L.append(f"    // identity {idn.name}  (q: {idn.qbits_total} bits, carries {idn.cb})")
        L.append(idn.emit())
    sel0 = 6 * K + 1
    L.append("    // x3 is canonical: limbs 1..4 are not all ones, so x3 < 2^256 - 2^60 < p")
    L.append(f"    assert(({canon_expr('x3')}) * w[{6 * K}] == 1);")
    L.append("    // x1 != x2: one-hot selector of a limb in which they differ, with an inverse")
    for i in range(K):
        L.append(f"    field s{i} = w[{sel0 + i}];")
    for i in range(K):
        L.append(f"    assert(s{i} * (s{i} - 1) == 0);")
    L.append("    assert(" + " + ".join(f"s{i}" for i in range(K)) + " == 1);")
    L.append("    assert((" + " + ".join(f"s{i} * (p1[{i}] - p2[{i}])" for i in range(K)) + f") * w[{sel0 + K}] == 1);")
    L.append("    return [" + ", ".join([f"x3[{i}]" for i in range(K)] + [f"y3[{i}]" for i in range(K)]) + "];")
    L.append("}")
    return "\n".join(L)


def zok_pdbl():
    L = [f"def pdbl(field[{PT}] p1, field[{NW_DBL}] w) -> field[{PT}] {{",
         lim_line("lam", 0), lim_line("x3", K), lim_line("y3", 2 * K),
         q_line(DBL_IDS[0], "q1", 3 * K), q_line(DBL_IDS[1], "q2", 4 * K), q_line(DBL_IDS[2], "q3", 5 * K)]
    for idn in DBL_IDS:
        L.append(f"    // identity {idn.name}  (q: {idn.qbits_total} bits, carries {idn.cb})")
        L.append(idn.emit())
    L.append(f"    assert(({canon_expr('x3')}) * w[{6 * K}] == 1);")
    L.append("    return [" + ", ".join([f"x3[{i}]" for i in range(K)] + [f"y3[{i}]" for i in range(K)]) + "];")
    L.append("}")
    return "\n".join(L)


def zok_oncurve():
    L = [f"def oncurve(field[{PT}] p1, field[{NW_OC}] w) -> bool {{",
         lim_line("sq", 0), q_line(OC_IDS[0], "q1", K), q_line(OC_IDS[1], "q2", 2 * K)]
    for idn in OC_IDS:
        L.append(f"    // identity {idn.name}  (q: {idn.qbits_total} bits, carries {idn.cb})")
        L.append(idn.emit())
    L.append("    return true;")
    L.append("}")
    return "\n".join(L)


def zok_modn():
    L = [f"def modn_inv(field[{K}] av, field[{NW_MI}] w) -> field[{K}] {{",
         lim_line("wv", 0), q_line(MI_ID, "q1", K),
         f"    // identity {MI_ID.name}: av*wv = 1 (mod n)  (q: {MI_ID.qbits_total} bits, carries {MI_ID.cb})",
         MI_ID.emit(), "    return wv;", "}", "",
         "// u = av*wv mod n; returns the 256 bits of u, most significant first (u is range-checked through its bits)",
         f"def modn_u(field[{K}] av, field[{K}] wv, field[{NW_MU}] w) -> bool[256] {{"]
    for i in range(K):
        Lb = W if i < K - 1 else TOP_BITS
        flat = " + ".join(f"(b{i}[{t}] ? {2 ** (Lb - 1 - t)} : 0)" for t in range(Lb))
        L.append(f"    bool[{Lb}] b{i} = unpack_e(w[{i}]); assert({flat} == w[{i}]);")
    L.append(f"    field[{K}] uv = [" + ", ".join(f"w[{i}]" for i in range(K)) + "];")
    L.append(q_line(MU_ID, "q1", K))
    L.append(f"    // identity {MU_ID.name}: av*wv - uv = 0 (mod n)  (q: {MU_ID.qbits_total} bits, carries {MU_ID.cb})")
    L.append(MU_ID.emit())
    L.append("    return [" + ", ".join(f"...b{i}" for i in range(K - 1, -1, -1)) + "];")
    L.append("}")
    return "\n".join(L)


def zok_misc():
    last = K - 1
    L = [f"def rc256(field[{K}] v) -> field[{K}] {{",
         "    return [" + ", ".join(f"{rcn(W if i < K - 1 else TOP_BITS)}(v[{i}])" for i in range(K)) + "];", "}", "",
         "// v is canonical: its limbs 1..4 are not all ones, so v < 2^256 - 2^60 < p",
         f"def canon(field[{K}] v, field[1] w) -> bool {{",
         f"    assert(({canon_expr('v')}) * w[0] == 1);", "    return true;", "}", "",
         "// 1 <= v <= n - 1  (v + d = n - 1 with d >= 0 range-checked, and v != 0)",
         f"def rng_n(field[{K}] v, field[{NW_RNGN}] w) -> bool {{",
         f"    field[{K}] d = [" + ", ".join(f"{rcn(W if i < K - 1 else TOP_BITS)}(w[{i}])" for i in range(K)) + "];"]
    for i in range(K - 1):
        prev = " + t%d" % (i - 1) if i > 0 else ""
        L.append(f"    field t{i} = (v[{i}] + d[{i}]{prev} - NM1[{i}]) * INV_B;")
        L.append(f"    assert(t{i} * (t{i} - 1) == 0);")
    L.append(f"    assert(v[{last}] + d[{last}] + t{last - 1} - NM1[{last}] == 0);")
    L.append(f"    assert((" + " + ".join(f"v[{i}]" for i in range(K)) + f") * w[{K}] == 1);")
    L += ["    return true;", "}", "",
          "// R.x mod n == r :  xr = r + b*n over the integers, b a bit",
          f"def final_cmp(field[{K}] xr, field[{K}] r, field[1] w) -> bool {{",
          "    field b = w[0];", "    assert(b * (b - 1) == 0);"]
    for i in range(K - 1):
        prev = f" + u{i - 1}" if i > 0 else ""
        L.append(f"    field t{i} = (xr[{i}] - r[{i}] - b * NN[{i}]{prev}) * INV_B;")
        L.append(f"    field u{i} = rc2(t{i} + 2) - 2;")
    RCSET.add(2)
    L.append(f"    assert(xr[{last}] - r[{last}] - b * NN[{last}] + u{last - 1} == 0);")
    L += ["    return true;", "}"]
    return "\n".join(L)


def zok_sel16(tc):
    """tc[i] = limbs (PT) of the constant table entry i*G + D' (j = 0). Variable entries come in tv (12 entries x PT)."""
    L = ["// one of the 16 table entries  T[i][j] = i*G + j*Q + D'  chosen by the 2-bit digits (a1 a0) of u1 and (b1 b0) of u2",
         f"def sel16(bool a1, bool a0, bool b1, bool b0, field[{12 * PT}] tv) -> field[{PT}] {{",
         "    field fa1 = if a1 { 1 } else { 0 }; field fa0 = if a0 { 1 } else { 0 };",
         "    field fb1 = if b1 { 1 } else { 0 }; field fb0 = if b0 { 1 } else { 0 };",
         "    field pa = fa1 * fa0; field pb = fb1 * fb0;",
         "    field[4] oa = [1 - fa1 - fa0 + pa, fa0 - pa, fa1 - pa, pa];",
         "    field[4] ob = [1 - fb1 - fb0 + pb, fb0 - pb, fb1 - pb, pb];"]
    for i in range(4):
        for j in range(4):
            L.append(f"    field s{i}{j} = oa[{i}] * ob[{j}];")
    outs = []
    for m in range(PT):
        terms = [f"{tc[i][m]} * s{i}0" for i in range(4)]
        for i in range(4):
            for j in range(1, 4):
                k = 3 * i + (j - 1)
                terms.append(f"s{i}{j} * tv[{PT * k + m}]")
        L.append(f"    field o{m} = " + " + ".join(terms) + ";")
        outs.append(f"o{m}")
    L.append("    return [" + ", ".join(outs) + "];")
    L.append("}")
    return "\n".join(L)


# ----------------------------------------------------------------------------------------------------------------
# constants of the circuit
# ----------------------------------------------------------------------------------------------------------------
D_PT, D_CTR = E.hash_to_curve(SALT_D)
G1, G2, G3 = E.G, E.add(E.G, E.G), E.add(E.add(E.G, E.G), E.G)
NWIN = 128
OFFS = (pow(4, NWIN) - 1) // 3
E_PT = E.neg(E.mul(OFFS, D_PT))
TC = [E.add(E.mul(i, E.G), D_PT) for i in range(4)]          # constant entries i*G + D'


def ptlimbs(Pt):
    return limbs(Pt[0]) + limbs(Pt[1])


def zok_consts():
    def arr(v):
        return "[" + ", ".join(str(x) for x in v) + "]"
    L = [f"const field INV_B = {INV_BASE};                  // 1 / 2^{W}",
         f"const field INVG = {INV_BASEG};                  // 1 / 2^{W * GRP}",
         f"const field TOPM = {TOPMAX};                      // 2^{TOP_BITS} - 1",
         f"const field LIMM = {MASK};                      // 2^{W} - 1",
         f"const field[{K}] NM1 = {arr(limbs(N - 1))};   // n - 1",
         f"const field[{K}] NN = {arr(limbs(N))};      // n",
         f"const field[{PT}] C_D = {arr(ptlimbs(D_PT))};   // D' = hash_to_curve('{SALT_D.decode()}'), counter {D_CTR}",
         f"const field[{PT}] C_G1 = {arr(ptlimbs(G1))};",
         f"const field[{PT}] C_G2 = {arr(ptlimbs(G2))};",
         f"const field[{PT}] C_G3 = {arr(ptlimbs(G3))};",
         f"const field[{PT}] C_E = {arr(ptlimbs(E_PT))};   // -((4^{NWIN} - 1)/3) * D'"]
    return "\n".join(L)


PREAMBLE_IMPORTS = 'from "EMBED" import unpack as unpack_e;\n'


def preamble(parts=("padd", "pdbl", "oncurve", "modn", "misc", "sel16")):
    RCSET.clear()
    body = []
    if "padd" in parts:
        body.append(zok_padd() + "\n")
    if "pdbl" in parts:
        body.append(zok_pdbl() + "\n")
    if "oncurve" in parts:
        body.append(zok_oncurve() + "\n")
    if "modn" in parts:
        body.append(zok_modn() + "\n")
    if "misc" in parts:
        body.append(zok_misc() + "\n")
    if "sel16" in parts:
        body.append(zok_sel16([ptlimbs(t) for t in TC]) + "\n")
    rcs = "\n".join(zok_rc(L) + "\n" for L in sorted(RCSET))
    head = [PREAMBLE_IMPORTS, zok_consts(), "", "// range checks: x in [0, 2^L)  (the assert on the recomposition keeps the bits in the circuit)", rcs]
    return "\n".join(head + body)


# ----------------------------------------------------------------------------------------------------------------
# witness builders (Python side of each gadget)
# ----------------------------------------------------------------------------------------------------------------
def _canon_inv(x):
    l = limbs(x)
    u = sum(LIM_MAX[i] - l[i] for i in range(1, K))
    if u == 0:
        raise Exceptional("value in the excluded non-canonical region")
    return pow(u, -1, RBN)


def wit_padd(P1, P2):
    (x1, y1), (x2, y2) = P1, P2
    if x1 == x2:
        raise Exceptional("x1 == x2 in an addition")
    lam = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    env = {}
    env.update(env_pt("p1", P1))
    env.update(env_pt("p2", P2))
    env.update(env_fe("lam", lam))
    env.update(env_fe("x3", x3))
    env.update(env_fe("y3", y3))
    wv = limbs(lam) + limbs(x3) + limbs(y3)
    for idn in ADD_IDS:
        wv += idn.eval(env)
    d = [a - b for a, b in zip(limbs(x1), limbs(x2))]
    i0 = next(i for i in range(K) if d[i] != 0)
    wv += [_canon_inv(x3)] + [1 if i == i0 else 0 for i in range(K)] + [pow(d[i0] % RBN, -1, RBN)]
    assert len(wv) == NW_ADD
    return wv, (x3, y3)


def wit_pdbl(P1):
    x1, y1 = P1
    lam = 3 * x1 * x1 * pow(2 * y1, -1, P) % P
    x3 = (lam * lam - 2 * x1) % P
    y3 = (lam * (x1 - x3) - y1) % P
    env = {}
    env.update(env_pt("p1", P1))
    env.update(env_fe("lam", lam))
    env.update(env_fe("x3", x3))
    env.update(env_fe("y3", y3))
    wv = limbs(lam) + limbs(x3) + limbs(y3)
    for idn in DBL_IDS:
        wv += idn.eval(env)
    wv += [_canon_inv(x3)]
    assert len(wv) == NW_DBL
    return wv, (x3, y3)


def wit_oncurve(Q):
    x, y = Q
    s = x * x % P
    env = env_pt("p1", Q)
    env.update(env_fe("sq", s))
    wv = limbs(s)
    for idn in OC_IDS:
        wv += idn.eval(env)
    assert len(wv) == NW_OC
    return wv


def wit_modn_inv(sv):
    w = pow(sv, -1, N)
    env = env_fe("av", sv)
    env.update(env_fe("wv", w))
    wv = limbs(w) + MI_ID.eval(env)
    return wv, w


def wit_modn_u(a, w):
    u = a * w % N
    env = env_fe("av", a)
    env.update(env_fe("wv", w))
    env.update(env_fe("uv", u))
    wv = limbs(u) + MU_ID.eval(env)
    return wv, u


def wit_rng_n(v):
    assert 1 <= v <= N - 1
    d = N - 1 - v
    return limbs(d) + [pow(sum(limbs(v)), -1, RBN)]


# ----------------------------------------------------------------------------------------------------------------
# tracer
# ----------------------------------------------------------------------------------------------------------------
LAST_MARKS = []


class Tracer:
    def __init__(self):
        self.lines, self.wit, self.n = [], [], 0
        self.marks, self.ctx = [], ""

    def name(self, pre="v"):
        self.n += 1
        return f"{pre}{self.n}"

    def emit(self, s):
        self.lines.append("    " + s)

    def alloc(self, vals):
        a = len(self.wit)
        self.wit.extend(vals)
        return a, a + len(vals)

    def slice(self, vals, label=""):
        a, b = self.alloc(vals)
        self.marks.append((a, b, label or self.ctx))
        return f"wit[{a}..{b}]"

    def padd(self, nA, PA, nB, PB, pre="a"):
        wv, R = wit_padd(PA, PB)
        nm = self.name(pre)
        self.emit(f"field[{PT}] {nm} = padd({nA}, {nB}, {self.slice(wv, 'padd:' + pre)});")
        return nm, R

    def pdbl(self, nA, PA, pre="d"):
        wv, R = wit_pdbl(PA)
        nm = self.name(pre)
        self.emit(f"field[{PT}] {nm} = pdbl({nA}, {self.slice(wv, 'pdbl')});")
        return nm, R


def build_chain_test(P0, Q0, kind, count):
    """Test circuit: `count` doublings (kind='dbl') or `count` additions of the input point q (kind='add') to p."""
    tr = Tracer()
    cur, Pc = "p", P0
    for _ in range(count):
        if kind == "dbl":
            cur, Pc = tr.pdbl(cur, Pc)
        else:
            cur, Pc = tr.padd(cur, Pc, "q", Q0)
    body = "\n".join(tr.lines)
    src = (preamble(("padd", "pdbl")) +
           f"\ndef main(field[{PT}] p, field[{PT}] q, private field[{len(tr.wit)}] wit) -> field[{PT}] {{\n{body}\n    return {cur};\n}}\n")
    return src, ptlimbs(P0) + ptlimbs(Q0) + tr.wit, Pc


def build_full(Q, z, r, s):
    """Full ECDSA verifier for the public key Q, 256-bit message hash z, signature (r, s)."""
    tr = Tracer()
    Qx, Qy = Q
    em = tr.emit
    em(f"field[{K}] QX = rc256(qx);")
    em(f"field[{K}] QY = rc256(qy);")
    em(f"field[{K}] ZZ = rc256(z);")
    em(f"field[{K}] RR = rc256(r);")
    em(f"field[{K}] SS = rc256(s);")
    em(f"field[{PT}] Q = [" + ", ".join([f"QX[{i}]" for i in range(K)] + [f"QY[{i}]" for i in range(K)]) + "];")
    em(f"assert(canon(QX, {tr.slice([_canon_inv(Qx)], 'canon(Qx)')}));")
    em(f"assert(oncurve(Q, {tr.slice(wit_oncurve(Q), 'oncurve(Q)')}));")
    em(f"assert(rng_n(RR, {tr.slice(wit_rng_n(r), 'rng_n(r)')}));")
    em(f"assert(rng_n(SS, {tr.slice(wit_rng_n(s), 'rng_n(s)')}));")
    wv, w = wit_modn_inv(s)
    em(f"field[{K}] WW = modn_inv(SS, {tr.slice(wv, 'modn_inv')});")
    wv, u1 = wit_modn_u(z, w)
    em(f"bool[256] UB1 = modn_u(ZZ, WW, {tr.slice(wv, 'modn_u(u1)')});")
    wv, u2 = wit_modn_u(r, w)
    em(f"bool[256] UB2 = modn_u(RR, WW, {tr.slice(wv, 'modn_u(u2)')});")
    T, names = {}, {}
    names[(0, 1)], T[(0, 1)] = tr.padd("C_D", D_PT, "Q", Q, "T")
    names[(0, 2)], T[(0, 2)] = tr.padd(names[(0, 1)], T[(0, 1)], "Q", Q, "T")
    names[(0, 3)], T[(0, 3)] = tr.padd(names[(0, 2)], T[(0, 2)], "Q", Q, "T")
    for i, (cn, cp) in zip((1, 2, 3), (("C_G1", G1), ("C_G2", G2), ("C_G3", G3))):
        for j in (1, 2, 3):
            names[(i, j)], T[(i, j)] = tr.padd(names[(0, j)], T[(0, j)], cn, cp, "T")
    for (i, j), Pt in T.items():
        assert Pt == E.add(E.add(E.mul(i, E.G), E.mul(j, Q)), D_PT)
    em(f"field[{12 * PT}] TV = [" + ", ".join(f"...{names[(i, j)]}" for i in range(4) for j in (1, 2, 3)) + "];")
    entry = {(i, 0): TC[i] for i in range(4)}
    entry.update(T)

    def digit(u, wdw):
        return (u >> (254 - 2 * wdw)) & 3

    acc_n = tr.name("S")
    em(f"field[{PT}] {acc_n} = sel16(UB1[0], UB1[1], UB2[0], UB2[1], TV);")
    acc = entry[(digit(u1, 0), digit(u2, 0))]
    for wdw in range(1, NWIN):
        acc_n, acc = tr.pdbl(acc_n, acc)
        acc_n, acc = tr.pdbl(acc_n, acc)
        sl = tr.name("S")
        em(f"field[{PT}] {sl} = sel16(UB1[{2 * wdw}], UB1[{2 * wdw + 1}], UB2[{2 * wdw}], UB2[{2 * wdw + 1}], TV);")
        pt = entry[(digit(u1, wdw), digit(u2, wdw))]
        acc_n, acc = tr.padd(acc_n, acc, sl, pt)
    R_n, R = tr.padd(acc_n, acc, "C_E", E_PT, "R")
    ref = E.add(E.mul(u1, E.G), E.mul(u2, Q))
    assert R == ref, "circuit trace disagrees with the reference scalar multiplication"
    if R[0] == r:
        b = 0
    elif R[0] == r + N:
        b = 1
    else:
        raise Exceptional("signature does not verify (R.x mod n != r)")
    em(f"assert(final_cmp([" + ", ".join(f"{R_n}[{i}]" for i in range(K)) + f"], RR, {tr.slice([b], 'final_cmp')}));")
    body = "\n".join(tr.lines)
    src = (preamble() + f"\ndef main(field[{K}] qx, field[{K}] qy, field[{K}] z, field[{K}] r, field[{K}] s, "
           f"private field[{len(tr.wit)}] wit) {{\n{body}\n}}\n")
    args = limbs(Qx) + limbs(Qy) + limbs(z) + limbs(r) + limbs(s) + tr.wit
    global LAST_MARKS
    LAST_MARKS = [(a + 5 * K, b + 5 * K, lab) for a, b, lab in tr.marks]      # positions in the argument list
    return src, args, R
