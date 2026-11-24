#!/usr/bin/env node
/**
 * Algaroshy Farm — one-window launcher (API + simulator + web).
 *
 *   node scripts/start.mjs            dev mode: hot reload, http://localhost:5173
 *   node scripts/start.mjs demo       demo mode: production build, phone/LAN access, installable PWA
 *   node scripts/start.mjs server     farm server (G7): like demo, but headless (no browser) and any
 *                                     part that stops is restarted. Run it from a service: docs/FARM_SERVER.md
 *   node scripts/start.mjs demo plc   (G5) the app drives a virtual PLC over Modbus TCP: the simulator
 *                                     plays the PLC behind the real register map (add to any mode)
 *   node scripts/start.mjs demo plcsim (G5) the REAL PLC program in PLCSIM Advanced (instance running,
 *                                     see plc/README.md); the simulator plays the farm around it
 *   node scripts/start.mjs --smoke    start everything, wait until healthy, then stop (self-test)
 *
 * First run sets itself up: Python venv + requirements, pnpm install, and a .env
 * with generated secrets. API_PORT in .env is the single source for the API port;
 * the simulator and the web proxy are pointed at it automatically.
 * Ctrl+C (or closing the window) stops every process it started — no orphans.
 * A restore chosen in Settings → Backups is applied here, before the database is opened.
 */
import { spawn, spawnSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { appendFileSync, copyFileSync, existsSync, mkdirSync, readFileSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const API_DIR = path.join(ROOT, 'apps', 'api');
const SIM_DIR = path.join(ROOT, 'apps', 'simulator');
const WEB_DIR = path.join(ROOT, 'apps', 'web');
const RUN_DIR = path.join(ROOT, '.run');
const IS_WIN = process.platform === 'win32';
const VENV_PY = IS_WIN ? path.join(API_DIR, '.venv', 'Scripts', 'python.exe') : path.join(API_DIR, '.venv', 'bin', 'python');

const args = process.argv.slice(2);
const SERVER = args.includes('server');
const VIRTUAL_PLC = args.includes('plc');
const PLCSIM = args.includes('plcsim');
const MODE = args.includes('demo') || SERVER ? 'demo' : 'dev';
const SMOKE = args.includes('--smoke');
const RESET = args.includes('reset');
const OPEN_BROWSER = !SMOKE && !SERVER && !args.includes('--no-open');

const ANSI = /\x1b\[[0-9;]*m/g;

// ── output ──────────────────────────────────────────────────────────────
const C = { api: 36, sim: 35, web: 33, setup: 32, err: 31, info: 37 };
const color = (n, s) => (process.stdout.isTTY ? `\x1b[${n}m${s}\x1b[0m` : s);
// farm server: also keep a log file (logs/farm-server.log, rotated at 5 MB, 3 old copies)
const LOG_FILE = SERVER ? path.join(ROOT, 'logs', 'farm-server.log') : null;
let logWrites = 0;
function rotateLog() {
  try {
    if (statSync(LOG_FILE).size < 5 * 1024 * 1024) return;
  } catch {
    return;
  }
  for (let i = 3; i >= 1; i--) {
    const from = i === 1 ? LOG_FILE : `${LOG_FILE}.${i - 1}`;
    if (existsSync(from)) renameSync(from, `${LOG_FILE}.${i}`);
  }
}
const log = (tag, msg) => {
  console.log(`${color(C[tag] ?? 37, `[${tag}]`.padEnd(8))} ${msg}`);
  if (!LOG_FILE) return;
  try {
    if (logWrites++ % 200 === 0) {
      mkdirSync(path.dirname(LOG_FILE), { recursive: true });
      rotateLog();
    }
    appendFileSync(LOG_FILE, `${new Date().toISOString()} [${tag}] ${String(msg).replace(ANSI, '')}\n`);
  } catch {
    /* logging must never stop the farm */
  }
};
function die(msg) {
  log('err', msg);
  shutdown(1);
}

// ── .env ────────────────────────────────────────────────────────────────
function parseEnv(text) {
  const env = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const i = line.indexOf('=');
    let value = line.slice(i + 1).split(/\s+#/)[0].trim();
    if (/^(['"]).*\1$/.test(value)) value = value.slice(1, -1);
    env[line.slice(0, i).trim()] = value;
  }
  return env;
}

function setEnvValue(text, key, value) {
  const re = new RegExp(`^${key}=.*$`, 'm');
  return re.test(text) ? text.replace(re, `${key}=${value}`) : `${text.trimEnd()}\n${key}=${value}\n`;
}

const secret = (n) => randomBytes(n).toString('base64url');

function ensureEnv() {
  const envPath = path.join(ROOT, '.env');
  if (existsSync(envPath)) return { env: parseEnv(readFileSync(envPath, 'utf8')), generated: null };
  let text = readFileSync(path.join(ROOT, '.env.example'), 'utf8');
  const generated = { ADMIN_PASSWORD: secret(9) };
  text = setEnvValue(text, 'SECRET_KEY', secret(48));
  text = setEnvValue(text, 'SIMULATOR_TOKEN', secret(24));
  text = setEnvValue(text, 'ADMIN_PASSWORD', generated.ADMIN_PASSWORD);
  if (process.env.API_PORT) text = setEnvValue(text, 'API_PORT', process.env.API_PORT);
  writeFileSync(envPath, text);
  log('setup', 'Created .env with generated secrets.');
  if (existsSync(path.join(API_DIR, 'farm.db'))) {
    log('setup', 'Note: an existing farm.db keeps its old admin password (the seed never overwrites users).');
  }
  return { env: parseEnv(text), generated };
}

// ── prerequisites & setup ───────────────────────────────────────────────
/** On Windows, .cmd shims (pnpm) can't be spawned directly; go through cmd.exe without shell string-joining. */
function resolveCmd(cmd, cmdArgs) {
  return IS_WIN && !/\.exe$/i.test(cmd) ? ['cmd.exe', ['/d', '/s', '/c', cmd, ...cmdArgs]] : [cmd, cmdArgs];
}

function run(cmd, cmdArgs, opts = {}) {
  const [c, a] = resolveCmd(cmd, cmdArgs);
  const r = spawnSync(c, a, { stdio: 'inherit', ...opts });
  return r.status === 0;
}

function findPython() {
  for (const [cmd, pre] of IS_WIN ? [['py', ['-3']], ['python', []]] : [['python3', []], ['python', []]]) {
    const r = spawnSync(cmd, [...pre, '-c', 'import sys;print(sys.version_info[:2]>=(3,11))'], { encoding: 'utf8', shell: false });
    if (r.status === 0 && r.stdout.trim() === 'True') return [cmd, pre];
  }
  return null;
}

const hashFile = (f) => createHash('sha256').update(readFileSync(f)).digest('hex');

function ensurePython() {
  const req = path.join(API_DIR, 'requirements.txt');
  const marker = path.join(API_DIR, '.venv', '.requirements.sha256');
  if (!existsSync(VENV_PY)) {
    const py = findPython();
    if (!py) die('Python 3.11+ not found. Install it from python.org (tick "Add to PATH"), then run again.');
    log('setup', 'Creating Python virtual environment (first run)…');
    if (!run(py[0], [...py[1], '-m', 'venv', path.join(API_DIR, '.venv')])) die('Could not create the Python venv.');
  }
  if (!existsSync(marker) || readFileSync(marker, 'utf8') !== hashFile(req)) {
    log('setup', 'Installing Python requirements…');
    if (!run(VENV_PY, ['-m', 'pip', 'install', '-q', '-r', req])) die('pip install failed (see output above).');
    writeFileSync(marker, hashFile(req));
  }
}

function ensureNode() {
  const major = Number(process.versions.node.split('.')[0]);
  if (major < 20) die(`Node.js 20+ required (found ${process.versions.node}).`);
  if (spawnSync(...resolveCmd('pnpm', ['--version']), { encoding: 'utf8' }).status !== 0) {
    die('pnpm not found. Run:  corepack enable   (or: npm i -g pnpm), then run again.');
  }
  const lock = path.join(ROOT, 'pnpm-lock.yaml');
  const stamp = path.join(ROOT, 'node_modules', '.modules.yaml');
  if (!existsSync(stamp) || statSync(lock).mtimeMs > statSync(stamp).mtimeMs) {
    log('setup', 'Installing JavaScript dependencies (pnpm install)…');
    if (!run('pnpm', ['install', '--frozen-lockfile'], { cwd: ROOT })) die('pnpm install failed (see output above).');
  }
}

/** Something already answers on the port? (Windows lets a second process bind a port
 *  whose owner set SO_REUSEADDR — e.g. Python's http.server — so a bind test alone lies.) */
function answers(port) {
  return new Promise((resolve) => {
    const sock = net.connect({ port, host: '127.0.0.1' });
    sock.setTimeout(800);
    sock.once('connect', () => {
      sock.destroy();
      resolve(true);
    });
    sock.once('timeout', () => {
      sock.destroy();
      resolve(false);
    });
    sock.once('error', () => resolve(false));
  });
}

function canBind(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, '0.0.0.0');
  });
}

async function portFree(port) {
  return !(await answers(port)) && (await canBind(port));
}

// ── restore (G7) ────────────────────────────────────────────────────────
/** Where the API keeps farm.db and its backups (same rules as app/services/backup.py). */
function dbPaths(env) {
  const url = process.env.DATABASE_URL || env.DATABASE_URL || 'sqlite+aiosqlite:///./farm.db';
  if (!url.startsWith('sqlite')) return null;
  const raw = url.split('///')[1];
  if (!raw || raw === ':memory:') return null;
  const db = path.resolve(API_DIR, raw);
  const bdir = process.env.BACKUP_DIR || env.BACKUP_DIR || 'backups';
  return { db, backups: path.isAbsolute(bdir) ? bdir : path.join(path.dirname(db), bdir) };
}

/** Swap in the backup chosen in Settings → Backups. The current DB is kept as pre-restore-*.db. */
function applyPendingRestore(paths, stamp = new Date()) {
  if (!paths) return null;
  const marker = path.join(paths.backups, 'restore.pending');
  if (!existsSync(marker)) return null;
  const name = readFileSync(marker, 'utf8').trim();
  rmSync(marker, { force: true });
  const src = path.join(paths.backups, name);
  if (!/^farm-\d{8}-\d{6}\.db$/.test(name) || !existsSync(src)) {
    log('err', `Restore skipped: backup "${name}" not found.`);
    return null;
  }
  const ts = stamp.toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
  if (existsSync(paths.db)) copyFileSync(paths.db, path.join(paths.backups, `pre-restore-${ts}.db`));
  for (const ext of ['-wal', '-shm']) rmSync(paths.db + ext, { force: true });
  copyFileSync(src, paths.db);
  log('setup', `Restored the database from ${name} (the previous one is kept as pre-restore-${ts}.db).`);
  return name;
}

// ── child processes ─────────────────────────────────────────────────────
const children = [];
let stopping = false;
const restarts = {};
/** 5 s, 10 s, 20 s, 40 s, then once a minute. */
const restartDelay = (tries) => Math.min(60_000, 5_000 * 2 ** Math.max(0, tries - 1));

function start(tag, cmd, cmdArgs, opts) {
  const [c, a] = resolveCmd(cmd, cmdArgs);
  const child = spawn(c, a, {
    cwd: opts.cwd,
    env: { ...process.env, ...opts.env, PYTHONUNBUFFERED: '1', FORCE_COLOR: '1' },
    detached: !IS_WIN, // own process group on POSIX so we can kill the whole tree
    windowsHide: true,
  });
  const pipe = (stream) => {
    let buf = '';
    stream.on('data', (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const l of lines) {
        if (!l.trim()) continue;
        if (tag === 'web' && !keepViteLine(l)) continue;
        log(tag, l);
      }
    });
  };
  pipe(child.stdout);
  pipe(child.stderr);
  child.on('exit', (code) => {
    if (stopping) return;
    log('err', `${tag} exited (code ${code}).`);
    if (SERVER && !SMOKE) {
      // farm server: never give up — restart this part, backing off up to a minute
      const i = children.findIndex((c) => c.child === child);
      if (i >= 0) children.splice(i, 1);
      const tries = (restarts[tag] = (restarts[tag] ?? 0) + 1);
      const delay = restartDelay(tries);
      log('info', `Restarting ${tag} in ${delay / 1000}s…`);
      setTimeout(() => {
        if (!stopping) start(tag, cmd, cmdArgs, opts);
      }, delay);
      return;
    }
    if (opts.critical) shutdown(1);
  });
  children.push({ tag, child });
  // the launcher goes first, so stop.bat also stops a farm server that would restart its parts
  const pids = [{ tag: 'launcher', pid: process.pid }, ...children.map((c) => ({ tag: c.tag, pid: c.child.pid }))];
  writeFileSync(path.join(RUN_DIR, 'pids.json'), JSON.stringify(pids));
  return child;
}

function killTree(pid) {
  if (!pid) return;
  try {
    if (IS_WIN) spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    else process.kill(-pid, 'SIGTERM');
  } catch {
    /* already gone */
  }
}

function shutdown(code = 0) {
  if (stopping) return;
  stopping = true;
  if (children.length) log('info', 'Stopping all services…');
  for (const { child } of [...children].reverse()) killTree(child.pid);
  rmSync(path.join(RUN_DIR, 'pids.json'), { force: true });
  process.exit(code);
}

for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP', 'SIGBREAK']) process.on(sig, () => shutdown(0));
process.on('exit', () => {
  if (!stopping) for (const { child } of children) killTree(child.pid);
});

async function waitFor(url, label, timeoutMs = 60_000, check = (r) => r.ok) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    try {
      const r = await fetch(url);
      if (await check(r)) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 700));
  }
  die(`${label} did not become ready within ${timeoutMs / 1000}s.`);
}

function isVirtualOrLinkLocal(addr, ifaceName = '') {
  if (!addr) return true;
  // 169.254.0.0/16 (link-local)
  if (addr.startsWith('169.254.')) return true;
  // 192.168.56.0/24 (VirtualBox default host-only subnet)
  if (addr.startsWith('192.168.56.')) return true;
  // 127.0.0.0/8 (loopback)
  if (addr.startsWith('127.')) return true;
  // Exclude virtual adapters by interface name (VirtualBox, vEthernet/Hyper-V, Docker, WSL, VMware, Loopback)
  if (ifaceName) {
    const lower = ifaceName.toLowerCase();
    if (
      lower.includes('virtualbox') ||
      lower.includes('vethernet') ||
      lower.includes('hyper-v') ||
      lower.includes('docker') ||
      lower.includes('wsl') ||
      lower.includes('vmware') ||
      lower.includes('loopback')
    ) {
      return true;
    }
  }
  return false;
}


/** IPv4 addresses of real LAN adapters (same rule as the phone list). */
function lanAddresses(interfaces = os.networkInterfaces()) {
  const out = new Set();
  for (const [name, addrs] of Object.entries(interfaces)) {
    for (const info of addrs ?? []) {
      if (info.family === 'IPv4' && !info.internal && !isVirtualOrLinkLocal(info.address, name)) out.add(info.address);
    }
  }
  return out;
}

/**
 * Vite prints its own "Network:" list, coloured with ANSI codes, and knows nothing about
 * adapter names. Keep a Network line only if its address is a real LAN adapter.
 */
function keepViteLine(line, allowed = lanAddresses()) {
  const m = line.replace(ANSI, '').match(/Network:\s+https?:\/\/([^:/\s]+)/i);
  return !m || allowed.has(m[1]);
}

function lanUrls(port, interfaces = os.networkInterfaces()) {
  const urls = [];
  for (const [name, addrs] of Object.entries(interfaces)) {
    if (!addrs) continue;
    for (const info of addrs) {
      if (info.family === 'IPv4' && !info.internal && !isVirtualOrLinkLocal(info.address, name)) {
        urls.push(`http://${info.address}:${port}`);
      }
    }
  }
  return urls;
}

function openBrowser(url) {
  const [cmd, a] = IS_WIN ? ['cmd', ['/c', 'start', '', url]] : process.platform === 'darwin' ? ['open', [url]] : ['xdg-open', [url]];
  spawn(cmd, a, { stdio: 'ignore', detached: true }).unref();
}

// ── main ────────────────────────────────────────────────────────────────
async function main() {
  mkdirSync(RUN_DIR, { recursive: true });
  log('info', `Algaroshy Farm — ${SERVER ? 'farm server' : MODE + ' mode'}${SMOKE ? ' (smoke test)' : ''}`);

  if (!existsSync(path.join(ROOT, '.env')) && !existsSync(path.join(ROOT, '.env.example'))) die('.env.example missing.');
  const { env, generated } = ensureEnv();
  ensurePython();
  ensureNode();

  const apiPort = Number(process.env.API_PORT || env.API_PORT || 8000);
  const webPort = Number(process.env.WEB_PORT || env.WEB_PORT || (MODE === 'demo' ? 4173 : 5173));
  for (const [port, what] of [
    [apiPort, 'API'],
    [webPort, 'web app'],
  ]) {
    if (!(await portFree(port))) {
      die(
        `Port ${port} (${what}) is already in use by another program.\n` +
          `         Free it, or pick another port in .env (API_PORT / WEB_PORT). ` +
          `If an old copy of this app is still running, run:  ${IS_WIN ? 'stop.bat' : './stop.sh'}`,
      );
    }
  }
  const apiBase = `http://127.0.0.1:${apiPort}`;
  const shared = { API_PORT: String(apiPort), API_URL: `${apiBase}/api/v1`, VITE_PROXY_TARGET: apiBase };

  applyPendingRestore(dbPaths(env));
  log('setup', 'Migrating database…');
  if (!run(VENV_PY, ['-m', 'alembic', 'upgrade', 'head'], { cwd: API_DIR, env: { ...process.env, ...shared } })) die('Database migration failed.');
  log('setup', 'Seeding (skipped if already seeded)…');
  run(VENV_PY, ['-m', 'app.seed'], { cwd: API_DIR, env: { ...process.env, ...shared } });
  if (RESET) {
    log('setup', 'Clearing alarms, commands, events and telemetry for a clean demo (users and settings are kept)…');
    if (!run(VENV_PY, ['-m', 'app.reset_demo'], { cwd: API_DIR, env: { ...process.env, ...shared } })) die('Demo reset failed.');
  }

  // API: in dev, --reload; the whole tree is killed on exit so no orphaned workers remain.
  start('api', VENV_PY, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(apiPort), ...(MODE === 'dev' && !SMOKE ? ['--reload'] : [])], {
    cwd: API_DIR,
    env: shared,
    critical: true,
  });
  await waitFor(`${apiBase}/health`, 'API');
  log('api', `ready on ${apiBase}  (docs: ${apiBase}/docs)`);

  const modbusMap = path.join(SIM_DIR, 'modbus_map.example.json');
  const simEnv = PLCSIM
    ? {
        ...shared,
        CONTROLLER_ADAPTER: 'modbus',
        PLCSIM_PLANT: '1',
        MODBUS_MAP: modbusMap,
        MODBUS_HOST: process.env.PLCSIM_HOST || env.PLCSIM_HOST || '192.168.0.1',
        PLCSIM_INSTANCE: process.env.PLCSIM_INSTANCE || env.PLCSIM_INSTANCE || 'PLC',
      }
    : VIRTUAL_PLC
      ? { ...shared, CONTROLLER_ADAPTER: 'modbus', VIRTUAL_PLC: '1', MODBUS_MAP: modbusMap }
      : shared;
  if (PLCSIM) log('setup', `PLCSIM: the app talks Modbus TCP to the real PLC program at ${simEnv.MODBUS_HOST}; the simulator plays the farm.`);
  else if (VIRTUAL_PLC) log('setup', 'Virtual PLC: the app talks Modbus TCP to the simulator playing the farm PLC.');
  start('sim', VENV_PY, ['-m', 'src.main'], { cwd: SIM_DIR, env: simEnv });

  if (MODE === 'demo') {
    log('setup', 'Building the web app (production)…');
    if (!run('pnpm', ['--filter', '@algaroshy/web', 'run', 'build'], { cwd: ROOT, env: { ...process.env, ...shared } })) die('Web build failed.');
    start('web', 'pnpm', ['--filter', '@algaroshy/web', 'exec', 'vite', 'preview', '--host', '--port', String(webPort), '--strictPort'], {
      cwd: ROOT,
      env: shared,
      critical: true,
    });
  } else {
    start('web', 'pnpm', ['--filter', '@algaroshy/web', 'exec', 'vite', '--port', String(webPort), '--strictPort'], {
      cwd: ROOT,
      env: shared,
      critical: true,
    });
  }
  const webUrl = `http://localhost:${webPort}`;
  await waitFor(webUrl, 'Web app');

  // wait until the simulator is feeding live data through the web proxy
  const token = `Bearer ${env.SIMULATOR_TOKEN || 'dev-simulator-token'}`;
  await waitFor(`${webUrl}/api/v1/zones`, 'Simulator link', 60_000, async () => {
    const r = await fetch(`${webUrl}/api/v1/state/map`, { headers: { Authorization: token } });
    return r.ok && (await r.json()).data_fresh === true;
  });

  console.log('');
  log('info', color(32, `Ready → ${webUrl}`));
  if (MODE === 'demo') for (const u of lanUrls(webPort)) log('info', `Phone on the same Wi-Fi → ${u}  (install: browser menu → "Add to Home screen")`);
  log('info', `Login: ${env.ADMIN_USERNAME || 'admin'} / ${generated ? generated.ADMIN_PASSWORD + '  (generated now — saved in .env)' : 'ADMIN_PASSWORD from .env'}`);
  log('info', 'Press Ctrl+C to stop everything.');

  if (SMOKE) {
    log('info', 'Smoke test passed — shutting down.');
    shutdown(0);
  }
  if (OPEN_BROWSER) openBrowser(webUrl);
}

function isEntrypoint() {
  if (!process.argv[1]) return false;
  try {
    const metaPath = realpathSync(fileURLToPath(import.meta.url)).toLowerCase();
    const argvPath = realpathSync(path.resolve(process.argv[1])).toLowerCase();
    return metaPath === argvPath;
  } catch {
    return path.resolve(fileURLToPath(import.meta.url)).toLowerCase() === path.resolve(process.argv[1]).toLowerCase();
  }
}

if (isEntrypoint()) {
  main().catch((e) => die(e?.stack || String(e)));
}

export { applyPendingRestore, dbPaths, isVirtualOrLinkLocal, keepViteLine, lanAddresses, lanUrls, restartDelay };
