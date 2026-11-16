"""Reference arithmetic for secp256k1 and ECDSA verification (pure Python, big integers).

Used (1) to cross-check against the `cryptography` library and (2) as the source of every witness value
for the ZoKrates circuit.
"""
import hashlib

p = 2**256 - 2**32 - 977
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G = (Gx, Gy)


def on_curve(P):
    if P is None:
        return True
    x, y = P
    return (y * y - x * x * x - 7) % p == 0


def neg(P):
    return None if P is None else (P[0], (-P[1]) % p)


def add(P1, P2):
    """Complete affine addition (None is the point at infinity)."""
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    x1, y1 = P1
    x2, y2 = P2
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return None
        lam = 3 * x1 * x1 * pow(2 * y1, -1, p) % p
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return (x3, y3)


def mul(k, P):
    k %= n
    R = None
    A = P
    while k:
        if k & 1:
            R = add(R, A)
        A = add(A, A)
        k >>= 1
    return R


def hash_to_curve(label: bytes):
    """Try-and-increment: first x = SHA-256(label || ctr) mod p with x^3+7 a square; y is the even root.
    Nobody knows the discrete logarithm of the result with respect to G (nothing-up-my-sleeve point)."""
    ctr = 0
    while True:
        x = int.from_bytes(hashlib.sha256(label + ctr.to_bytes(4, "big")).digest(), "big") % p
        rhs = (x * x * x + 7) % p
        y = pow(rhs, (p + 1) // 4, p)
        if y * y % p == rhs:
            if y & 1:
                y = p - y
            return (x, y), ctr
        ctr += 1


def ecdsa_verify(Q, z, r, s):
    """Textbook ECDSA verification with z the (already hashed) message as a 256-bit integer."""
    if not (1 <= r < n and 1 <= s < n):
        return False
    if Q is None or not on_curve(Q):
        return False
    w = pow(s, -1, n)
    u1 = z * w % n
    u2 = r * w % n
    R = add(mul(u1, G), mul(u2, Q))
    if R is None:
        return False
    return R[0] % n == r


def ecdsa_sign(d, z, k):
    R = mul(k, G)
    r = R[0] % n
    s = pow(k, -1, n) * (z + r * d) % n
    return r, s
