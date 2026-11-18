// Runs a command and writes each output line with the milliseconds since start; last line "EXIT <code>".
// usage: TSLOG=file node ts.js <command> <args...>
const { spawn } = require('child_process');
const fs = require('fs');
const t0 = process.hrtime.bigint();
const ms = () => (Number(process.hrtime.bigint() - t0) / 1e6).toFixed(1);
const out = fs.createWriteStream(process.env.TSLOG);
const p = spawn(process.argv[2], process.argv.slice(3), { shell: process.platform === 'win32' });
const tap = (s) => { let b = ''; s.on('data', (d) => { b += d; let i; while ((i = b.indexOf('\n')) >= 0) { out.write(ms() + '\t' + b.slice(0, i).replace(/\r$/, '') + '\n'); b = b.slice(i + 1); } }); };
tap(p.stdout); tap(p.stderr);
p.on('close', (c) => { out.write(ms() + '\tEXIT ' + c + '\n'); out.end(() => process.exit(c === null ? 1 : c)); });
