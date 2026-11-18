// Prints constraints, wires, public inputs/outputs and non-zero terms of A, B, C from a circom .r1cs file.
const fs = require('fs');
const b = fs.readFileSync(process.argv[2]);
let o = 4 + 4; const ns = b.readUInt32LE(o); o += 4;
let fsz = 0, hdr = {}, nnz = [0, 0, 0];
const secs = [];
for (let k = 0; k < ns; k++) { const t = b.readUInt32LE(o); const sz = Number(b.readBigUInt64LE(o + 4)); secs.push([t, o + 12, sz]); o += 12 + sz; }
for (const [t, p] of secs) if (t === 1) { fsz = b.readUInt32LE(p); let q = p + 4 + fsz; hdr = { wires: b.readUInt32LE(q), pub_out: b.readUInt32LE(q + 4), pub_in: b.readUInt32LE(q + 8), prv_in: b.readUInt32LE(q + 12), constraints: b.readUInt32LE(q + 24) }; }
for (const [t, p] of secs) if (t === 2) { let q = p; for (let c = 0; c < hdr.constraints; c++) for (let m = 0; m < 3; m++) { const n = b.readUInt32LE(q); q += 4 + n * (4 + fsz); nnz[m] += n; } }
console.log(JSON.stringify({ ...hdr, nnz_A: nnz[0], nnz_B: nnz[1], nnz_C: nnz[2] }));
