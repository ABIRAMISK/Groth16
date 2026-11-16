# Third-party notice

Everything in this repository is released under the MIT licence (`LICENSE`), with one exception.

Three files contain code from the ZoKrates standard library, which is released under the GNU Lesser General Public License v3 (<https://github.com/Zokrates/ZoKrates>). These files keep that licence. The licence texts are in `LICENSES/LGPL-3.0.txt` and `LICENSES/GPL-3.0.txt` (the LGPL incorporates the GPL).

| File | Origin |
|---|---|
| `zkp_v4/circuits/sha256_hash_circuit.zok` and `zkp_v4/generators/sha256/hash_circuit.zok` (the same file) | Everything before the line `// --- Helper Functions for Bit Conversion ---` is the code of `hashes/sha256/shaRound.zok` and `hashes/sha256/sha256.zok` of the ZoKrates 0.8.7 standard library, with the comments removed and `main` renamed to `shaRound` and `sha256_main`. The helper functions and `main` after that line were written for this study. |
| `data/table_ecc/eddsa_poseidon_variant.zok` | Adapted from `signatures/verifyEddsa.zok` of the same standard library, with Poseidon in place of SHA-256 as the challenge hash. |

The other `.zok` files import functions from the standard library (for example `hashes/poseidon/poseidon`, `ecc/edwardsAdd`, `signatures/verifyEddsa`) but do not contain its code. The ZoKrates compiler and its standard library are not part of this repository; the harness runs the official `zokrates/zokrates:0.8.7` image or the 0.8.7 release binary.
