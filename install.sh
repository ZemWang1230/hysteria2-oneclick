#!/usr/bin/env bash
set -Eeuo pipefail

# Usage: sudo bash install.sh PUBLIC_IPV4 [UDP_PORT]
# Never source this file. Client credentials stay on the deployed server.
fail() { echo "错误：$*" >&2; exit 1; }
validate() {
  python3 - "$1" "$2" <<'PY'
import ipaddress, re, sys
try:
    ip = ipaddress.IPv4Address(sys.argv[1])
    assert ip.is_global
    assert re.fullmatch(r'[0-9]+', sys.argv[2])
    assert 1 <= int(sys.argv[2]) <= 65535
except (ValueError, AssertionError):
    sys.exit('请输入有效公网 IPv4 和 1–65535 的 UDP 端口。')
PY
}

render_clients() {
  local address=$1 port=$2 password=$3 fingerprint=$4 destination=$5
  cat > "$destination/clash-verge.yaml" <<YAML
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
ipv6: false
proxies:
  - name: HY2
    type: hysteria2
    server: $address
    port: $port
    password: "$password"
    sni: hy2.internal
    skip-cert-verify: false
    fingerprint: "$fingerprint"
    alpn: [h3]
proxy-groups:
  - name: PROXY
    type: select
    proxies: [HY2]
rules:
  - IP-CIDR,$address/32,DIRECT,no-resolve
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
YAML
  cat > "$destination/shadowrocket.conf" <<CONF
[General]
bypass-system = true
skip-proxy = localhost, *.local, $address, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
ipv6 = false
dns-server = system

[Proxy]
HY2 = hysteria2, $address, $port, auth=$password, peer=hy2.internal, alpn=h3, allowInsecure=1, udp=1

[Proxy Group]
HY2-PROXY = select, HY2

[Rule]
IP-CIDR,$address/32,DIRECT,no-resolve
IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
FINAL,HY2-PROXY
CONF
  printf 'hysteria2://%s@%s:%s/?sni=hy2.internal&insecure=1#HY2\n' \
    "$password" "$address" "$port" > "$destination/shadowrocket-uri.txt"
}

show_clients() {
  local file
  for file in clash-verge.yaml shadowrocket.conf shadowrocket-uri.txt; do
    printf '\n========== %s 开始 ==========\n' "$file"
    cat "/root/hy2-client/$file"
    printf '========== %s 结束 ==========\n' "$file"
  done
}

# Offline checks exercise validation and rendering without root/network/install.
if [[ ${1:-} == --self-test ]]; then
  validate 8.8.8.8 443
  for bad in 127.0.0.1 10.0.0.1 999.1.1.1 '8.8.8.8;id'; do
    if validate "$bad" 443 2>/dev/null; then fail "IP validation: $bad"; fi
  done
  for bad in 0 65536 abc '443;id'; do
    if validate 8.8.8.8 "$bad" 2>/dev/null; then fail "port validation: $bad"; fi
  done
  test_dir=$(mktemp -d)
  trap 'rm -rf "$test_dir"' EXIT
  umask 077
  render_clients 8.8.8.8 443 test-password abcdef "$test_dir"
  python3 - "$test_dir" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
c = (p/'clash-verge.yaml').read_text()
s = (p/'shadowrocket.conf').read_text()
u = (p/'shadowrocket-uri.txt').read_text()
assert 'server: 8.8.8.8' in c and 'fingerprint: "abcdef"' in c
assert 'auth=test-password' in s and 'FINAL,HY2-PROXY' in s
assert u.startswith('hysteria2://test-password@8.8.8.8:443/')
assert all(f.stat().st_mode & 0o077 == 0 for f in p.iterdir())
PY
  echo 'PASS: validation, client rendering, credential file permissions'
  exit
fi

[[ $EUID == 0 ]] || fail '请用 sudo bash 执行。'
if [[ ${1:-} == --show ]]; then show_clients; exit; fi
[[ $# -ge 1 && $# -le 2 ]] || fail '用法：sudo bash install.sh 公网IPv4 [UDP端口]'
# Check the platform, not an Ubuntu release number.
[[ -r /etc/os-release ]] || fail '无法识别系统：缺少 /etc/os-release。'
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || fail '本脚本需要 Ubuntu 服务器。'
command -v apt-get >/dev/null || fail '缺少 apt-get，无法安装依赖。'
command -v systemctl >/dev/null && systemctl show-environment >/dev/null 2>&1 ||
  fail '需要正在运行的 systemd；不支持未启用 systemd 的容器或 WSL。'
case $(uname -m) in x86_64) ARCH=amd64;; aarch64) ARCH=arm64;; *) fail '仅支持 64 位 amd64/arm64。';; esac
[[ ! -e /etc/hysteria/config.yaml && ! -e /root/hy2-client ]] ||
  fail '已有配置或客户端文件，停止以免覆盖。查看现有输出：sudo bash install.sh --show'
export DEBIAN_FRONTEND=noninteractive
apt-get update || fail '更新 Ubuntu 软件源失败，请检查网络和 apt 源（旧版本可能已停止维护）。'
apt-get install -y --no-install-recommends python3 iproute2 curl ca-certificates openssl tar passwd coreutils ||
  fail '安装依赖失败，请检查 apt 输出。'
python3 -c 'import sys; sys.exit(sys.version_info < (3, 6))' || fail '需要 Python 3.6 或更新版本。'
validate "$1" "${2:-443}"
SERVER_IP=$1
PORT=$((10#${2:-443}))

[[ -z $(ss -H -lun "sport = :$PORT") ]] || fail "UDP $PORT 已被占用。"

trap 'echo "部署中断，行号：$LINENO。日志：sudo journalctl -u hysteria-server -n 60 --no-pager" >&2' ERR
openssl req -help 2>&1 | grep -q -- '-addext' || fail '系统 OpenSSL 不支持 -addext，请升级 OpenSSL 或 Ubuntu。'
umask 022
installer=$(mktemp)
trap 'rm -f "$installer"' EXIT
curl -fSL --retry 3 https://get.hy2.sh/ -o "$installer"
HYSTERIA_USER=hysteria bash "$installer"
group=$(id -gn hysteria)
umask 077
install -d -m 0750 -o root -g "$group" /etc/hysteria
install -d -m 0700 /root/hy2-client
password=$(openssl rand -hex 24)
openssl req -x509 -nodes -newkey ec \
  -pkeyopt ec_paramgen_curve:prime256v1 -sha256 -days 3650 \
  -keyout /etc/hysteria/server.key -out /etc/hysteria/server.crt \
  -subj '/CN=hy2.internal' \
  -addext "subjectAltName=DNS:hy2.internal,IP:$SERVER_IP"
cat > /etc/hysteria/config.yaml <<YAML
listen: 0.0.0.0:$PORT
tls:
  cert: /etc/hysteria/server.crt
  key: /etc/hysteria/server.key
auth:
  type: password
  password: "$password"
YAML
chown root:"$group" /etc/hysteria/{config.yaml,server.crt,server.key}
chmod 0640 /etc/hysteria/{config.yaml,server.crt,server.key}
fingerprint=$(openssl x509 -in /etc/hysteria/server.crt -noout -fingerprint -sha256 |
  cut -d= -f2 | tr -d ':' | tr '[:upper:]' '[:lower:]')
[[ $fingerprint =~ ^[0-9a-f]{64}$ ]]
render_clients "$SERVER_IP" "$PORT" "$password" "$fingerprint" /root/hy2-client
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then
  ufw allow "$PORT/udp"
fi
systemctl enable hysteria-server.service
systemctl restart hysteria-server.service
sleep 2
systemctl is-active --quiet hysteria-server.service
[[ -n $(ss -H -lun "sport = :$PORT") ]]
show_clients
echo "服务已启动并监听 UDP $PORT；请在云安全组放行此端口。"
echo 'Shadowrocket 兼容配置跳过证书验证，存在中间人风险；Mac 配置固定证书指纹。'
echo '配置含密码，不要公开分享。本机检查通过不代表公网/客户端连通性已验证。'
