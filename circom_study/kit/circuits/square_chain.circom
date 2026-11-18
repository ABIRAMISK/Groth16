pragma circom 2.0.0;
// N constraints s[i+1] = s[i] * s[i]. With x = 1 every witness value is 1 (a "boolean" witness);
// with x = 3 the values are full-width field elements. Same circuit, same keys: only the witness differs.
template SquareChain(N) {
    signal input x;
    signal output y;
    signal s[N + 1];
    s[0] <== x;
    for (var i = 0; i < N; i++) {
        s[i + 1] <== s[i] * s[i];
    }
    y <== s[N];
}
