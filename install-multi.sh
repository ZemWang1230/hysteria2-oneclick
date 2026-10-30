#!/usr/bin/env bash
set -Eeuo pipefail
fail() { echo "错误：$*" >&2; exit 1; }
BASE=/etc/sing-multi
CLIENTS=/root/multi-client
SING_BOX_VERSION=1.14.4

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
keys = dict(line.split(':', 1) for line in subprocess.check_output([binary, 'generate', 'reality-keypair'], universal_newlines=True).splitlines() if ':' in line)
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
log-level: warning
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
augment() {
  python3 - "$1" "$2" <<'PYAUG'
import base64, json, pathlib, secrets, subprocess, sys, uuid
from urllib.parse import urlencode
p = pathlib.Path(sys.argv[1]).resolve()
ip = sys.argv[2]
conf = json.loads((p / 'server.json').read_text())
uid = str(uuid.uuid4())
sspw, hypw, tupw = (secrets.token_hex(24) for _ in range(3))
tls = {'enabled': True, 'certificate_path': str(p/'server.crt'), 'key_path': str(p/'server.key')}
conf['inbounds'].extend([
 {'type':'shadowsocks','tag':'ss-in','listen':'0.0.0.0','listen_port':8388,'network':'tcp','method':'chacha20-ietf-poly1305','password':sspw},
 {'type':'hysteria2','tag':'hy2-in','listen':'0.0.0.0','listen_port':8443,'users':[{'password':hypw}],'tls':dict(tls)},
 {'type':'tuic','tag':'tuic-in','listen':'0.0.0.0','listen_port':8444,'users':[{'uuid':uid,'password':tupw}],'congestion_control':'cubic','tls':dict(tls, alpn=['h3'])},
])
(p/'server.json').write_text(json.dumps(conf, indent=2)+'\n')
fingerprint = subprocess.check_output(['openssl','x509','-in',str(p/'server.crt'),'-noout','-fingerprint','-sha256'],universal_newlines=True).strip().split('=',1)[1].replace(':','').lower()
extra = f'''  - name: SS
    type: ss
    server: {ip}
    port: 8388
    cipher: chacha20-ietf-poly1305
    password: "{sspw}"
    udp: false
  - name: HY2
    type: hysteria2
    server: {ip}
    port: 8443
    password: "{hypw}"
    sni: {ip}
    fingerprint: "{fingerprint}"
    skip-cert-verify: false
  - name: TUIC
    type: tuic
    server: {ip}
    port: 8444
    uuid: {uid}
    password: "{tupw}"
    congestion-controller: cubic
    alpn: [h3]
    sni: {ip}
    fingerprint: "{fingerprint}"
    skip-cert-verify: false
'''
clash = (p/'clash-verge.yaml').read_text().replace('proxy-groups:\n', extra+'proxy-groups:\n').replace('proxies: [REALITY]', 'proxies: [REALITY, SS, HY2, TUIC]')
(p/'clash-verge.yaml').write_text(clash)
ss = base64.urlsafe_b64encode(('chacha20-ietf-poly1305:'+sspw).encode()).decode().rstrip('=')
uri = (p/'vless-uri.txt').read_text().strip()
lines = [uri, 'ss://'+ss+'@'+ip+':8388#SS',
         'hysteria2://'+hypw+'@'+ip+':8443/?'+urlencode({'sni':ip,'insecure':'0'})+'#HY2',
         'tuic://'+uid+':'+tupw+'@'+ip+':8444?'+urlencode({'congestion_control':'cubic','udp_relay_mode':'native','alpn':'h3','sni':ip,'allow_insecure':'0'})+'#TUIC']
(p/'shadowrocket-nodes.txt').write_text('\n'.join(lines)+'\n')
for f in p.iterdir(): f.chmod(0o600)
PYAUG
}

show() {
  local file
  for file in clash-verge.yaml shadowrocket.conf vless-uri.txt shadowrocket-nodes.txt root-ca.crt; do
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
[[ $# -ge 1 && $# -le 3 ]] || fail '用法：sudo bash install-multi.sh 公网IPv4 [TCP端口=443] [握手目标=www.microsoft.com]'
# Check the platform, not an Ubuntu release number.
[[ -r /etc/os-release ]] || fail '无法识别系统：缺少 /etc/os-release。'
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || fail '本脚本需要 Ubuntu 服务器。'
command -v apt-get >/dev/null || fail '缺少 apt-get，无法安装依赖。'
command -v systemctl >/dev/null && systemctl show-environment >/dev/null 2>&1 ||
  fail '需要正在运行的 systemd；不支持未启用 systemd 的容器或 WSL。'
case $(uname -m) in x86_64) ARCH=amd64;; aarch64) ARCH=arm64;; *) fail '仅支持 64 位 amd64/arm64。';; esac
[[ ! -e $BASE && ! -e $CLIENTS && ! -e /etc/systemd/system/sing-multi.service ]] || fail '已有多协议部署，停止以免覆盖。使用 --show 查看原配置。'
export DEBIAN_FRONTEND=noninteractive
apt-get update || fail '更新 Ubuntu 软件源失败，请检查网络和 apt 源（旧版本可能已停止维护）。'
apt-get install -y --no-install-recommends python3 iproute2 curl ca-certificates openssl tar passwd coreutils ||
  fail '安装依赖失败，请检查 apt 输出。'
python3 -c 'import sys; sys.exit(sys.version_info < (3, 6))' || fail '需要 Python 3.6 或更新版本。'
validate "$1" "${2:-443}" "${3:-www.microsoft.com}"
ADDRESS=$1
PORT=$((10#${2:-443}))
TARGET=${3:-www.microsoft.com}
[[ -z $(ss -H -ltn "sport = :$PORT") ]] || fail "TCP $PORT 已被占用。可在 IP 后指定 24443。"
[[ -z $(ss -H -ltn 'sport = :18080') ]] || fail '本地测试端口 TCP 18080 已被占用，请释放后再安装。'
[[ $PORT != 18080 ]] || fail 'REALITY 端口不能与本地测试端口 TCP 18080 相同。'
[[ $PORT != 8388 ]] || fail 'REALITY 端口不能与 Shadowsocks 的 TCP 8388 相同。'
[[ -z $(ss -H -ltn 'sport = :8388') ]] || fail 'TCP 8388 已被占用。'
for p in 8443 8444; do [[ -z $(ss -H -lun "sport = :$p") ]] || fail "UDP $p 已被占用。"; done
trap 'echo "部署中断（行 $LINENO）；sudo journalctl -u sing-multi -n 60 --no-pager" >&2' ERR
# Official release only; pinned to the version validated by this repository.
umask 077
work=$(mktemp -d)
client_pid=''
cleanup() { if [[ -n $client_pid ]]; then kill "$client_pid" 2>/dev/null || true; wait "$client_pid" 2>/dev/null || true; fi; rm -rf "$work"; }
trap cleanup EXIT
curl -fSL --retry 3 --connect-timeout 15 --max-time 180 \
 "https://github.com/SagerNet/sing-box/releases/download/v$SING_BOX_VERSION/sing-box-$SING_BOX_VERSION-linux-$ARCH.tar.gz" -o "$work/sing-box.tar.gz"
tar --no-same-owner -xzf "$work/sing-box.tar.gz" -C "$work"
BINARY="$work/sing-box-$SING_BOX_VERSION-linux-$ARCH/sing-box"
"$BINARY" version || fail 'sing-box 二进制无法运行，请检查系统运行库与 CPU/内核兼容性。'
openssl s_client -help 2>&1 | grep -q -- '-tls1_3' || fail '系统 OpenSSL 不支持 TLS 1.3，请升级 OpenSSL 或 Ubuntu。'
# Verify the selected target is reachable with TLS 1.3 before writing deployment files.
timeout 20 openssl s_client -connect "$TARGET:443" -servername "$TARGET" \
 -tls1_3 -verify_return_error -verify_hostname "$TARGET" -brief </dev/null >"$work/target.log" 2>&1 || {
  cat "$work/target.log" >&2
  fail '握手目标不可达或 TLS 校验失败。可更换第三个参数中的目标域名。'
}
render "$BINARY" "$ADDRESS" "$PORT" "$TARGET" "$work/output"
# Dedicated CA is generated locally. Only its public certificate is exported.
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -sha256 -subj '/CN=sing-multi local CA' \
 -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' \
 -keyout "$work/ca.key" -out "$work/output/root-ca.crt" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -subj "/CN=$ADDRESS" -keyout "$work/output/server.key" -out "$work/server.csr" >/dev/null 2>&1
printf 'subjectAltName=IP:%s\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\n' "$ADDRESS" > "$work/extensions"
openssl x509 -req -in "$work/server.csr" -CA "$work/output/root-ca.crt" -CAkey "$work/ca.key" -CAcreateserial \
 -out "$work/output/server.crt" -days 825 -sha256 -extfile "$work/extensions" >/dev/null 2>&1
augment "$work/output" "$ADDRESS"
"$BINARY" check -c "$work/output/server.json"
"$BINARY" check -c "$work/output/check-client.json"
if ! id sing-multi >/dev/null 2>&1; then
 useradd --system --user-group --no-create-home --shell /usr/sbin/nologin sing-multi
fi
GROUP=$(id -gn sing-multi)
install -d -m 0755 /usr/local/lib/sing-multi
install -m 0755 "$BINARY" /usr/local/lib/sing-multi/sing-box
install -d -m 0750 -o root -g "$GROUP" "$BASE"
install -m 0640 -o root -g "$GROUP" "$work/output/server.crt" "$work/output/server.key" "$BASE/"
python3 - "$work/output/server.json" "$BASE" <<'PYPATH'
import json,sys
p, base = sys.argv[1:]
c = json.load(open(p))
for inbound in c['inbounds']:
    if inbound['type'] in ('hysteria2', 'tuic'):
        inbound['tls']['certificate_path'] = base + '/server.crt'
        inbound['tls']['key_path'] = base + '/server.key'
open(p, 'w').write(json.dumps(c, indent=2)+'\n')
PYPATH
"$BINARY" check -c "$work/output/server.json"
install -m 0640 -o root -g "$GROUP" "$work/output/server.json" "$BASE/config.json"
install -d -m 0700 "$CLIENTS"
for file in clash-verge.yaml shadowrocket.conf vless-uri.txt shadowrocket-nodes.txt root-ca.crt check-client.json; do
 install -m 0600 "$work/output/$file" "$CLIENTS/$file"
done
cat > /etc/systemd/system/sing-multi.service <<UNIT
[Unit]
Description=sing-box multi-protocol server
Wants=network-online.target
After=network-online.target
[Service]
User=sing-multi
Group=$GROUP
ExecStart=/usr/local/lib/sing-multi/sing-box run -c /etc/sing-multi/config.json
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
chmod 0644 /etc/systemd/system/sing-multi.service
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then ufw allow "$PORT/tcp"; ufw allow 8388/tcp; ufw allow 8443/udp; ufw allow 8444/udp; fi
systemctl daemon-reload
systemctl enable --now sing-multi.service
sleep 2
systemctl is-active --quiet sing-multi.service
[[ -n $(ss -H -ltn "sport = :$PORT") ]]
/usr/local/lib/sing-multi/sing-box run -c "$CLIENTS/check-client.json" >"$work/client.log" 2>&1 &
client_pid=$!
sleep 1
if curl --fail --silent --show-error --noproxy '' --proxy socks5h://127.0.0.1:18080 \
 --connect-timeout 10 --max-time 30 https://example.com/ -o /dev/null; then
 echo 'PASS：本机 REALITY 握手、认证及 HTTPS 代理转发成功（其他协议需另行测试）。'
else
 cat "$work/client.log" >&2
 echo '警告：服务已启动，但本机端到端测试失败，请检查 sing-multi 日志。' >&2
fi
show
echo "请在厂商防火墙放行 TCP $PORT、TCP 8388、UDP 8443 和 UDP 8444，并在 Mac/iPhone 导入新配置。"
echo '本机测试不能证明你的公网线路可达。旧服务未停止；如监听端口冲突，请换端口或在新服务器安装。'
echo '小火箭先导入 shadowrocket-nodes.txt 中的节点和分流配置；HY2/TUIC 还需信任导出的 CA。'
echo 'CA 私钥仅用于签发，安装结束清理临时文件；仅将 root-ca.crt 通过可信渠道导入 iPhone 并启用完全信任。' 
