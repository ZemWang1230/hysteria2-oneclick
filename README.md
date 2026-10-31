# Ubuntu 五协议一键部署

在 Ubuntu 64 位 VPS 上用一个 Mihomo 服务同时提供 SS、VMess + WS + TLS、VLESS REALITY、Hysteria 2、HTTPS 正向代理；无需 Docker 或域名。需要公网 IPv4、Python 3.10+、systemd 和可用软件源。

## 安装

先在 VPS 厂商防火墙放行 **TCP 80**（用于签发和续期证书），替换 IP 后运行：

```bash
curl -fSL 'https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install.sh' -o /tmp/proxy-install.sh && sudo bash /tmp/proxy-install.sh 你的公网IPv4
```

安装随机选择五个 20000–29999 端口，打印端口及协议；REALITY、SS、VMess、HTTPS 为 TCP，HY2 为 UDP。UFW 已启用时自动放行；其他防火墙和厂商安全组需自行放行。请保持 TCP 80 公网可达，且不要被其他服务占用。重复安装不会覆盖既有配置。

公网 IP 证书由 Let's Encrypt 签发，有效期约六天。systemd 定时器每六小时检查续期；续期后重启代理以加载证书。安装时运行续期模拟；如失败立即排查。未配置邮件告警，请定期检查定时器与日志。

## 导入

- **Mac：** 保存输出的 `clash-verge.yaml` 并导入，在 PROXY 中切换节点；JSON 也是 YAML 的有效格式。
- **iPhone：** 逐条导入 `shadowrocket-nodes.txt` 中四条链接；HTTPS 正向代理按同一段输出中的地址、端口、用户名、密码手动添加，启用 TLS 和证书验证。保存并导入 `shadowrocket.conf` 分流配置。

使用公开可信 IP 证书，无需安装根 CA；证书续期不会更改客户端配置。节点内容含凭据，不要公开分享。默认局域网直连，其余代理；系统代理不一定覆盖所有应用或 DNS。

## 管理

```bash
sudo bash /tmp/proxy-install.sh --show
sudo systemctl status mihomo-five --no-pager -l
sudo journalctl -u mihomo-five -n 60 --no-pager
sudo systemctl status mihomo-five-renew.timer
sudo journalctl -u mihomo-five-renew -n 60 --no-pager
sudo /usr/local/lib/mihomo-five/certbot/bin/certbot renew --dry-run
```

安装中断后请先检查输出和日志，不要直接删除已有凭据；安装并非自动回滚。`--show` 会输出秘密，只在安全的终端使用。

## 验证范围

Mihomo 1.19.33 已通过五节点服务端和客户端配置检查、本地双端 HTTP 代理转发，以及错误密码/证书拒绝测试。真实公网 IP 证书签发与自动续期、systemd 低权限服务、Mac/iPhone 真机导入尚未实测，特别是 Shadowrocket 配置兼容性需在设备上验证。HY2 依赖 UDP，网络阻断 UDP 时无法使用。
