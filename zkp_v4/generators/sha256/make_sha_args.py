#!/usr/bin/env python3
"""Makes the two witness files of the SHA-256 baseline circuit (sha256_hash_circuit.zok = src/zkp/hash_circuit.zok of the
repository, unchanged), following src/zkp/proof_simulation.py of the repository:
  ECC input: secret = SECP256R1 private scalar, pubkey = public-key x coordinate, randomness = 11111
  RSA input: secret = RSA-2048 private exponent d, pubkey = modulus n, randomness = 22222
  (both reduced modulo 2^256 - 2^32 - 977 as in the repository code)
commitment = secret*pubkey + randomness; its low 254 bits form the 512-bit block; the circuit applies the SHA-256 compression
function once (no padding) and returns (commitment, first output word). The last 8 arguments (expected_hash) are computed
with hashlib as in the repository; the circuit does not constrain them.
Usage: make_sha_args.py <outdir>       (needs the 'cryptography' package)"""
import sys, os, hashlib
from cryptography.hazmat.primitives.asymmetric import ec, rsa
PP = 2**256 - 2**32 - 977
def u32s(c):
    bits = [(c >> i) & 1 for i in range(254)] + [0] * 258
    return [sum(bits[i * 32 + j] << j for j in range(32)) for i in range(16)]
def sha_words(ws):
    h = hashlib.sha256(b"".join(w.to_bytes(4, "little") for w in ws)).digest()
    return [int.from_bytes(h[i * 4:(i + 1) * 4], "little") for i in range(8)]
def args(secret, pub, rnd):
    c = secret * pub + rnd
    return [secret, pub, rnd] + sha_words(u32s(c))
out = sys.argv[1] if len(sys.argv) > 1 else "."
k = ec.generate_private_key(ec.SECP256R1())
a = args(k.private_numbers().private_value % PP, k.public_key().public_numbers().x % PP, 11111)
open(os.path.join(out, "sha256_args_ecc.txt"), "w").write(" ".join(map(str, a)))
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
a = args(k.private_numbers().d % PP, k.public_key().public_numbers().n % PP, 22222)
open(os.path.join(out, "sha256_args_rsa.txt"), "w").write(" ".join(map(str, a)))
print("wrote sha256_args_ecc.txt and sha256_args_rsa.txt in", out)
