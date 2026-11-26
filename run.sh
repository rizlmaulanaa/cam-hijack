#!/usr/bin/env bash
# cam-hijack-lab · portable (Linux/macOS) · authorized lab demonstration only
# target = perangkat lab yang kamu arahkan sendiri
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-3040}"
export PORT
export CAMLAB_ORIGIN_PORT="${CAMLAB_ORIGIN_PORT:-$((PORT + 1))}"

get_ip() {
  local ip
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  [ -n "$ip" ] || ip=$(ip -4 -o addr show scope global 2>/dev/null | head -1 | awk '{print $4}' | cut -d/ -f1)
  [ -n "$ip" ] || ip=$(ipconfig getifaddr en0 2>/dev/null)
  [ -n "$ip" ] || ip="localhost"
  echo "$ip"
}

CERT=.cert
if [ ! -f "$CERT/cert.pem" ]; then
  mkdir -p "$CERT"
  IP=$(get_ip)
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$CERT/key.pem" -out "$CERT/cert.pem" \
    -subj "/CN=$IP" -addext "subjectAltName=IP:$IP,DNS:$IP,DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
fi
if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | awk '{print $4}' | grep -qE ":$PORT\$"; then
  echo "port $PORT sudah terpakai - server kemungkinan sudah jalan."
  echo "restart:  pkill -f 'cam-hijack-lab/server.py' && ./run.sh"
  exit 0
fi
IP=$(get_ip)
echo "port $PORT (+ origin loopback $CAMLAB_ORIGIN_PORT untuk tunnel) · CLI: ./camlab new"
exec python3 server.py
