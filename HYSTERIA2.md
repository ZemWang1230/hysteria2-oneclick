# Hysteria 2 一键部署

面向 Ubuntu、64 位 amd64/arm64、公网 IPv4 的单用户部署。使用官方安装器 + systemd；自动生成密码和自签证书，终端打印 Clash Verge YAML、Shadowrocket CONF 和节点链接。

## 使用

先在云安全组放行所选 **UDP 端口**（默认 443）。系统 UFW 已启用时脚本自动添加对应规则；不会开启、关闭或重置 UFW。其他防火墙需自行配置。不需要域名或 TCP 80。

公开仓库：`ZemWang1230/hysteria2-oneclick`。服务器无需登录 GitHub，替换公网 IPv4 后执行：

```bash
curl -fSL https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install.sh -o /tmp/hy2-install.sh && sudo bash /tmp/hy2-install.sh 你的公网IPv4
```

可在最后增加端口，例如 `你的公网IPv4 8443`。默认安装当时官方最新版本；首次运行需要访问 Ubuntu 软件源、官方安装站及安装器所需下载源。不限制 Ubuntu 版本号；需运行中的 systemd 和可用的 apt 软件源。自动安装 Python 3、iproute2 等依赖；要求 Python ≥ 3.6 和支持 `-addext` 的 OpenSSL。上游安装器及二进制仍有自身兼容要求，未承诺所有旧版本可用。下载命令需要预装 curl。运行前可以检查下载的脚本。无需向任何在线订阅转换网站发送密码。

## 导入

- Mac：复制输出分隔线之间的 YAML，保存为 `clash-verge.yaml`，导入使用 Mihomo 内核的 Clash Verge，选用该配置并开启系统代理。系统代理只覆盖遵循系统代理的应用；需要其他流量时自行配置客户端 TUN。
- iPhone：将 CONF 保存为 `shadowrocket.conf`，通过文件分享导入 Shadowrocket，启用配置，路由选择“配置”。如版本未识别配置内节点，可使用输出的 `hysteria2://` 链接添加。
- 默认局域网 IPv4 直连，其余代理；无中国大陆分流表、广告过滤、订阅服务或额外面板。未承诺 DNS 防泄漏、所有应用全设备隧道或特定吞吐。

## 证书与凭据

Clash 配置固定 SHA-256 证书指纹。Shadowrocket 兼容配置和备用链接使用 `allowInsecure=1` / `insecure=1`，**跳过服务器身份验证，存在中间人风险**；不能宣称它与指纹固定同等安全。需要完整身份校验时，应改为该客户端验证支持的证书固定或可信证书方案，不应仅忽略证书错误。

`hy2.internal` 只是自签证书名称，无需注册或解析。证书有效期 10 年，无自动续期；更换证书后需重新导出指纹配置。

密码、私钥、配置仅生成于部署服务器；不会上传 GitHub。客户端配置位于 root 私有目录 `/root/hy2-client`。服务账户可读服务端配置和私钥，其他普通用户不能读取。不要分享含密码的输出、截图或日志。

## 管理

```bash
sudo bash /tmp/hy2-install.sh --show
sudo systemctl status hysteria-server --no-pager
sudo journalctl -u hysteria-server -n 60 --no-pager
sudo systemctl restart hysteria-server
sudo systemctl stop hysteria-server
```

重复安装会在发现已有配置/输出目录时停止，不覆盖密码或证书。失败后检查日志与现有文件，不要为了重试而直接删除有效配置。`--show` 可重新打印已生成的客户端配置。

## 验证范围

```bash
bash -n install.sh
bash install.sh --self-test
```

离线检查涵盖 IP/端口边界、输出格式关键字段及凭据文件权限。安装期间检查服务 active 和 UDP 监听。尚未在用户服务器及真实 Mac/iPhone 上完成端到端实测；需在设备导入后检查连接和出口 IP。

## 参考

- https://v2.hysteria.network/docs/getting-started/Server-Installation-Script/
- https://v2.hysteria.network/docs/getting-started/Server/
- https://wiki.metacubex.one/config/proxies/hysteria2/
- https://github.com/jinofhust/shadowrocket

此仓库脚本为独立部署包装，非 Hysteria 或客户端官方项目。
