// Median proving time per circuit (measured passes only) and the time to the main snarkjs steps.
const fs = require('fs'); const path = require('path'); const R = process.argv[2];
const rows = fs.readFileSync(path.join(R, 'results.csv'), 'utf8').trim().split('\n').slice(1).map(l => l.split(','));
const med = (a) => { a = [...a].sort((x, y) => x - y); const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
const ids = [...new Set(rows.map(r => r[0]))];
console.log('circuit          passes  prove_s  witness_s  verified');
for (const id of ids) {
  const r = rows.filter(x => x[0] === id && +x[1] >= 1); const use = r.length ? r : rows.filter(x => x[0] === id);
  console.log(id.padEnd(16), String(use.length).padStart(6), med(use.map(x => +x[3])).toFixed(3).padStart(8), med(use.map(x => +x[2])).toFixed(3).padStart(10), use.every(x => x[4] === '1') ? '   all' : '   NOT ALL');
}
