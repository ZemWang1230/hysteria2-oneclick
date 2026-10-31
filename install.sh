#!/usr/bin/env bash
set -Eeuo pipefail
fail() { echo "错误：$*" >&2; exit 1; }
ROOT=/etc/mihomo-five
BIN=/usr/local/lib/mihomo-five
CLIENTS=/root/mihomo-five-client
VERSION=v1.19.33
show() {
 for f in ports.json clash-verge.yaml shadowrocket-nodes.txt shadowrocket.conf; do
  printf '\n========== %s 开始 ==========\n' "$f"; cat "$CLIENTS/$f"; printf '========== %s 结束 ==========\n' "$f"
 done
}
[[ $EUID == 0 ]] || fail '请使用 sudo bash。'
if [[ ${1:-} == --show ]]; then show; exit; fi
[[ $# == 1 ]] || fail '用法：sudo bash install.sh 公网IPv4'
[[ -r /etc/os-release ]] || fail '无法识别系统。'
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || fail '需要 Ubuntu。'
command -v systemctl >/dev/null && systemctl show-environment >/dev/null 2>&1 || fail '需要运行中的 systemd。'
[[ ! -e $ROOT && ! -e $CLIENTS && ! -e /etc/systemd/system/mihomo-five.service ]] || fail '已有安装文件；为保护凭据已停止。请查看状态，不要直接删除现有文件。'
case $(uname -m) in
 x86_64) ARCH=amd64-compatible; DIGEST=386508bfb1c72c43b6a0eda73708ecdce82546581b0ebcb16366c53757c622b6;;
 aarch64) ARCH=arm64; DIGEST=ba408b317080ee265c46cb923a50018c1b82cbd708551cdd46a1e3e307396187;;
 *) fail '仅支持 64 位 amd64/arm64。';;
esac
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv curl ca-certificates iproute2 openssl gzip
python3 -c 'import sys; sys.exit(sys.version_info < (3,10))' || fail '公网 IP 证书工具要求 Python 3.10 或更高。'
python3 - "$1" <<'PY'
import ipaddress,sys
try:
 ip=ipaddress.IPv4Address(sys.argv[1])
 if not ip.is_global: raise ValueError()
except ValueError: sys.exit('请输入有效公网 IPv4。')
PY
IP=$1
[[ -z $(ss -H -ltn 'sport = :80') ]] || fail 'TCP 80 已被占用；IP 证书申请与续期需要使用 TCP 80。'
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then
 ufw allow 80/tcp
else
 echo 'UFW 未启用；如有其他主机防火墙，请放行 TCP 80。'
fi
echo '证书签发及后续续期要求 VPS 厂商防火墙始终允许公网 TCP 80。'
umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl -fSL --retry 3 --connect-timeout 15 --max-time 180 "https://github.com/MetaCubeX/mihomo/releases/download/$VERSION/mihomo-linux-$ARCH-$VERSION.gz" -o "$work/mihomo.gz"
printf '%s  %s\n' "$DIGEST" "$work/mihomo.gz" | sha256sum -c -
gzip -dc "$work/mihomo.gz" > "$work/mihomo"; chmod 0755 "$work/mihomo"
curl -fSL --retry 3 --connect-timeout 15 --max-time 60 'https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/render.py?sha256=fe68ae654453cfcbf239ec81e8410b27d5dfe917135e95167cbf6ff87b40c5ae' -o "$work/render.py"
printf '%s  %s\n' 'fe68ae654453cfcbf239ec81e8410b27d5dfe917135e95167cbf6ff87b40c5ae' "$work/render.py" | sha256sum -c -
install -d -m 0755 "$BIN"
python3 -m venv "$BIN/certbot"
"$BIN/certbot/bin/pip" install 'certbot==5.4.0'
"$BIN/certbot/bin/certbot" certonly --standalone --ip-address "$IP" --preferred-profile shortlived --cert-name "$IP" --agree-tos --register-unsafely-without-email --non-interactive --keep-until-expiring
# Do not delete anything on failure; repeat attempts will detect existing files.
install -m 0755 "$work/mihomo" "$BIN/mihomo"
install -m 0755 "$work/render.py" "$BIN/render.py"
if ! id mihomo-five >/dev/null 2>&1; then useradd --system --user-group --no-create-home --shell /usr/sbin/nologin mihomo-five; fi
GROUP=$(id -gn mihomo-five)
install -d -m 0750 -o root -g "$GROUP" "$ROOT"
install -d -m 0700 "$CLIENTS"
install -m 0640 -o root -g "$GROUP" "/etc/letsencrypt/live/$IP/fullchain.pem" "$ROOT/fullchain.pem"
install -m 0640 -o root -g "$GROUP" "/etc/letsencrypt/live/$IP/privkey.pem" "$ROOT/privkey.pem"
python3 "$BIN/render.py" "$IP" "$work/generated" "$BIN/mihomo" "$ROOT/fullchain.pem" "$ROOT/privkey.pem"
"$BIN/mihomo" -t -f "$work/generated/server.json" -d "$ROOT"
"$BIN/mihomo" -t -f "$work/generated/clash-verge.yaml" -d "$ROOT"
install -m 0640 -o root -g "$GROUP" "$work/generated/server.json" "$ROOT/config.json"
for f in ports.json clash-verge.yaml shadowrocket-nodes.txt shadowrocket.conf; do install -m 0600 "$work/generated/$f" "$CLIENTS/$f"; done
cat > /etc/systemd/system/mihomo-five.service <<UNIT
[Unit]
Description=Mihomo five-protocol server
Wants=network-online.target
After=network-online.target
[Service]
User=mihomo-five
Group=$GROUP
ExecStart=$BIN/mihomo -d $ROOT -f $ROOT/config.json
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
# The marker records the certificate only after a successful restart. If restart
# fails, the next timer run retries even if Certbot considers renewal complete.
cat > "$BIN/deploy-cert" <<HOOK
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
lineage=\${RENEWED_LINEAGE:-/etc/letsencrypt/live/$IP}
new_hash=\$(cat "\$lineage/fullchain.pem" "\$lineage/privkey.pem" | sha256sum | cut -d' ' -f1)
old_hash=\$(cat '$ROOT/loaded-cert.sha256' 2>/dev/null || true)
if [[ \$new_hash == \$old_hash ]]; then exit 0; fi
install -m 0640 -o root -g '$GROUP' "\$lineage/fullchain.pem" '$ROOT/fullchain.new'
install -m 0640 -o root -g '$GROUP' "\$lineage/privkey.pem" '$ROOT/privkey.new'
mv -f '$ROOT/fullchain.new' '$ROOT/fullchain.pem'
mv -f '$ROOT/privkey.new' '$ROOT/privkey.pem'
systemctl restart mihomo-five.service
printf '%s\\n' "\$new_hash" > '$ROOT/loaded-cert.sha256.new'
mv -f '$ROOT/loaded-cert.sha256.new' '$ROOT/loaded-cert.sha256'
HOOK
chmod 0755 "$BIN/deploy-cert"
cat > /etc/systemd/system/mihomo-five-renew.service <<UNIT
[Unit]
Description=Renew Mihomo IP certificate
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=$BIN/certbot/bin/certbot renew --cert-name $IP --deploy-hook $BIN/deploy-cert --non-interactive
ExecStartPost=$BIN/deploy-cert
UNIT
cat > /etc/systemd/system/mihomo-five-renew.timer <<UNIT
[Unit]
Description=Check Mihomo IP certificate renewal
[Timer]
OnBootSec=15min
OnUnitActiveSec=6h
Persistent=true
[Install]
WantedBy=timers.target
UNIT
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then
 while read -r port proto; do ufw allow "$port/$proto"; done < <(python3 - "$CLIENTS/ports.json" <<'PY'
import json,sys
for name, port in json.load(open(sys.argv[1])).items(): print(port,name.split('/')[-1].lower())
PY
 )
fi
systemctl daemon-reload
systemctl enable --now mihomo-five.service mihomo-five-renew.timer
sleep 3
systemctl is-active --quiet mihomo-five.service || fail '服务未启动，请查看 journalctl -u mihomo-five。'
# Mihomo may report listener failures without failing its process; verify every socket.
python3 - "$CLIENTS/ports.json" <<'PY'
import json,subprocess,sys
for name,port in json.load(open(sys.argv[1])).items():
 mode='-lun' if name.endswith('/UDP') else '-ltn'
 out=subprocess.check_output(['ss','-H',mode,'sport = :{}'.format(port)],text=True)
 if not out.strip(): sys.exit('监听失败: '+name+' '+str(port))
PY
# Mark the certificate loaded by the successfully started service, so the first
# routine renewal check does not restart an unchanged service.
cat "/etc/letsencrypt/live/$IP/fullchain.pem" "/etc/letsencrypt/live/$IP/privkey.pem" | sha256sum | cut -d' ' -f1 > "$ROOT/loaded-cert.sha256"
if timeout 90 "$BIN/certbot/bin/certbot" renew --cert-name "$IP" --dry-run --non-interactive; then
 echo 'PASS：证书续期模拟通过；仍需持续监控定时器和实际续期。'
else
 echo '警告：证书续期模拟失败，请立即检查 TCP 80 和 certbot 日志；证书约六天后到期。' >&2
fi
show
echo '请在厂商防火墙放行上面的五个端口和 TCP 80。'
echo '证书有效期约六天；定时器每六小时检查续期，TCP 80 必须一直可从公网访问。'
echo '请在 Mac 和 iPhone 实测；不要公开分享节点凭据。'
