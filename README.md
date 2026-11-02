# 五协议一键部署

在全新 Ubuntu x86_64 VPS 上一次安装 Shadowsocks-rust、V2Ray VMess + WS + TLS、Xray VLESS + REALITY + Vision、Hysteria 2 和 Caddy HTTPS 正向代理。不使用 Docker；每个服务分配不同的随机端口。支持只有 IPv4、只有 IPv6 或双栈，前提是所用公网地址确实可被客户端访问。

## 安装

在 VPS 上执行：

```bash
sudo apt-get update && sudo apt-get install -y curl && curl -fsSL https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install.sh -o /tmp/install-five.sh && sudo bash /tmp/install-five.sh
```

默认自动检测公网 IP；也可手动指定，例如：`sudo bash /tmp/install-five.sh 你的IPv4 你的IPv6`，单栈则只写一个地址。仅使用属于该 VPS、可以被公网访问的 IP。

证书首次签发和后续续期需要公网 TCP 80 畅通且未被其他服务占用。安装结束会显示所有端口，请在 VPS 厂商的防火墙或安全组中放行相应 TCP/UDP 端口。UFW 已开启时脚本添加规则，不会自动开启 UFW；使用 IPv6 的话还需确保 UFW 的 IPv6 防火墙和厂商安全组允许相应流量。

## 导入

安装结束会显示配置和订阅地址，稍后可用 `sudo bash /tmp/install-five.sh --show` 再次查看：

- Clash Verge：导入 `clash-verge.yaml` 内容或 Clash 订阅 URL；包含所有协议的 IPv4/IPv6 节点。
- Shadowrocket：添加 Shadowrocket 订阅 URL 导入 SS、VMess、REALITY、HY2 节点；`shadowrocket.conf` 是可选规则配置。HTTPS 正向代理需根据 `shadowrocket-https-manual.json` 手动添加，类型选 HTTPS，并开启证书验证。

订阅 URL、节点和配置包含密码，请勿公开。订阅 URL 是不易猜测的私密链接，持有链接的人可读取节点。相关文件保存在 `/root/dual-proxy-client/`。

## 注意

- Hysteria 2 沿用参考项目的自签名证书方案，客户端关闭证书验证，存在中间人攻击风险。其余 TLS 和订阅使用 Let's Encrypt IP 证书，证书有效期约 6 天，systemd 定时续期。请确保 TCP 80 长期可访问。
- 本项目使用参考项目的 Caddy forward_proxy 构建，目前只支持 x86_64。Xray 固定在与测试用 Mihomo 兼容的 26.6.27；应关注上游安全更新。Caddy 上游使用可变的 monthly 文件名，本项目验证固定 SHA-256，上游更新文件后会安全地停止安装，需更新校验值。
- 网络实际速度取决于 VPS 线路及 TCP/UDP 通路；IP 证书签发需要 CA 能从公网访问每个指定地址。脚本不会覆盖已检测到的本项目安装或占用的 TCP 80。
- 参照 [yeahwu/v2ray-wss](https://github.com/yeahwu/v2ray-wss)，见 LICENSE 和 NOTICE。
