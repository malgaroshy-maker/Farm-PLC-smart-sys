# Farm server (Milestone G7)

How to run the farm app on the farm's own PC around the clock, back it up, and reach it safely from anywhere.

The farm server is a normal PC or mini-PC that stays on. The hardware report suggests one, with a small UPS. It runs three parts: the API, the controller gateway and the web app. Phones and laptops on the farm Wi-Fi open it in a browser. Away from the farm, they reach it through Tailscale.

## 1. First start, by hand
Run the demo once. It installs Python packages, JavaScript packages and a `.env` with new secrets:

```
run.bat demo          (Windows)
./run.sh demo         (Linux)
```

Sign in, check the map, then close the window (Ctrl+C).

## 2. Start with the PC, restart on failure
`node scripts/start.mjs server` is the farm-server mode. It works like `demo` (a production build that phones can open), but:
- it opens no browser;
- if any part stops, it restarts that part after 5 s, 10 s, 20 s, 40 s, then once a minute;
- it writes `logs/farm-server.log`, rotated at 5 MB with 3 old copies kept;
- it applies a restore chosen in Settings → Backups before it opens the database (see section 3).

The installers start it as a service when the PC boots, with nobody signed in.

**Windows.** Open PowerShell with *Run as administrator* in the project folder:
```
powershell -ExecutionPolicy Bypass -File infra\farm-server\install-windows.ps1 -NoSleep
```
- This creates a scheduled task, `AlgaroshyFarmServer`. It starts 30 s after boot, runs as your Windows user and stores no password.
- If the task itself stops, Windows starts it again within a minute.
- `-NoSleep` turns off sleep and hibernate while on mains power.
- To remove it, run the same command with `-Uninstall`.

**Linux** (Ubuntu or Debian, with systemd):
```
sudo sh infra/farm-server/install-linux.sh
```
- This creates a service, `algaroshy-farm`, with `Restart=always`.
- Logs: `journalctl -u algaroshy-farm -f`.
- To remove it: `sudo sh infra/farm-server/install-linux.sh --uninstall`.

Also set the PC's BIOS to **power on after a power cut** (often called "AC power recovery" or "Restore on AC power loss": On). The server then comes back by itself, even if the UPS runs flat.

## 3. Backups
The API copies the database:
- every day at `BACKUP_TIME` (default 03:00, farm time);
- whenever an admin presses **Back up now** in Settings → Backups.

The copy is taken with SQLite's online backup, so it is safe while the farm is running. The newest `BACKUP_KEEP` copies (default 14) are kept in `apps/api/backups/`. A backup selected for restore is kept until the request is applied or cancelled.

Two optional extra copies, set in `.env`:

| Copy | Setting | Notes |
|---|---|---|
| USB stick or external disk | `BACKUP_USB_DIR=E:/FarmBackups` (Linux: `/media/usb/farm`) | If the drive isn't plugged in, the tab shows "Drive not plugged in". The copy on the server is still made. |
| Google Drive | `BACKUP_RCLONE_REMOTE=gdrive:FarmBackups` | Needs [rclone](https://rclone.org). Run `rclone config` once and sign in to Google yourself; the app never sees your Google password. |

Restart the server after changing `.env`.

**Restore.** In Settings → Backups, press **Restore** next to a backup and confirm. Nothing changes until the next server restart. Then, before the database opens, the launcher:

1. verifies the selected file is a readable Farm-PLC database;
2. saves the current database, including committed changes still in SQLite's write-ahead log, as `backups/pre-restore-<date>.db`;
3. restores through SQLite and clears the request after the restore succeeds.

If the current database is unreadable, the launcher preserves the damaged file and its SQLite sidecars before replacing it with the verified backup.

You can cancel a pending restore before the restart. To restart:
- Windows: restart the PC, or run `stop.bat` then `Start-ScheduledTask AlgaroshyFarmServer`.
- Linux: `sudo systemctl restart algaroshy-farm`.

A restore takes every record back to the backup's time: alarms, history, settings and users. **Old passwords and disabled or enabled accounts come back too**, and everyone is signed out. Restore only to recover from a broken or lost database.

**Keep in mind.** Backup files are not encrypted: anyone holding the USB drive or the Drive folder can read the farm's records. A failed or old backup (over 36 hours) shows as a warning in system health.

**Locked out?** On the farm PC, in `apps/api`: `.venv\Scripts\python.exe -m app.reset_password <username>`.

## 4. Remote access with Tailscale (HTTPS)
Don't open router ports to the internet. [Tailscale](https://tailscale.com) makes a private network between your own devices. The free plan covers a farm.

1. Install Tailscale on the farm server and on each phone or laptop. Sign in with the same account on each one; you sign in yourself.
2. In the Tailscale admin console → **DNS**, turn on **MagicDNS** and **HTTPS Certificates**.
3. On the farm server, publish the web app inside your tailnet only:
   ```
   tailscale serve --bg 4173
   ```
4. On a phone, open `https://<server-name>.<your-tailnet>.ts.net`. Tailscale shows the exact address in `tailscale serve status`.

**Why HTTPS matters.** Phone notifications (web push) and "Add to Home screen" work only over HTTPS. The `ts.net` address has a real certificate, so both work from anywhere. The app already accepts `*.ts.net` names. Add any other name to `WEB_ALLOWED_HOSTS` in `.env`.

`tailscale serve` (private to your devices) is not `tailscale funnel` (public on the internet). Don't use funnel for the farm.

## 5. Checklist for the farm PC
- [ ] The first `run.bat demo` worked and you can sign in.
- [ ] Service installed and started with the PC (test it: reboot, wait 2 minutes, open the app).
- [ ] BIOS "power on after AC loss" set to On; UPS connected.
- [ ] Settings → Backups shows a backup; USB and/or Drive copies show "Done".
- [ ] A phone reaches the `ts.net` address over 4G (Wi-Fi off), and a test notification arrives.
