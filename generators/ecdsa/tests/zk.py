"""Thin wrapper around a native ZoKrates 0.8.7 binary, used only by the tests in this folder.

Set  ZOKRATES_BIN=/path/to/zokrates  and  ZOKRATES_STDLIB=/path/to/stdlib  (the stdlib folder of the same release).
Test circuits are compiled in  ECDSA_TEST_WORK  (default: ./work next to this file).
"""
import os, subprocess, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ZOK = os.environ.get("ZOKRATES_BIN", "zokrates")
STD = os.environ.get("ZOKRATES_STDLIB", "")
WORK = os.environ.get("ECDSA_TEST_WORK", os.path.join(HERE, "work"))

def run(cmd, cwd, timeout=None):
    env = dict(os.environ)
    if STD:
        env["ZOKRATES_STDLIB"] = STD
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    out = p.stdout.read()
    _, st, ru = os.wait4(p.pid, 0)
    rc = os.WEXITSTATUS(st) if os.WIFEXITED(st) else -1
    return rc, out.decode(errors="replace"), time.time() - t0, ru.ru_maxrss / 1024.0   # peak RSS in MB (Linux)

def compile_src(src, work, name="main.zok"):
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, name), "w") as f:
        f.write(src)
    rc, out, t, mb = run([ZOK, "compile", "-i", name], work)
    m = [l for l in out.splitlines() if "constraints" in l.lower()]
    return rc, (m[0].split(":")[-1].strip() if m else None), out, t, mb

def witness(args, work, verbose=False):
    cmd = [ZOK, "compute-witness", "-a"] + [str(a) for a in args]
    if verbose: cmd.insert(2, "--verbose")
    rc, out, t, mb = run(cmd, work)
    return rc, out, t, mb
