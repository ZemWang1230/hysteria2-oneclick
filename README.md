# Ubuntu 四协议一键部署

在全新 Ubuntu 64 位 VPS 上使用 sing-box 和 systemd，提供 **VLESS REALITY、Shadowsocks、Hysteria 2、TUIC**。不需要 Docker 或域名。需要公网 IPv4、运行中的 systemd、可用的 apt 软件源和 curl。

## 安装

将 `你的公网IPv4` 替换为服务器地址，执行：

```bash
curl -fSL 'https://raw.githubusercontent.com/ZemWang1230/hysteria2-oneclick/main/install-multi.sh' -o /tmp/install-multi.sh && sudo bash /tmp/install-multi.sh 你的公网IPv4
```

脚本随机选择四个不同的 **20000–29999** 端口并打印：REALITY、SS 使用 TCP；HY2、TUIC 使用 UDP。UFW 已启用时自动放行；其他主机防火墙及厂商防火墙需自行放行对应端口。脚本不会覆盖已有部署或停止旧服务。

## 导入

复制终端输出中各段分隔线之间的内容：

- **Mac / Clash Verge：** 保存 `clash-verge.yaml` 并导入，在 `PROXY` 组中选择节点。
- **iPhone / Shadowrocket：** 逐条导入 `shadowrocket-nodes.txt` 中的节点链接，再保存并导入 `shadowrocket.conf` 分流配置；在首页选择节点。
- **iPhone 的 HY2 / TUIC：** 将 `root-ca.crt` 保存为证书文件，通过可信渠道传到 iPhone，安装后在「设置 → 通用 → 关于本机 → 证书信任设置」中启用完全信任。信任根证书会扩大系统信任范围，只应信任自己服务器生成的证书。

客户端配置及节点链接包含凭据，**不要公开分享或提交到 GitHub**。证书有效期 825 天，当前不支持自动续期。

## 管理

```bash
sudo bash /tmp/install-multi.sh --show          # 重新打印配置和端口
sudo systemctl status sing-multi --no-pager -l  # 查看状态
sudo journalctl -u sing-multi -n 60 --no-pager # 查看日志
sudo systemctl restart sing-multi               # 重启
```

## 验证范围

服务端配置、证书链和客户端导出已离线检查，YAML 已通过 Mihomo 配置校验。**尚未完成四协议真实连接及 Shadowrocket 真机验证**；安装时的本机自检只覆盖 REALITY。HY2 和 TUIC 依赖 UDP，UDP 不通时无法使用。

旧版脚本：[REALITY 单协议](install-reality.sh) · [Hysteria 2 文档](HYSTERIA2.md)。
