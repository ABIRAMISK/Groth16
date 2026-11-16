#!/usr/bin/env python3
"""Native baseline of the paper: how long the operations that the circuits prove take outside a circuit, on this laptop.

Suites (--suite):
  baseline (default, about 1-2 minutes): RSA PKCS#1 v1.5 / SHA-256 sign and verify at 1024, 2048, 3072 and 4096 bits (e = 65537)
           and ECDSA / SHA-256 sign and verify on SECP256K1 (the curve of the circuit) and SECP256R1 (for reference).
  full     (about 45-60 minutes): the baseline plus the old tables: key generation (RSA 2048/3072/4096, four curves),
           RSA-OAEP encrypt/decrypt (2048/3072/4096) and ECDSA sign/verify on SECP384R1 and SECP521R1.

Protocol of the old suite, kept: 
repository's src/benchmarks/performance_tests.py (time.perf_counter around each operation; fresh key on every
key-generation iteration; one key pair per configuration for the encryption and signing tests; message b"Test message"; RSA-OAEP
with SHA-256 and MGF1-SHA256; ECDSA with SHA-256; 1,000 iterations), with three additions:
  * a few untimed warm-up iterations before each configuration,
  * the configurations are run in a random order (seed below) that is written to the log,
  * the machine and power state are recorded (env.json).
Nothing is discarded or repeated. The raw per-iteration times are the result; statistics are computed from them afterwards.

usage:  python classical_bench.py [--suite baseline|full] [--iterations 1000] [--out DIR] [--resume DIR] [--allow-battery] [--quick]
  --quick          20 iterations per configuration (seconds for the baseline suite): checks that everything works
  --resume DIR     continue an interrupted run (configurations that finished are skipped; the one that was running starts again)
Needs: Python 3.8 or newer and the 'cryptography' package (pip install cryptography).
"""
import argparse, csv, ctypes, datetime, gc, json, os, platform, random, subprocess, sys, time

from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1

SEED = 20261113
MSG = b"Test message"
RSA_SIZES = [2048, 3072, 4096]
CURVES = [("SECP256R1", ec.SECP256R1), ("SECP384R1", ec.SECP384R1), ("SECP521R1", ec.SECP521R1), ("SECP256K1", ec.SECP256K1)]
COLUMNS = ["Algorithm", "Parameter", "Experiment", "Time", "Encrypt Time", "Decrypt Time", "Sign Time", "Verify Time", "Iteration"]


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# ------------------------------------------------------------------ machine and power state
def run_text(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).replace("\r", "").strip()
    except Exception as e:                                           # noqa
        return "n/a (%s)" % e


def power_status():
    """(ac_line_status, battery_percent): ac_line_status 1 = mains power, 0 = battery, 255 = unknown. Windows only."""
    if os.name != "nt":
        return None, None

    class SPS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                    ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = SPS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    return int(s.ACLineStatus), int(s.BatteryLifePercent)


def cpu_info():
    name, mhz = platform.processor(), None
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            mhz = winreg.QueryValueEx(k, "~MHz")[0]
        except Exception:                                            # noqa
            pass
    elif os.path.exists("/proc/cpuinfo"):
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                name = line.split(":", 1)[1].strip()
                break
    return name, mhz


def ram_gib():
    if os.name == "nt":
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / 2 ** 30, 2)
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 2)
    except Exception:                                                # noqa
        return None


def openssl_version():
    try:
        from cryptography.hazmat.backends.openssl import backend
        return backend.openssl_version_text()
    except Exception:                                                # noqa
        import ssl
        return ssl.OPENSSL_VERSION


def environment():
    import cryptography
    name, mhz = cpu_info()
    ac, pct = power_status()
    e = {
        "started_utc": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.replace("\n", " "), "python_executable": sys.executable,
        "cryptography": cryptography.__version__, "openssl": openssl_version(),
        "platform": platform.platform(), "os_version": platform.version(), "machine": platform.machine(),
        "cpu_name": name, "cpu_mhz_registry": mhz, "logical_cpus": os.cpu_count(), "ram_gib": ram_gib(),
        "ac_line_status(1=mains,0=battery)": ac, "battery_percent": pct,
    }
    if os.name == "nt":
        e["ver"] = run_text(["cmd", "/c", "ver"])
        e["powercfg_active_scheme"] = run_text(["powercfg", "/getactivescheme"])
        ps = lambda q: run_text(["powershell", "-NoProfile", "-NonInteractive", "-Command", q])
        e["power_mode_overlay_plugged_in"] = ps(r"(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes).ActiveOverlayAcPowerScheme")
        e["power_mode_overlay_on_battery"] = ps(r"(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes).ActiveOverlayDcPowerScheme")
        e["note"] = "Best performance overlay = ded574b5-45a0-4f42-8737-46345c09c238"
    return e


# ------------------------------------------------------------------ the measurements (as in performance_tests.py)
def oaep():
    return OAEP(mgf=MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def block_keygen(kind, param, n, warm):
    gen = (lambda: rsa.generate_private_key(public_exponent=65537, key_size=param)) if kind == "RSA" else \
          (lambda: ec.generate_private_key(dict(CURVES)[param]()))
    for _ in range(warm):
        gen()
    rows = []
    for i in range(n):
        t0 = time.perf_counter(); gen(); t1 = time.perf_counter()
        rows.append([kind, str(param), "Key Generation", t1 - t0, "", "", "", "", i + 1])
    return rows


def block_rsa_ops(bits, n, warm):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits); pub = priv.public_key()
    for _ in range(warm):
        priv.decrypt(pub.encrypt(MSG, oaep()), oaep())
    rows = []
    for i in range(n):
        t0 = time.perf_counter(); ct = pub.encrypt(MSG, oaep()); enc = time.perf_counter() - t0
        t0 = time.perf_counter(); priv.decrypt(ct, oaep()); dec = time.perf_counter() - t0
        rows.append(["RSA", str(bits), "RSA Encryption", "", enc, dec, "", "", i + 1])
    return rows


def block_rsa_sig(bits, n, warm):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits); pub = priv.public_key()
    from cryptography.hazmat.primitives.asymmetric import padding
    for _ in range(warm):
        pub.verify(priv.sign(MSG, padding.PKCS1v15(), hashes.SHA256()), MSG, padding.PKCS1v15(), hashes.SHA256())
    rows = []
    for i in range(n):
        t0 = time.perf_counter(); sig = priv.sign(MSG, padding.PKCS1v15(), hashes.SHA256()); sg = time.perf_counter() - t0
        t0 = time.perf_counter(); pub.verify(sig, MSG, padding.PKCS1v15(), hashes.SHA256()); vf = time.perf_counter() - t0
        rows.append(["RSA", str(bits), "RSA Signature", "", "", "", sg, vf, i + 1])
    return rows


def block_ecc_ops(curve, n, warm):
    priv = ec.generate_private_key(dict(CURVES)[curve]()); pub = priv.public_key()
    for _ in range(warm):
        pub.verify(priv.sign(MSG, ec.ECDSA(hashes.SHA256())), MSG, ec.ECDSA(hashes.SHA256()))
    rows = []
    for i in range(n):
        t0 = time.perf_counter(); sig = priv.sign(MSG, ec.ECDSA(hashes.SHA256())); sg = time.perf_counter() - t0
        t0 = time.perf_counter(); pub.verify(sig, MSG, ec.ECDSA(hashes.SHA256())); vf = time.perf_counter() - t0
        rows.append(["ECC", curve, "ECC Signing", "", "", "", sg, vf, i + 1])
    return rows


def blocks(n, suite):
    b = []
    for bits in [1024, 2048, 3072, 4096]:
        b.append(("sig_RSA_%d" % bits, lambda bits=bits: block_rsa_sig(bits, n, 20)))
    for c in ["SECP256K1", "SECP256R1"]:
        b.append(("ops_ECC_%s" % c, lambda c=c: block_ecc_ops(c, n, 20)))
    if suite == "full":
        for bits in RSA_SIZES:
            b.append(("keygen_RSA_%d" % bits, lambda bits=bits: block_keygen("RSA", bits, n, 3)))
            b.append(("ops_RSA_%d" % bits, lambda bits=bits: block_rsa_ops(bits, n, 20)))
        for c, _ in CURVES:
            b.append(("keygen_ECC_%s" % c, lambda c=c: block_keygen("ECC", c, n, 20)))
            if c not in ("SECP256K1", "SECP256R1"):
                b.append(("ops_ECC_%s" % c, lambda c=c: block_ecc_ops(c, n, 20)))
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument("--suite", choices=["baseline", "full"], default="baseline")
    ap.add_argument("--out"); ap.add_argument("--resume")
    ap.add_argument("--allow-battery", action="store_true")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    n = 20 if a.quick else a.iterations
    out = a.resume or a.out or time.strftime("native_%Y%m%d_%H%M%S") + ("_quick" if a.quick else "")
    os.makedirs(out, exist_ok=True)
    csv_path, done_path, log_path = (os.path.join(out, f) for f in ("raw_classical.csv", "done_blocks.txt", "run_log.txt"))

    def log(s):
        print(s, flush=True)
        with open(log_path, "a") as f:
            f.write(s + "\n")

    ac, pct = power_status()
    log("Output folder: %s   suite: %s   iterations per configuration: %d" % (out, a.suite, n))
    log("AC line status now (1 = mains power, 0 = battery, None = not Windows): %s, battery %s %%" % (ac, pct))
    if ac == 0 and not a.allow_battery and not a.quick:
        log("!!! STOP: the laptop is on BATTERY. Plug in the charger, wait 30 seconds, and start again (or use --allow-battery on purpose).")
        sys.exit(1)
    env = environment()
    with open(os.path.join(out, "env.json" if not a.resume else "env_resumed.json"), "w") as f:
        json.dump(env, f, indent=2)
    log(json.dumps(env, indent=1))

    allb = blocks(n, a.suite)
    order = list(range(len(allb)))
    random.Random(SEED).shuffle(order)
    log("block order (seed %d): %s" % (SEED, " ".join(allb[i][0] for i in order)))
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
    new_file = not os.path.exists(csv_path)
    t_start = time.time()
    for k, i in enumerate(order):
        name, fn = allb[i]
        if name in done:
            log("(skip %s: already done)" % name); continue
        gc.collect()
        ac, pct = power_status()
        log("[%d/%d, elapsed %.1f min] %s  start %s UTC  ac=%s" % (k + 1, len(order), (time.time() - t_start) / 60, name,
                                                                  utcnow().strftime("%H:%M:%S"), ac))
        t0 = time.time(); rows = fn(); dt = time.time() - t0
        with open(csv_path, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(COLUMNS); new_file = False
            w.writerows(rows)
        with open(done_path, "a") as f:
            f.write(name + "\n")
        col = {"Key Generation": 3, "RSA Encryption": 4}.get(rows[0][2], 7)      # otherwise the verify column
        vals = [r[col] for r in rows]
        log("    done in %.1f s; mean of first timed column %.6f s over %d iterations" % (dt, sum(vals) / len(vals), len(vals)))
    ac, pct = power_status()
    log("finished %s UTC, ac=%s" % (utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), ac))
    if os.name == "nt" and ac == 0:
        log("!!! WARNING: the laptop was on battery at the end of the run.")


if __name__ == "__main__":
    main()
