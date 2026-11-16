import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecref as E
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

def make(seed=None):
    """A valid (Q, z, r, s) from the cryptography library (SHA-256 of a random message)."""
    key = ec.generate_private_key(ec.SECP256K1())
    pub = key.public_key().public_numbers()
    msg = os.urandom(48) if seed is None else hashlib.sha256(seed).digest()
    sig = key.sign(msg, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(sig)
    z = int.from_bytes(hashlib.sha256(msg).digest(), "big")
    Q = (pub.x, pub.y)
    assert E.ecdsa_verify(Q, z, r, s)
    return Q, z, r, s
