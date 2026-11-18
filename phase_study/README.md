# Phase study (16-18 November 2026): working archive

Raw results of every run after v11, the kits that produced them, the frozen EdDSA predictions and the analysis
scripts. This is a working archive, not yet the repository layout; scripts in `analysis/` were written for the
review workspace and expect its folder layout (`<work>`).

| folder | contents |
|---|---|
| results/<machine>/ark_phases | 21 circuits, ark back end, phase timers (16-17 Nov) |
| results/<machine>/bellman_phases | 21 circuits, bellman back end (17 Nov) |
| results/<machine>/eddsa_ark, eddsa_bellman | frozen-model test, two EdDSA verifiers (17 Nov) |
| results/<machine>/fast_cached | 21 circuits, cached-matrix prover (18 Nov; laptop and desktop) |
| results/<machine>/original_same_day | 21 circuits, original prover, same day as fast_cached (18 Nov) |
| results/<machine>/eddsa_fast | the two EdDSA verifiers with the cached-matrix prover (18 Nov) |
| results/vm/dev_check_2core | development check on the reviewer's 2-core cloud VM; not a study machine |
| predictions/eddsa_2026-11-17 | predictions written before the EdDSA timings, with checksums |
| tools/kit_fast_v3 | latest run scripts, wrapper, extractor, notebooks, source patches (binaries omitted: rebuild from the patches or use the kit zips) |
| analysis | scripts and summaries used for the numbers reported in chat |

Machines: laptop i7-8665U (8 threads), desktop i7-10700 (16 threads), vm = Colab, Xeon 2.20 GHz, 2 threads.
Every visit in every run is OK and every proof verified with the unchanged `zokrates verify`.
