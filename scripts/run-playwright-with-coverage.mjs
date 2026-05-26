import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';


const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv[2] === 'web' ? 'web' : 'root';
const extraArgs = process.argv.slice(mode === 'web' ? 3 : 2);
const cwd = mode === 'web' ? path.join(repoRoot, 'web') : repoRoot;
const passthrough = extraArgs.length ? ` -- ${extraArgs.map((arg) => JSON.stringify(arg)).join(' ')}` : '';
const command = `npm exec playwright test${passthrough}`;

const child = spawn(command, {
  cwd,
  shell: true,
  stdio: 'inherit',
  env: {
    ...process.env,
    PW_COLLECT_COVERAGE: '1',
  },
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }

  process.exit(code ?? 1);
});