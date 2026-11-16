#!/usr/bin/env python3
"""Writes ../circuits/rsa2048_verify.zok. Constants are computed, not typed by hand."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rsa_common import *

SRC = '''// RSA-2048 signature verification (PKCS#1 v1.5, SHA-256, e = 65537) in ZoKrates 0.8.7 / Groth16 / BN254.
//
// Statement: there is a signature s <= n such that s^65537 = EM (mod n), where EM is the
// PKCS#1 v1.5 encoding of the public SHA-256 digest (RFC 8017, RSASSA-PKCS1-v1_5-VERIFY).
//
// Non-native arithmetic: a 2048-bit integer is K = 17 little-endian limbs of W = 121 bits, each limb a
// BN254 scalar-field element. s^65537 is 16 squarings and one multiplication, i.e. 17 modular
// multiplications. Each is checked as a*b = q*n + r over the integers (q and r supplied by the prover):
// limb products are formed in the field, then a carry chain is verified with range-checked carries.
//
// Public inputs : n (modulus limbs), dg (digest as 121 + 121 + 14 bits)
// Private inputs: s, d = n - s, quotients q and remainders r of the 16 squarings, quotient ql of the
//                 last multiplication (its remainder is the encoded message, built from n-independent
//                 constants and the digest).
//
// The message hash itself (27,470 constraints per SHA-256 block) is NOT part of this circuit.

import "utils/pack/bool/unpack" as unpack;
import "utils/pack/bool/pack" as pack;

const u32 K = {K};
const u32 W = {W};
const u32 CB = {CB};                       // carry range check: carry + OFFSET in [0, 2^CB)
const field INV_W = {INV_W};   // 1 / 2^W
const field OFFSET = {OFFSET};  // 2^(CB-1)
const field[K] EM_CONST = {EM};   // PKCS#1 v1.5 block with the 32 digest bytes zeroed, as limbs

// Returns x after asserting x in [0, 2^L). ZoKrates drops an unpack whose bits are never used, together
// with its constraints, so the assert on the recomposition is what keeps the range check in the circuit.
def range_check<L>(field x) -> field {{
    bool[L] b = unpack::<L>(x);
    assert(pack(b) == x);
    return x;
}}

def range_limbs(field[K] x) -> field[K] {{
    field[K] mut y = x;
    for u32 i in 0..K {{
        y[i] = range_check::<W>(x[i]);
    }}
    return y;
}}

// Asserts a*b = q*n + r as integers and returns r. All limbs of a, b, q, r, n must lie in [0, 2^W).
def mulmod(field[K] a, field[K] b, field[K] q, field[K] r, field[K] n) -> field[K] {{
    field[2 * K - 1] mut c = [0; 2 * K - 1];
    for u32 i in 0..K {{
        for u32 j in 0..K {{
            c[i + j] = c[i + j] + a[i] * b[j] - q[i] * n[j];
        }}
        c[i] = c[i] - r[i];
    }}
    field mut carry = 0;
    for u32 i in 0..(2 * K - 2) {{
        field t = (c[i] + carry) * INV_W;
        carry = range_check::<CB>(t + OFFSET) - OFFSET;
    }}
    assert(c[2 * K - 2] + carry == 0);
    return r;
}}

def main(field[K] n, field[3] dg, private field[K] s, private field[K] d,
         private field[16][K] q, private field[16][K] r, private field[K] ql) {{
    // every prover-supplied limb, and the digest, must be in range
    field[K] sc = range_limbs(s);
    field[K] dc = range_limbs(d);
    field[K] qlc = range_limbs(ql);
    field d0 = range_check::<W>(dg[0]);
    field d1 = range_check::<W>(dg[1]);
    field d2 = range_check::<14>(dg[2]);

    // s <= n: s + d = n as integers (ripple-carry adder with boolean carries)
    field mut cin = 0;
    for u32 i in 0..K {{
        field cout = (sc[i] + dc[i] + cin - n[i]) * INV_W;
        assert(cout * (cout - 1) == 0);
        cin = cout;
    }}
    assert(cin == 0);

    // 16 squarings: x_(j+1) = x_j^2 mod n, with x_0 = s
    field[K] mut x = sc;
    for u32 j in 0..16 {{
        x = mulmod(x, x, range_limbs(q[j]), range_limbs(r[j]), n);
    }}

    // x_16 * s = ql * n + EM(digest): the remainder is the encoded message itself
    field[K] mut em = EM_CONST;
    em[0] = em[0] + d0;
    em[1] = em[1] + d1;
    em[2] = em[2] + d2;
    field[K] last = mulmod(x, sc, qlc, em, n);
    return;
}}
'''
def source(mutant=None):
    out = SRC.format(K=K, W=W, CB=CB, INV_W=INV_W, OFFSET=OFFSET,
                     EM="[" + ", ".join(str(v) for v in limbs(em_const())) + "]")
    if BITS != 2048:           # comments only; the 2048-bit file stays byte-identical to the one that was measured
        out = out.replace("RSA-2048", f"RSA-{BITS}").replace("a 2048-bit integer is K = 17", f"a {BITS}-bit integer is K = {K}")
    def sub(text, old, new):
        assert text.count(old) == 1, old
        return text.replace(old, new)
    if mutant == "noadder":      # drop the s <= n check
        i, j = out.index("    // s <= n:"), out.index("    // 16 squarings")
        out = out[:i] + out[j:]
    elif mutant == "norange":    # drop range checks on quotient and remainder limbs
        out = sub(out, "range_limbs(q[j]), range_limbs(r[j])", "q[j], r[j]")
    elif mutant == "nocarry":    # drop range checks on carries
        out = sub(out, "carry = range_check::<CB>(t + OFFSET) - OFFSET;", "carry = t;")
    elif mutant == "nofinal":    # drop the final zero-carry assertion
        out = sub(out, "    assert(c[2 * K - 2] + carry == 0);\n", "")
    else:
        assert mutant is None
    return out

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", f"rsa{BITS}_verify.zok"))
    src = source()
    open(path, "w").write(src)
    print("wrote", path, len(src), "bytes")
