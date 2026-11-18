pragma circom 2.0.0;
include "circomlib/circuits/sha256/sha256.circom";
// SHA-256 of a 256-bit message (one compression block, as circomlib pads it)
component main = Sha256(256);
