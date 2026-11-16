"""Writes the ECDSA-secp256k1 verifier circuit and one fixed, deterministic valid input.

usage: python3 build_circuit.py OUT_DIR            -> OUT_DIR/ecdsa_verify.zok, ecdsa_args.txt, ecdsa_input.json
The ZoKrates source does not depend on the signature (only the witness vector does); the fixed input is a deterministic
signature of a fixed message made with a fixed key and nonce derived from SHA-256 (benchmark input, not a secret).
Pure Python (no third-party packages). If the `cryptography` package is installed the signature is also verified with it.
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecref as E
import ecgen as G

LABEL = b"zkp-ecdsa-secp256k1 benchmark input v1"
MESSAGE = b"Empirical Profiling of Classical Cryptography and R1CS Costs in ZK-Native and Non-Native Circuits"


def h(*parts):
    return int.from_bytes(hashlib.sha256(b"".join(parts)).digest(), "big")


def fixed_input():
    d = h(LABEL, b"/key") % (E.n - 1) + 1
    z = h(MESSAGE)
    k = h(LABEL, b"/nonce", d.to_bytes(32, "big"), z.to_bytes(32, "big")) % (E.n - 1) + 1
    Q = E.mul(d, E.G)
    r, s = E.ecdsa_sign(d, z, k)
    assert E.ecdsa_verify(Q, z, r, s)
    return Q, z, r, s


def main(out):
    os.makedirs(out, exist_ok=True)
    Q, z, r, s = fixed_input()
    src, args, R = G.build_full(Q, z, r, s)
    open(os.path.join(out, "ecdsa_verify.zok"), "w", newline="\n").write(src)
    open(os.path.join(out, "ecdsa_args.txt"), "w", newline="\n").write(" ".join(str(a) for a in args))
    json.dump({"public_key_x": hex(Q[0]), "public_key_y": hex(Q[1]), "message_hash_z": hex(z), "r": hex(r), "s": hex(s),
               "message": MESSAGE.decode(), "limbs": "5 limbs of 60,60,60,60,16 bits, least significant first",
               "arguments": "qx(5) qy(5) z(5) r(5) s(5) then %d private witness values" % (len(args) - 25)},
              open(os.path.join(out, "ecdsa_input.json"), "w"), indent=1)
    try:   # independent check of the benchmark signature with a standard library, if available
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        pub = ec.EllipticCurvePublicNumbers(Q[0], Q[1], ec.SECP256K1()).public_key()
        pub.verify(encode_dss_signature(r, s), MESSAGE, ec.ECDSA(hashes.SHA256()))
        print("signature also verified with the 'cryptography' package")
    except ImportError:
        print("(package 'cryptography' not installed: independent check skipped)")
    print("wrote", out, "| source %d bytes, %d arguments (25 public + %d private)" % (len(src), len(args), len(args) - 25))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
