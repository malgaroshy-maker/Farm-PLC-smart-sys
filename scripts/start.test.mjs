import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmdirSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { applyPendingRestore, dbPaths, isVirtualOrLinkLocal, keepViteLine, lanAddresses, lanUrls, restartDelay } from './start.mjs';

test('first-run credentials are saved without appearing in launcher output', () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'farm-launcher-credentials-'));
  try {
    const keys = ['SECRET_KEY', 'SIMULATOR_TOKEN', 'ADMIN_PASSWORD'];
    writeFileSync(path.join(root, '.env.example'), keys.map((key) => `${key}=placeholder`).join('\n'));
    const moduleUrl = new URL('./start.mjs', import.meta.url).href;
    const code = `import { ensureEnv } from ${JSON.stringify(moduleUrl)}; ensureEnv(process.argv[1]);`;
    const result = spawnSync(process.execPath, ['--input-type=module', '-e', code, root], { encoding: 'utf8' });
    assert.equal(result.status, 0);
    const output = (result.stdout || '') + (result.stderr || '');
    const saved = readFileSync(path.join(root, '.env'), 'utf8');
    for (const key of keys) {
      const line = saved.split(/\r?\n/).find((entry) => entry.startsWith(`${key}=`));
      const value = line?.slice(key.length + 1);
      assert.ok(value && value !== 'placeholder', `${key} was not generated`);
      assert.ok(!output.includes(value), `${key} appeared in launcher output`);
    }
  } finally {
    rmSync(path.join(root, '.env'), { force: true });
    rmSync(path.join(root, '.env.example'), { force: true });
    rmdirSync(root);
  }
});

test('isVirtualOrLinkLocal filters link-local addresses (169.254.x.x)', () => {
  assert.equal(isVirtualOrLinkLocal('169.254.0.1'), true);
  assert.equal(isVirtualOrLinkLocal('169.254.120.45'), true);
});

test('isVirtualOrLinkLocal filters VirtualBox subnet (192.168.56.x)', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.56.1'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.56.102'), true);
});

test('isVirtualOrLinkLocal filters virtual adapters by interface name', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.56.1', 'VirtualBox Host-Only Network'), true);
  assert.equal(isVirtualOrLinkLocal('172.28.0.1', 'vEthernet (WSL)'), true);
  assert.equal(isVirtualOrLinkLocal('172.18.96.1', 'vEthernet (Default Switch)'), true);
  assert.equal(isVirtualOrLinkLocal('10.0.75.1', 'Hyper-V Virtual Ethernet Adapter'), true);
  assert.equal(isVirtualOrLinkLocal('172.17.0.1', 'docker0'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.49.2', 'Docker Desktop'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.120.1', 'VMware Network Adapter VMnet1'), true);
  assert.equal(isVirtualOrLinkLocal('127.0.0.1', 'Loopback Pseudo-Interface 1'), true);
});

test('isVirtualOrLinkLocal does NOT blanket ban 172.16-31.x.x on normal interfaces (e.g. Wi-Fi / LAN hotspot)', () => {
  assert.equal(isVirtualOrLinkLocal('172.16.0.1', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('172.20.10.5', 'iPhone USB'), false);
  assert.equal(isVirtualOrLinkLocal('172.20.10.2', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('172.31.255.254', 'Ethernet'), false);
});

test('isVirtualOrLinkLocal keeps legitimate local Wi-Fi / LAN addresses', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.1.50', 'Ethernet'), false);
  assert.equal(isVirtualOrLinkLocal('192.168.0.101', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('10.0.0.15', 'en0'), false);
});

test('lanUrls with mocked os.networkInterfaces() filters VirtualBox and returns only real LAN URLs', () => {
  const mockInterfaces = {
    'Ethernet (Unplugged)': [
      { address: '169.254.12.34', family: 'IPv4', internal: false },
    ],
    'VirtualBox Host-Only Ethernet Adapter': [
      { address: '192.168.56.1', family: 'IPv4', internal: false },
    ],
    'vEthernet (Default Switch)': [
      { address: '172.28.0.1', family: 'IPv4', internal: false },
    ],
    'VMware Network Adapter VMnet8': [
      { address: '192.168.120.1', family: 'IPv4', internal: false },
    ],
    'docker0': [
      { address: '172.17.0.1', family: 'IPv4', internal: false },
    ],
    'Loopback Pseudo-Interface 1': [
      { address: '127.0.0.1', family: 'IPv4', internal: true },
    ],
    'Wi-Fi': [
      { address: '192.168.1.150', family: 'IPv4', internal: false },
    ],
    'iPhone USB': [
      { address: '172.20.10.2', family: 'IPv4', internal: false },
    ],
  };

  const urls = lanUrls(4173, mockInterfaces);
  assert.deepEqual(urls, [
    'http://192.168.1.150:4173',
    'http://172.20.10.2:4173',
  ]);
});

test('Vite "Network:" lines: keeps only real LAN addresses, even with ANSI colours', () => {
  const allowed = new Set(['192.168.0.100', '192.168.1.8']);
  const esc = '\x1b';
  const line = (ip) => `  ${esc}[32m➜${esc}[39m  ${esc}[1mNetwork${esc}[22m: ${esc}[36mhttp://${ip}:${esc}[1m4173${esc}[22m/${esc}[39m`;
  assert.equal(keepViteLine(line('169.254.83.107'), allowed), false);
  assert.equal(keepViteLine(line('192.168.56.1'), allowed), false);
  assert.equal(keepViteLine(line('172.28.80.1'), allowed), false); // WSL / Hyper-V vEthernet
  assert.equal(keepViteLine(line('192.168.0.100'), allowed), true);
  assert.equal(keepViteLine(`  ${esc}[32m➜${esc}[39m  ${esc}[1mLocal${esc}[22m:   http://localhost:4173/`, allowed), true);
});

test('lanAddresses drops VirtualBox, vEthernet and link-local adapters', () => {
  const got = lanAddresses({
    'VirtualBox Host-Only Network': [{ address: '192.168.56.1', family: 'IPv4', internal: false }],
    'vEthernet (WSL)': [{ address: '172.28.80.1', family: 'IPv4', internal: false }],
    Ethernet: [{ address: '169.254.83.107', family: 'IPv4', internal: false }],
    'Wi-Fi': [{ address: '192.168.0.100', family: 'IPv4', internal: false }],
  });
  assert.deepEqual([...got], ['192.168.0.100']);
});

test('restartDelay backs off 5s, 10s, 20s, 40s, then once a minute', () => {
  assert.deepEqual([1, 2, 3, 4, 5, 9].map(restartDelay), [5000, 10000, 20000, 40000, 60000, 60000]);
});

test('dbPaths follows DATABASE_URL and BACKUP_DIR', () => {
  const p = dbPaths({ DATABASE_URL: 'sqlite+aiosqlite:///./farm.db' });
  assert.ok(p.db.endsWith(path.join('apps', 'api', 'farm.db')));
  assert.equal(p.backups, path.join(path.dirname(p.db), 'backups'));
  assert.equal(dbPaths({ DATABASE_URL: 'postgresql://x/y' }), null);
});

test('applyPendingRestore swaps the chosen backup in and keeps the old database', () => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'farm-restore-'));
  const backups = path.join(dir, 'backups');
  mkdirSync(backups);
  const db = path.join(dir, 'farm.db');
  const marker = path.join(backups, 'restore.pending');
  const validBackup = 'farm-20261120-030000.db';
  const invalidBackup = 'farm-20261121-030000.db';
  const isWindows = process.platform === 'win32';
  const venvPython = fileURLToPath(new URL(isWindows
    ? '../apps/api/.venv/Scripts/python.exe'
    : '../apps/api/.venv/bin/python', import.meta.url));
  const [cmd, prefix] = existsSync(venvPython) ? [venvPython, []]
    : isWindows ? ['py', ['-3']] : ['python3', []];
  const python = (code, ...args) => {
    const result = spawnSync(cmd, [...prefix, '-c', code, ...args], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    return result.stdout.trim();
  };
  const createDb = (file, name) => python(`
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    db.executescript("CREATE TABLE farms(name); CREATE TABLE zones(id); CREATE TABLE users(id);")
    db.execute("INSERT INTO farms VALUES (?)", [sys.argv[2]])
`, file, name);
  const readName = (file) => python(`
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    print(db.execute("SELECT name FROM farms").fetchone()[0])
`, file);

  try {
    createDb(db, 'current');
    createDb(path.join(backups, validBackup), 'old-good');
    writeFileSync(marker, validBackup);
    const name = applyPendingRestore({ db, backups }, new Date('2026-11-24T10:00:00Z'));
    assert.equal(name, validBackup);
    assert.equal(readName(db), 'old-good');
    assert.equal(existsSync(marker), false);
    assert.equal(readName(path.join(backups, 'pre-restore-20261124-100000.db')), 'current');

    writeFileSync(path.join(backups, invalidBackup), 'not a database');
    for (const invalid of [invalidBackup, '../farm.db']) {
      writeFileSync(marker, invalid);
      assert.equal(applyPendingRestore({ db, backups }), null);
      assert.equal(existsSync(marker), false);
      assert.equal(readName(db), 'old-good');
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
