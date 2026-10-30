# Ubuntu 单用户代理一键部署

默认使用 **sing-box + VLESS + REALITY + Vision，TCP 443**。适合只有公网 IPv4、不想购买域名、UDP 连接不稳定的场景。支持 amd64 / arm64；直接使用 systemd，不安装管理面板。固定使用已校验的 sing-box **1.14.4**。

旧 Hysteria 2 的 `install.sh` 保留，文档见 [HYSTERIA2.md](HYSTERIA2.md)。新脚本不会停止或修改旧 HY2；TCP 443 和 UDP 443 可以同时使用。

## 四协议安装（实验版）

在全新 Ubuntu VPS 上运行一个 systemd 服务，生成 VLESS REALITY、Shadowsocks、Hysteria 2、TUIC 四个节点；不使用 Docker。需要公网 IPv4，amd64/arm64、systemd 和可用 apt。示例将 `你的公网IPv4` 替换为服务器地址：

```bash
curl -fSL 'https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install-multi.sh' -o /tmp/install-multi.sh && sudo bash /tmp/install-multi.sh 你的公网IPv4
```

默认占用 TCP 443（REALITY）、TCP 8388（SS）、UDP 8443（HY2）和 UDP 8444（TUIC）。请在云厂商防火墙放行；脚本会先检查端口，不停止已有服务。REALITY 端口可通过第二个参数调整，例如 `公网IPv4 24443`。不适用于直接覆盖已有安装；请在新服务器使用。系统 UFW 启用时会添加规则。

输出 `clash-verge.yaml` 包含四个可选节点。`shadowrocket-nodes.txt` 包含四条节点链接，逐条导入；另将 `shadowrocket.conf` 保存并导入分流配置，首页选择要用的节点。输出包含密码、UUID，切勿公开分享或上传仓库。

HY2 和 TUIC 使用本机生成的专用 CA 签发证书；Mac 配置固定服务端证书 SHA-256 指纹，不跳过验证。iPhone 需将 `root-ca.crt` 分隔线内的 PEM 内容保存为 `.crt`，通过可信、安全渠道传到 iPhone，安装描述文件后，在“设置 → 通用 → 关于本机 → 证书信任设置”中启用该证书的完全信任。安装根证书会扩大系统信任范围，只能信任自己这次安装生成的证书；不要信任陌生证书。CA 私钥仅在服务器临时文件中用于签发并在结束时清理，不会导出。

证书及配置保存在 `/etc/sing-multi` 和 `/root/multi-client`，重启不会重新生成；可 `sudo bash /tmp/install-multi.sh --show` 重新打印输出。叶子证书有效 825 天，当前不支持自动续期，届时需重新部署并更新客户端配置和证书。请勿删除现有文件后直接重试，否则凭据可能改变。

**验证限制：** 服务端配置、证书链、客户端 YAML 与导出格式已离线校验。此环境无法启动 sing-box 网络服务，未完成真实握手、Ubuntu systemd 安装或 Clash Verge / Shadowrocket 真机测试；特别是 Shadowrocket 的 TUIC/HY2 链接字段和系统 CA 信任仍需在真实版本上验证。脚本仅对 REALITY 进行本机代理自检，PASS 不代表四种协议均可用。你的网络此前出现 UDP 不通，HY2 和 TUIC 可能仍然失败。

```bash
sudo systemctl status sing-multi --no-pager -l
sudo journalctl -u sing-multi -n 60 --no-pager
python3 tests/test-multi.py /path/to/sing-box  # 测试环境需要 PyYAML 和 OpenSSL
```

## 原有 REALITY 单协议安装

## 系统要求

不再限制 Ubuntu 版本号，22.04、24.04 等版本均可进入安装流程。需要 64 位 amd64/arm64、正在运行的 systemd、可用的 apt 软件源和公网 IPv4；安装后检查 Python ≥ 3.6、OpenSSL TLS 1.3 能力以及 sing-box 二进制能否运行。

取消版本白名单不代表任意古老 Ubuntu 都能运行：过旧的运行库、内核或失效的软件源仍可能不兼容。优先使用仍受维护的 Ubuntu。未完成所有版本的真实 VPS 安装测试。

## 一条命令安装

先在 VPS 厂商防火墙 / 安全组放行 **TCP 443**，将下面的 `你的公网IPv4` 替换为服务器 IP：

```bash
curl -fSL https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install-reality.sh -o /tmp/install-reality.sh && sudo bash /tmp/install-reality.sh 你的公网IPv4
```

公开仓库，无需登录 GitHub。可先阅读下载的脚本再执行。下载命令需要 `curl`（缺少时先执行 `sudo apt-get update && sudo apt-get install -y curl`）。脚本自动安装 Python 3、iproute2、OpenSSL 等依赖，从 SagerNet 官方 GitHub Release 下载固定版本二进制。需要能访问 Ubuntu 软件源、GitHub 和握手目标。

可选参数：`公网IPv4 TCP端口 握手目标域名`，例如：

```bash
sudo bash /tmp/install-reality.sh 你的公网IPv4 24443 www.microsoft.com
```

默认握手目标是 `www.microsoft.com`，不是你需要拥有的域名。脚本在 VPS 上检查其 TLS 1.3 连通性和证书；目标不通时会停止。更换目标应选择 VPS 可直连、支持 TLS 1.3 的真实网站。目标可达不代表客户端公网链路一定可达。

安装会生成独立 UUID 和 REALITY 密钥，校验配置、启动服务，然后通过本机 REALITY 客户端请求 HTTPS 页面。输出 `PASS` 表示本机握手、认证和代理转发通过；若测试失败会打印警告。最终仍需用 Mac/iPhone 测试公网连接。

## 复制输出到客户端

脚本会打印带“开始 / 结束”分隔线的三段内容。只复制分隔线之间的正文，不要复制分隔线。

- **Mac / Clash Verge（Mihomo 内核）**：保存 YAML 为 `clash-verge.yaml`，导入并启用该配置，选择 `REALITY`，开启系统代理。系统代理仅覆盖遵循系统代理的应用；需要全设备接管时使用客户端 TUN 并另行验证 DNS、IPv6 和应用流量。
- **iPhone / Shadowrocket**：先复制整条 `vless://…` 链接并导入节点；再将 CONF 保存为 `shadowrocket.conf`，通过文件分享导入并启用；首页选择 `REALITY` 节点，路由选“配置”。**CONF 只包含分流规则，不能单独建立连接，节点链接必须导入。** 采用两步方式避免依赖不同版本的配置内节点语法。

客户端应使用支持 VLESS REALITY / Vision 的版本。全部凭据一致生成，不需要在线订阅转换。

默认服务器 IP、回环和局域网 IPv4 直连，其余经代理。未包含中国大陆分流、广告屏蔽或订阅服务。不是游戏加速方案；TCP 丢包时仍会影响速度，实际吞吐取决于 VPS 线路、带宽和负载。

## 隐私与权限

REALITY 使用服务端公钥验证，不需要自签证书，也不启用跳过证书验证。私钥只保存在服务器端；客户端配置和链接包含访问凭据，不能提交到 GitHub 或分享截图。

服务使用独立低权限账户，配置目录限制访问。服务端配置为 `/etc/sing-reality/config.json`，客户端文件保存在 root 私有目录 `/root/reality-client/`。日志级别为 `warn`，不启用普通访问日志；错误日志仍可能包含连接信息。

自建代理不等于匿名：VPS 厂商和目标网站仍能看到各自连接信息。当前配置不承诺 DNS 防泄漏；小火箭默认使用系统 DNS，Mac 的 DNS 行为取决于客户端接管方式。仍应使用 HTTPS。公开仓库仅存通用脚本，不存实际部署的 UUID、密钥或客户端配置。

## 管理与排查

```bash
# 重新打印三段客户端内容（需保留或重新下载脚本）
sudo bash /tmp/install-reality.sh --show
sudo systemctl status sing-reality --no-pager -l
sudo journalctl -u sing-reality -n 60 --no-pager
sudo ss -ltnp 'sport = :443'
sudo systemctl restart sing-reality
```

UFW 已启用时脚本添加所选 TCP 端口规则；不会启用、停用或重置 UFW。厂商防火墙及其他 nftables/iptables 规则需要自行检查。

重复安装发现已有目录或服务文件时会停止，避免覆盖凭据。中途失败时先查看日志和现有文件，不要直接删除配置重试。安装不会自动回滚已经写入的文件。

确认新节点在两端正常后，可以停止旧 HY2：

```bash
sudo systemctl disable --now hysteria-server
```

## 验证范围

```bash
bash -n install-reality.sh
python3 tests/test-platform.py
# 测试机需 PyYAML；不会安装服务或修改防火墙
python3 tests/test-reality.py /path/to/sing-box
```

已用官方 sing-box 1.14.4 检查服务端 / 自检客户端配置，并验证 YAML 解析、跨客户端凭据一致、输出不含服务端私钥、文件权限及非法输入拒绝。测试环境限制网络套接字创建，未完成真实握手与 Mac/iPhone 实测；安装器会在 VPS 上执行本机端到端测试。此脚本不是上游官方安装器。

## 官方参考

- [sing-box VLESS](https://sing-box.sagernet.org/configuration/inbound/vless/)
- [sing-box TLS / REALITY](https://sing-box.sagernet.org/configuration/shared/tls/)
- [sing-box 官方版本](https://github.com/SagerNet/sing-box/releases)
- [Mihomo VLESS](https://wiki.metacubex.one/config/proxies/vless/)
