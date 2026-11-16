"""Shared constants and helpers for the RSA (e=65537) ZoKrates circuit. Key size from the environment variable RSA_BITS (default 2048)."""
import os
BITS = int(os.environ.get("RSA_BITS", "2048"))
assert BITS % 8 == 0 and BITS >= 1024
W = 121                        # limb width in bits
K = -(-BITS // W)              # number of limbs (2048 -> 17, 17*121 = 2057 >= 2048)
# bit width of the carry range check (carry + 2^(CB-1) in [0, 2^CB)): every honest carry satisfies |carry| <= K*2^W + 2
CB = (K * (1 << W) + 2).bit_length() + 1
if BITS == 2048: assert (K, CB) == (17, 127)
P = 21888242871839275222246405745257275088548364400416034343698204186575808495617   # BN254 scalar field
INV_W = pow(2 ** W, -1, P)
OFFSET = 2 ** (CB - 1)
MASK = (1 << W) - 1
DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")   # PKCS#1 v1.5 prefix for SHA-256
assert len(DIGESTINFO) == 19

def limbs(x, k=K, w=W):
    assert 0 <= x < (1 << (k * w))
    return [(x >> (w * i)) & ((1 << w) - 1) for i in range(k)]

def unlimbs(ls, w=W):
    return sum(v << (w * i) for i, v in enumerate(ls))

def em_const():
    """PKCS#1 v1.5 encoded message with the 32 digest bytes zeroed."""
    kb = BITS // 8
    ps = kb - 3 - len(DIGESTINFO) - 32
    em = b"\x00\x01" + b"\xff" * ps + b"\x00" + DIGESTINFO + b"\x00" * 32
    assert len(em) == kb
    return int.from_bytes(em, "big")

def digest_limbs(h):
    """SHA-256 digest (bytes) as three public field elements: 121 + 121 + 14 bits."""
    x = int.from_bytes(h, "big")
    return [x & MASK, (x >> W) & MASK, x >> (2 * W)]

def em_int(h):
    return em_const() + int.from_bytes(h, "big")

def chain(n, s, h, e_bits=16):
    """Quotients/remainders for x_{j+1} = x_j^2 mod n (16 squarings) and the final x16*s product."""
    xs, qs, rs = [s], [], []
    for _ in range(e_bits):
        sq = xs[-1] * xs[-1]
        qs.append(sq // n); rs.append(sq % n); xs.append(rs[-1])
    prod = xs[-1] * s
    ql, rl = prod // n, prod % n
    return qs, rs, ql, rl

def build_args(n, s, h, d=None, qs=None, rs=None, ql=None):
    """Flatten inputs in the order of main(): n, dg, s, d, q[16][K], r[16][K], ql."""
    if qs is None:
        qs, rs, ql, rl = chain(n, s, h)
    if d is None:
        d = n - s
    args = limbs(n) + digest_limbs(h) + limbs(s) + limbs(d)
    for j in range(16):
        args += limbs(qs[j])
    for j in range(16):
        args += limbs(rs[j])
    args += limbs(ql)
    return [str(a) for a in args]
