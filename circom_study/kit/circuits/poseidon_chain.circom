pragma circom 2.0.0;
include "circomlib/circuits/poseidon.circom";
// N sequential Poseidon hashes of one field element (as the ZoKrates Poseidon chain)
template PoseidonChain(N) {
    signal input in;
    signal output out;
    signal s[N + 1];
    component h[N];
    s[0] <== in;
    for (var i = 0; i < N; i++) {
        h[i] = Poseidon(1);
        h[i].inputs[0] <== s[i];
        s[i + 1] <== h[i].out;
    }
    out <== s[N];
}
