#!/usr/bin/env python3
"""Writes the four synthetic circuits of the mechanism experiment into ../../circuits/.
   synth_full_<k>.zok : x_(i+1) = x_i*x_i + 1          N steps, 1 constraint per step,  N+1 constraints, every witness value a full-width field element
   synth_bool_<k>.zok : (b,d) -> (b != d, b || d)      N steps, 2 constraints per step, 2N+2 constraints, every witness value 0 or 1
   Matched pairs: 100,00x constraints (N = 100000 and 50000) and 300,00x constraints (N = 300000 and 150000)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "..", "circuits")
FULL = """// Synthetic circuit, full-width witness: x_(i+1) = x_i * x_i + 1, N steps.
// One multiplication constraint per step (N+1 constraints in all); every intermediate value is a pseudo-random 254-bit field element.
const u32 N = {n};
def main(private field x0) -> field {{
    field mut x = x0;
    for u32 i in 0..N {{
        x = x * x + 1;
    }}
    return x;
}}
"""
BOOL = """// Synthetic circuit, boolean witness: (b, d) -> (b != d, b || d), N steps.
// Two constraints per step (2N+2 in all); every intermediate value is 0 or 1.
const u32 N = {n};
def main(private bool b0, private bool d0) -> bool {{
    bool mut b = b0;
    bool mut d = d0;
    for u32 i in 0..N {{
        bool nb = b != d;
        bool nd = b || d;
        b = nb;
        d = nd;
    }}
    return b;
}}
"""
for tag, nf, nb in (("100k", 100000, 50000), ("300k", 300000, 150000)):
    open(os.path.join(OUT, f"synth_full_{tag}.zok"), "w", newline="\n").write(FULL.format(n=nf))
    open(os.path.join(OUT, f"synth_bool_{tag}.zok"), "w", newline="\n").write(BOOL.format(n=nb))
open(os.path.join(OUT, "synth_full_args.txt"), "w", newline="\n").write("3\n")
open(os.path.join(OUT, "synth_bool_args.txt"), "w", newline="\n").write("1 0\n")
print("written to", os.path.normpath(OUT))
