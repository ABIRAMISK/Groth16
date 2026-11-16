#!/usr/bin/env python3
"""Make a fresh RSA key (size from RSA_BITS, default 2048) and PKCS#1 v1.5 / SHA-256 signature and write the 615 circuit inputs.
Usage: make_inputs.py [message] [outfile]     (needs the 'cryptography' package)"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rsa_common import *
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

msg = sys.argv[1].encode() if len(sys.argv) > 1 else b"hello zero knowledge"
out = sys.argv[2] if len(sys.argv) > 2 else "valid_args.txt"
key = rsa.generate_private_key(public_exponent=65537, key_size=BITS)
sig = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
key.public_key().verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())       # the library accepts it
n = key.public_key().public_numbers().n; s = int.from_bytes(sig, "big"); h = hashlib.sha256(msg).digest()
assert pow(s, 65537, n) == em_int(h)                                           # EM construction matches
args = build_args(n, s, h)
open(out, "w").write(" ".join(args))
print(f"wrote {out}: {len(args)} values (public: n limbs and 3 digest limbs; private: the rest)")
print("sha256(message) =", h.hex())
