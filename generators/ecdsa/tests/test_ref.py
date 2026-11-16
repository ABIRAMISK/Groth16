import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecref as E
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

# 1. generator on curve, order
assert E.on_curve(E.G) and E.mul(E.n, E.G) is None and E.mul(E.n - 1, E.G) == E.neg(E.G)
# 2. public key from the library equals ours; library signatures verify with our verifier; tampering breaks it
ok = 0
for i in range(25):
    key = ec.generate_private_key(ec.SECP256K1())
    d = key.private_numbers().private_value
    pub = key.public_key().public_numbers()
    Q = (pub.x, pub.y)
    assert E.mul(d, E.G) == Q
    msg = os.urandom(40)
    sig = key.sign(msg, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(sig)
    z = int.from_bytes(hashlib.sha256(msg).digest(), "big")
    assert E.ecdsa_verify(Q, z, r, s), "valid signature rejected"
    assert not E.ecdsa_verify(Q, z ^ 1, r, s)
    assert not E.ecdsa_verify(Q, z, r ^ 1, s)
    assert not E.ecdsa_verify(Q, z, r, s ^ 1)
    # signature made by our own signer is accepted by the library
    k = int.from_bytes(os.urandom(32), "big") % (E.n - 1) + 1
    r2, s2 = E.ecdsa_sign(d, z, k)
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    key.public_key().verify(encode_dss_signature(r2, s2), msg, ec.ECDSA(hashes.SHA256()))
    ok += 1
print("reference ECDSA agrees with the cryptography library on", ok, "random keys/messages")
D, ctr = E.hash_to_curve(b"zkp-ecdsa-secp256k1/offset-D/v1")
print("D' found at counter", ctr, "on curve:", E.on_curve(D))
