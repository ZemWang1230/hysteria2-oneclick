#!/usr/bin/env bash
set -Eeuo pipefail
fail() { echo "错误：$*" >&2; exit 1; }
BASE=/etc/sing-reality
CLIENTS=/root/reality-client
VERSION=1.14.4

validate() {
  python3 - "$@" <<'PY'
import ipaddress, re, sys
try:
    assert len(sys.argv) == 4
    assert ipaddress.IPv4Address(sys.argv[1]).is_global
    assert re.fullmatch(r'[0-9]{1,5}', sys.argv[2])
    assert 1 <= int(sys.argv[2]) <= 65535
    host = sys.argv[3]
    assert len(host) <= 253 and '.' in host
    assert all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part) for part in host.split('.'))
except (AssertionError, ValueError):
    sys.exit('需要公网 IPv4、有效 TCP 端口和握手目标域名（不能包含 URL 路径）。')
PY
}

render() {
  python3 - "$@" <<'PY'
import json, pathlib, secrets, subprocess, sys, uuid
from urllib.parse import urlencode
binary, address, port, host, dest = sys.argv[1:]
port = int(port)
p = pathlib.Path(dest)
p.mkdir(mode=0o700, parents=True, exist_ok=True)
keys = dict(line.split(':', 1) for line in subprocess.check_output([binary, 'generate', 'reality-keypair'], text=True).splitlines() if ':' in line)
private, public = keys['PrivateKey'].strip(), keys['PublicKey'].strip()
uid, sid = str(uuid.uuid4()), secrets.token_hex(8)
def write(name, text):
    f = p / name
    f.write_text(text)
    f.chmod(0o600)
server = {
 'log': {'level': 'warn', 'timestamp': True},
 'inbounds': [{'type':'vless','tag':'reality-in','listen':'0.0.0.0','listen_port':port,
  'users':[{'name':'owner','uuid':uid,'flow':'xtls-rprx-vision'}],
  'tls':{'enabled':True,'server_name':host,'reality':{'enabled':True,
   'handshake':{'server':host,'server_port':443},'private_key':private,'short_id':[sid]}}}],
 'outbounds':[{'type':'direct','tag':'direct'}],
 'route':{'rules':[{'ip_is_private':True,'action':'reject'}],'final':'direct'}
}
write('server.json', json.dumps(server, indent=2)+'\n')
write('clash-verge.yaml', f'''mixed-port: 7890
allow-lan: false
mode: rule
log-level: warn
ipv6: false
proxies:
  - name: REALITY
    type: vless
    server: {address}
    port: {port}
    uuid: {uid}
    network: tcp
    tls: true
    udp: true
    flow: xtls-rprx-vision
    servername: {host}
    client-fingerprint: chrome
    skip-cert-verify: false
    reality-opts:
      public-key: {public}
      short-id: "{sid}"
proxy-groups:
  - name: PROXY
    type: select
    proxies: [REALITY]
rules:
  - IP-CIDR,{address}/32,DIRECT,no-resolve
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
''')
# Shadowrocket keeps the server node and routing profile separate.
write('shadowrocket.conf', f'''# First import the VLESS URI, select REALITY on Home, then enable this profile.
[General]
bypass-system = true
skip-proxy = localhost, *.local, {address}, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
ipv6 = false
dns-server = system

[Rule]
IP-CIDR,{address}/32,DIRECT,no-resolve
IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
FINAL,PROXY
''')
query = urlencode({'encryption':'none','security':'reality','type':'tcp',
 'sni':host,'fp':'chrome','pbk':public,'sid':sid,'flow':'xtls-rprx-vision'})
write('vless-uri.txt', f'vless://{uid}@{address}:{port}?{query}#REALITY\n')
# Kept private and used for a real loopback handshake + proxy request during installation.
client = {'log':{'level':'warn'},
 'inbounds':[{'type':'mixed','listen':'127.0.0.1','listen_port':18080}],
 'outbounds':[{'type':'vless','tag':'proxy','server':'127.0.0.1','server_port':port,
 'uuid':uid,'flow':'xtls-rprx-vision',
 'tls':{'enabled':True,'server_name':host,'utls':{'enabled':True,'fingerprint':'chrome'},
 'reality':{'enabled':True,'public_key':public,'short_id':sid}}}]}
write('check-client.json', json.dumps(client, indent=2)+'\n')
PY
}
show() {
  local file
  for file in clash-verge.yaml shadowrocket.conf vless-uri.txt; do
    printf '\n========== %s 开始 ==========\n' "$file"
    cat "$CLIENTS/$file"
    printf '========== %s 结束 ==========\n' "$file"
  done
}

# Safe local rendering mode used by tests. No service, apt or firewall changes.
if [[ ${1:-} == --test-render ]]; then
  [[ $# == 4 ]] || fail '--test-render BINARY OUTPUT_DIR HANDSHAKE_HOST'
  umask 077
  validate 8.8.8.8 18443 "$4"
  render "$2" 8.8.8.8 18443 "$4" "$3"
  exit
fi
[[ $EUID == 0 ]] || fail '请使用 sudo bash。'
if [[ ${1:-} == --show ]]; then show; exit; fi
[[ $# -ge 1 && $# -le 3 ]] || fail '用法：sudo bash install-reality.sh 公网IPv4 [TCP端口=443] [握手目标=www.microsoft.com]'
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || fail '仅支持 Ubuntu 24.04。'
command -v python3 >/dev/null || fail '请先安装 python3。'
validate "$1" "${2:-443}" "${3:-www.microsoft.com}"
ADDRESS=$1
PORT=$((10#${2:-443}))
TARGET=${3:-www.microsoft.com}
[[ ! -e $BASE && ! -e $CLIENTS && ! -e /etc/systemd/system/sing-reality.service ]] || fail '已有 REALITY 部署，停止以免覆盖。使用 --show 查看原配置。'
command -v ss >/dev/null || fail '请先安装 iproute2。'
[[ -z $(ss -H -ltn "sport = :$PORT") ]] || fail "TCP $PORT 已被占用。可在 IP 后指定 24443。"
[[ -z $(ss -H -ltn 'sport = :18080') ]] || fail '本地测试端口 TCP 18080 已被占用，请释放后再安装。'
trap 'echo "部署中断（行 $LINENO）；sudo journalctl -u sing-reality -n 60 --no-pager" >&2' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends curl ca-certificates openssl tar
# Official release only; pinned to the version validated by this repository.
case $(uname -m) in x86_64) ARCH=amd64;; aarch64) ARCH=arm64;; *) fail '仅支持 amd64/arm64。';; esac
umask 077
work=$(mktemp -d)
client_pid=''
cleanup() { if [[ -n $client_pid ]]; then kill "$client_pid" 2>/dev/null || true; wait "$client_pid" 2>/dev/null || true; fi; rm -rf "$work"; }
trap cleanup EXIT
curl -fSL --retry 3 --connect-timeout 15 --max-time 180 \
 "https://github.com/SagerNet/sing-box/releases/download/v$VERSION/sing-box-$VERSION-linux-$ARCH.tar.gz" -o "$work/sing-box.tar.gz"
tar --no-same-owner -xzf "$work/sing-box.tar.gz" -C "$work"
BINARY="$work/sing-box-$VERSION-linux-$ARCH/sing-box"
"$BINARY" version
# Verify the selected target is reachable with TLS 1.3 before writing deployment files.
timeout 20 openssl s_client -connect "$TARGET:443" -servername "$TARGET" \
 -tls1_3 -verify_return_error -verify_hostname "$TARGET" -brief </dev/null >"$work/target.log" 2>&1 || {
  cat "$work/target.log" >&2
  fail '握手目标不可达或 TLS 校验失败。可更换第三个参数中的目标域名。'
}
render "$BINARY" "$ADDRESS" "$PORT" "$TARGET" "$work/output"
"$BINARY" check -c "$work/output/server.json"
"$BINARY" check -c "$work/output/check-client.json"
if ! id sing-reality >/dev/null 2>&1; then
 useradd --system --user-group --no-create-home --shell /usr/sbin/nologin sing-reality
fi
GROUP=$(id -gn sing-reality)
install -d -m 0755 /usr/local/lib/sing-reality
install -m 0755 "$BINARY" /usr/local/lib/sing-reality/sing-box
install -d -m 0750 -o root -g "$GROUP" "$BASE"
install -m 0640 -o root -g "$GROUP" "$work/output/server.json" "$BASE/config.json"
install -d -m 0700 "$CLIENTS"
for file in clash-verge.yaml shadowrocket.conf vless-uri.txt check-client.json; do
 install -m 0600 "$work/output/$file" "$CLIENTS/$file"
done
cat > /etc/systemd/system/sing-reality.service <<UNIT
[Unit]
Description=sing-box VLESS REALITY TCP server
Wants=network-online.target
After=network-online.target
[Service]
User=sing-reality
Group=$GROUP
ExecStart=/usr/local/lib/sing-reality/sing-box run -c /etc/sing-reality/config.json
Restart=on-failure
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/sing-reality.service
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then ufw allow "$PORT/tcp"; fi
systemctl daemon-reload
systemctl enable --now sing-reality.service
sleep 2
systemctl is-active --quiet sing-reality.service
[[ -n $(ss -H -ltn "sport = :$PORT") ]]
/usr/local/lib/sing-reality/sing-box run -c "$CLIENTS/check-client.json" >"$work/client.log" 2>&1 &
client_pid=$!
sleep 1
if curl --fail --silent --show-error --noproxy '' --proxy socks5h://127.0.0.1:18080 \
 --connect-timeout 10 --max-time 30 https://example.com/ -o /dev/null; then
 echo 'PASS：本机 REALITY 握手、认证及 HTTPS 代理转发成功。'
else
 cat "$work/client.log" >&2
 echo '警告：服务已启动，但本机端到端测试失败，请检查 sing-reality 日志。' >&2
fi
show
echo "请在厂商防火墙放行 TCP $PORT，并在 Mac/iPhone 导入新配置。"
echo '本机测试不能证明你的公网线路可达。HY2 未停止；确认新节点可用后再停旧服务。'
echo '小火箭先导入 vless 链接，再导入 shadowrocket.conf，并选用 REALITY 节点。'
