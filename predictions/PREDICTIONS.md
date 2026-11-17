# Frozen-model predictions for the two EdDSA verifiers

Written on 17 November 2026, before either circuit was timed on the laptop, the desktop or the VM.
The checksum of `eddsa_predictions.json` is in `SHA256SUMS.txt`; keep both files unchanged.

## What is predicted

The inner `generate-proof` time (median of five measured passes after one warm-up, as in every other run) of

| id | circuit | constraints | non-zero terms per constraint |
|---|---|---|---|
| eddsa_sha256 | BabyJubJub EdDSA verifier of the ZoKrates 0.8.7 standard library (SHA-256 challenge), with the standard library's own test signature | 94,181 | 32.5 |
| eddsa_poseidon | the same verifier with a Poseidon challenge hash (`table_ecc/eddsa_poseidon_variant.zok`), with a signature generated for this test | 15,211 | 4.5 |

Neither circuit, nor any circuit of the EdDSA family, is in the training data.

## Predictions (seconds)

Models M0, M1 and M3 as in the paper, fitted on the 21 circuits of the 13 November sessions (ark back end).
The phase model is fitted on the instrumented runs of 16-17 November.

| machine | back end | circuit | M0 | M1 | M3 | phase model | phase model: front end |
|---|---|---|---|---|---|---|---|
| laptop | ark | eddsa_sha256 | 2.43 | 4.90 | 3.40 | 3.12 | 1.86 |
| laptop | ark | eddsa_poseidon | 0.49 | 0.40 | 0.56 | 0.49 | 0.11 |
| laptop | bellman | eddsa_sha256 | | | | 2.92 | 1.64 |
| laptop | bellman | eddsa_poseidon | | | | 0.42 | 0.07 |
| desktop | ark | eddsa_sha256 | 1.31 | 2.36 | 1.98 | 1.76 | 1.23 |
| desktop | ark | eddsa_poseidon | 0.29 | 0.25 | 0.29 | 0.23 | 0.07 |
| desktop | bellman | eddsa_sha256 | | | | 1.62 | 1.08 |
| desktop | bellman | eddsa_poseidon | | | | 0.18 | 0.05 |
| VM | ark | eddsa_sha256 | 6.91 | 18.28 | 9.80 | | |
| VM | ark | eddsa_poseidon | 1.17 | 0.93 | 1.87 | | |

Full values, coefficients and the features used are in `eddsa_predictions.json`.

`method/` holds the scripts and the two feature files that produced these numbers, as a record. They call the analysis scripts of the review and are not yet self-contained; a self-contained version goes to the repository together with the results.

## How the result will be reported

Every prediction above is reported against the measurement, including the ones that miss. Nothing is refitted.

## Things known before timing

* eddsa_sha256 has 32.5 non-zero terms per constraint, above the training range (3.75 to 28.24): its predictions are an extrapolation in that feature. Its matrix C alone holds 2.8 million non-zero terms.
* The kit was tested once on a 2-core cloud VM that is not one of the study machines (4.50 s and 0.62 s, one pass). The predictions were written before that test, and the test does not enter any model.
* The Poseidon variant is a cost illustration, not a vetted signature scheme; the signature used for it satisfies the verifier's equation and a wrong signature is rejected.
