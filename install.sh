#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[[ $EUID == 0 ]] || { echo '请使用 sudo bash install.sh'; exit 1; }
if [[ ${1:-} == --show ]]; then
  for f in /root/dual-proxy-client/*; do [[ -f $f ]] && { printf '\n========== %s ==========\n' "${f##*/}"; cat "$f"; }; done
  exit 0
fi
source /etc/os-release
[[ ${ID:-} == ubuntu ]] || { echo '仅支持 Ubuntu。'; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo '参考项目 Caddy forward_proxy 二进制仅提供 x86_64；当前架构暂不支持。'; exit 1; }
command -v systemctl >/dev/null && [[ -d /run/systemd/system ]] || { echo '需要以 systemd 启动的系统。'; exit 1; }
[[ ! -e /etc/dual-proxy && ! -e /var/lib/dual-proxy && ! -e /root/dual-proxy-client ]] || { echo '检测到现有安装，请勿重复运行。查看配置请执行 sudo bash install.sh --show'; exit 1; }
if command -v ss >/dev/null && ss -ltnH '( sport = :80 )' | grep -q .; then echo 'TCP 80 已被占用；签发证书需要端口空闲。'; exit 1; fi
had_nginx=0
if command -v nginx >/dev/null || systemctl cat nginx.service >/dev/null 2>&1; then had_nginx=1; fi
apt-get update
apt-get install -y ca-certificates curl coreutils iproute2 openssl python3 python3-venv xz-utils unzip tar
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo '证书工具需要 Python 3.10 或更高版本（建议 Ubuntu 22.04 或更新版本）。'; exit 1; }
apt-get install -y nginx
if [[ $had_nginx == 0 ]]; then systemctl disable --now nginx || true; fi
if ss -ltnH '( sport = :80 )' | grep -q .; then echo 'TCP 80 被其他服务占用，请释放后重试。'; exit 1; fi
umask 077
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
base='https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main'
while read -r hash name; do
  curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 "$base/$name?sha256=$hash" -o "$work/$name"
  printf '%s  %s\n' "$hash" "$work/$name" | sha256sum --check --status || { echo "下载校验失败: $name"; exit 1; }
done <<'CHECKSUMS'
557899afc5b934bb7b718ed0217490114adbee49727645282f8df91b8eaf53c1 deploy.py
94982bf3016099a90e149cdec872641c4a91be6cc4ecf70902eecc929edb00cf state.py
4daf7b10814ef87a9e4ab5a5eaf1a84a690d976d6046135cd6fe05b28c41350f services.py
69ccf2489b6fc209ab6fb0f45e11e5ff6f6dd195e003126184f791e4d7011de8 clients.py
c818a01dc285da8ae13fd1f4b8c09f7b8884bd33cce98479fa0d52858c1d1eac hy2.py
CHECKSUMS
python3 "$work/deploy.py" "$@"
