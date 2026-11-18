#!/usr/bin/env node
/**
 * Safety net: stop anything the launcher left behind (e.g. after a crash).
 *
 * Kills (1) the process trees recorded in .run/pids.json and (2) processes listening
 * on this project's ports (API_PORT, 5173, 4173) whose command line is clearly ours
 * (uvicorn app.main / vite / src.main). Other programs on those ports are reported,
 * never killed.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const IS_WIN = process.platform === 'win32';
const OURS = /uvicorn\s+app\.main|vite|-m\s+src\.main/i;

function envPort() {
  try {
    const m = readFileSync(path.join(ROOT, '.env'), 'utf8').match(/^API_PORT=(\d+)/m);
    return m ? Number(m[1]) : 8000;
  } catch {
    return 8000;
  }
}

function killTree(pid) {
  if (IS_WIN) spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
  else spawnSync('kill', ['-TERM', `-${pid}`], { stdio: 'ignore' }) || spawnSync('kill', ['-TERM', String(pid)], { stdio: 'ignore' });
}

function listeners(port) {
  if (IS_WIN) {
    const out = spawnSync('netstat', ['-ano', '-p', 'TCP'], { encoding: 'utf8' }).stdout || '';
    return [...new Set(out.split(/\r?\n/).filter((l) => /LISTENING/.test(l) && new RegExp(`:${port}\\s`).test(l)).map((l) => Number(l.trim().split(/\s+/).pop())))];
  }
  const out = spawnSync('lsof', ['-ti', `tcp:${port}`, '-sTCP:LISTEN'], { encoding: 'utf8' }).stdout || '';
  return out.split(/\s+/).filter(Boolean).map(Number);
}

function commandLine(pid) {
  if (IS_WIN) {
    const r = spawnSync('powershell', ['-NoProfile', '-Command', `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`], { encoding: 'utf8' });
    return (r.stdout || '').trim();
  }
  return (spawnSync('ps', ['-o', 'args=', '-p', String(pid)], { encoding: 'utf8' }).stdout || '').trim();
}

let stopped = 0;
const pidFile = path.join(ROOT, '.run', 'pids.json');
if (existsSync(pidFile)) {
  for (const { tag, pid } of JSON.parse(readFileSync(pidFile, 'utf8'))) {
    killTree(pid);
    console.log(`stopped ${tag} (pid ${pid})`);
    stopped++;
  }
  rmSync(pidFile, { force: true });
}

for (const port of [envPort(), 5173, 4173]) {
  for (const pid of listeners(port)) {
    const cmd = commandLine(pid);
    if (OURS.test(cmd)) {
      killTree(pid);
      console.log(`stopped leftover on port ${port} (pid ${pid})`);
      stopped++;
    } else if (cmd) {
      console.log(`port ${port} is used by another program (pid ${pid}) — left alone: ${cmd.slice(0, 100)}`);
    }
  }
}
console.log(stopped ? 'Done.' : 'Nothing of ours was running.');
