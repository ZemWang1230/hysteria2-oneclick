#!/usr/bin/env python3
"""Install five services on a fresh Ubuntu host, without modifying unrelated servers."""
import ipaddress, json, os, pathlib, shutil, subprocess, sys, tempfile, urllib.request
import clients, services, state

BIN=pathlib.Path('/usr/local/lib/dual-proxy')
ETC=pathlib.Path('/etc/dual-proxy')
WEB=pathlib.Path('/var/lib/dual-proxy')
OUTPUT=pathlib.Path('/root/dual-proxy-client')
CERT='/etc/letsencrypt/live/dual-proxy-ip/'

def run(*args, **kw):
    print('+', ' '.join(map(str,args)), flush=True)
    return subprocess.run(args,check=True,**kw)

def fetch(url, digest, destination):
    run('curl','-fL','--retry','3','-o',destination,url)
    import hashlib
    h=hashlib.sha256(pathlib.Path(destination).read_bytes()).hexdigest()
    if h!=digest: raise RuntimeError('下载文件校验失败: '+url)

def detect():
    addresses=[]
    for flag,url in [('-4','https://api.ipify.org'),('-6','https://api64.ipify.org')]:
        r=subprocess.run(['curl','-fsS',flag,'--max-time','8',url],capture_output=True,text=True)
        if r.returncode==0:
            try:
                a=ipaddress.ip_address(r.stdout.strip())
                if a.is_global and a.version==int(flag[1]):addresses.append(str(a))
            except ValueError:pass
    return addresses

def write(path, body, mode=0o600):
    path=pathlib.Path(path); path.write_text(body);path.chmod(mode)

def unit(name,cmd,user='dualproxy',extra=''):
    return f'''[Unit]\nDescription=Dual proxy {name}\nAfter=network-online.target\nWants=network-online.target\n[Service]\nUser={user}\nExecStart={cmd}\n{extra}Restart=on-failure\nRestartSec=3\nNoNewPrivileges=true\nPrivateTmp=true\n[Install]\nWantedBy=multi-user.target\n'''

def main():
    addresses=sys.argv[1:] or detect()
    if not addresses: raise RuntimeError('无法自动检测公网 IP；请手动在命令后传入公网 IPv4 和/或 IPv6。')
    parsed=[ipaddress.ip_address(a) for a in addresses]
    if len(parsed)>2 or len({x.version for x in parsed})!=len(parsed) or any(not x.is_global for x in parsed):raise RuntimeError('请提供一个公网 IPv4 和/或一个公网 IPv6。')
    addresses=[str(x) for x in parsed]
    print('准备使用公网地址:', ', '.join(addresses),flush=True)
    print('签发和续期需公网 TCP 80 可达；请同时在 VPS 厂商防火墙放行。',flush=True)
    if shutil.which('ufw') and 'Status: active' in subprocess.run(['ufw','status'],capture_output=True,text=True).stdout:run('ufw','allow','80/tcp')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=pathlib.Path(tmp)
        downloads=[
         ('https://github.com/shadowsocks/shadowsocks-rust/releases/download/v1.25.0/shadowsocks-v1.25.0.x86_64-unknown-linux-musl.tar.xz','8439bf43c324b0fc273e663d0b1f8926fd8f666cbd1e0fd59b35096f0e778e92','ss.tar.xz'),
         ('https://github.com/v2fly/v2ray-core/releases/download/v5.53.0/v2ray-linux-64.zip','6bbb8aee65a57d0b12599b4b7c842b3ad0daca4436e661d94015c447cb31b4fa','v2ray.zip'),
         ('https://github.com/XTLS/Xray-core/releases/download/v26.6.27/Xray-linux-64.zip','b3e5902d06d6282fe53cfa2fc426058b9aeaa429b2c812e20887cd47f26d08bf','xray.zip'),
         ('https://github.com/apernet/hysteria/releases/download/app/v2.13.0/hysteria-linux-amd64','907ba8c9693edb104b20582681fb7dc15639d5b64a9cbb616a7b539190a86691','hysteria'),
         ('https://github.com/yeahwu/v2ray-wss/releases/download/v-monthly/caddy-v-monthly.tar.gz','a12b3919140309b15e254a48d5dd2d7992c0f1e9ac1d79aefa31698d049d2956','caddy.tar.gz')]
        for url,digest,name in downloads:fetch(url,digest,str(tmp/name))
        for name in ('ss','v2ray','xray','caddy'):(tmp/name).mkdir()
        run('tar','-xJf',str(tmp/'ss.tar.xz'),'-C',str(tmp/'ss'))
        run('unzip','-qo',str(tmp/'v2ray.zip'),'-d',str(tmp/'v2ray'))
        run('unzip','-qo',str(tmp/'xray.zip'),'-d',str(tmp/'xray'))
        run('tar','-xzf',str(tmp/'caddy.tar.gz'),'-C',str(tmp/'caddy'))
        BIN.mkdir(parents=True,exist_ok=True);BIN.chmod(0o755)
        for name,source in [('ssserver',tmp/'ss/ssserver'),('v2ray',tmp/'v2ray/v2ray'),('xray',tmp/'xray/xray'),('hysteria',tmp/'hysteria'),('caddy',tmp/'caddy/caddy')]:shutil.copyfile(source,BIN/name);(BIN/name).chmod(0o755)
        if 'http.handlers.forward_proxy' not in subprocess.check_output([str(BIN/'caddy'),'list-modules'],text=True):raise RuntimeError('Caddy 缺少 forward_proxy 模块。')
    # Python virtualenv isolates the Certbot version required for IP certificates.
    if not (BIN/'certbot/bin/certbot').exists():
        run('python3','-m','venv',str(BIN/'certbot'))
        run(str(BIN/'certbot/bin/pip'),'install','certbot==5.4.0')
    certbot=str(BIN/'certbot/bin/certbot')
    args=[certbot,'certonly','--standalone','--non-interactive','--agree-tos','--register-unsafely-without-email','--preferred-profile','shortlived','--cert-name','dual-proxy-ip']
    for addr in addresses:args+=['--ip-address',addr]
    run(*args)
    s=state.make(addresses,str(BIN/'xray'))
    if subprocess.run(['getent','group','dualproxy'],stdout=subprocess.DEVNULL).returncode:run('groupadd','--system','dualproxy')
    if subprocess.run(['id','-u','dualproxy'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:run('useradd','--system','--gid','dualproxy','--no-create-home','--shell','/usr/sbin/nologin','dualproxy')
    ETC.mkdir(mode=0o750);WEB.mkdir(mode=0o750);OUTPUT.mkdir(mode=0o700,exist_ok=True)
    ETC.chmod(0o750);WEB.chmod(0o750)
    run('chown','root:dualproxy',str(ETC));run('chown','root:www-data',str(WEB));OUTPUT.chmod(0o700)
    for d in ['client','proxy','fastcgi','uwsgi','scgi']:
        p=pathlib.Path('/var/cache/dual-proxy/nginx')/d;p.mkdir(parents=True,exist_ok=True);p.parent.parent.chmod(0o755);p.parent.chmod(0o755);p.chmod(0o700);run('chown','www-data:www-data',str(p))
    run('openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',str(ETC/'hy2.key'),'-out',str(ETC/'hy2.crt'),'-days','3650','-subj','/CN=bing.com')
    for f in ['fullchain.pem','privkey.pem']:
        shutil.copyfile(CERT+f,ETC/f)
    for f in ['fullchain.pem','privkey.pem','hy2.key','hy2.crt']:
        os.chmod(ETC/f,0o640);run('chown','root:dualproxy',str(ETC/f))
    paths={'prefix':str(WEB),'certificate':str(ETC/'fullchain.pem'),'private_key':str(ETC/'privkey.pem'),'hy2_cert':str(ETC/'hy2.crt'),'hy2_key':str(ETC/'hy2.key'),'nginx_temp':'/var/cache/dual-proxy/nginx','nginx_pid':'/run/dual-proxy-nginx.pid'}
    for name,body in services.render(s,paths).items():
        write(ETC/name,body,0o600 if name=='nginx.conf' else 0o640)
        if name!='nginx.conf':run('chown','root:dualproxy',str(ETC/name))
    write(ETC/'state.json',json.dumps(s,indent=2)+'\n')
    for name,body in clients.build(s).items():
        write(OUTPUT/name,body)
        if name in ('clash-verge.yaml','shadowrocket-subscription.txt','shadowrocket.conf'):
            write(WEB/name,body,0o640);run('chown','root:www-data',str(WEB/name))
    token=s['credentials']['subscription_token'];port=s['ports']['subscription']
    urls=[]
    for ip in addresses:
        host='['+ip+']' if ':' in ip else ip
        urls.append(f'{ip}:\n  Clash Verge: https://{host}:{port}/{token}/clash\n  Shadowrocket: https://{host}:{port}/{token}/shadowrocket\n  Shadowrocket 规则: https://{host}:{port}/{token}/shadowrocket.conf')
    p=s['ports'];ports=f"TCP 80 (证书签发和续期)\nTCP+UDP {p['ss']} (Shadowsocks)\nTCP {p['vmess']} (VMess+WS+TLS)\nTCP {p['reality']} (REALITY)\nUDP {p['hy2']} (Hysteria2)\nTCP {p['https']} (HTTPS 代理)\nTCP {p['subscription']} (私密订阅)\n"
    write(OUTPUT/'ports.txt',ports);write(OUTPUT/'subscriptions.txt','\n'.join(urls)+'\n')
    definitions={'ss':f'{BIN}/ssserver -c {ETC}/ss.json','v2ray':f'{BIN}/v2ray run -c {ETC}/v2ray.json','xray':f'{BIN}/xray run -config {ETC}/xray.json','hy2':f'{BIN}/hysteria server --disable-update-check -c {ETC}/hysteria.json','https':f'{BIN}/caddy run --config {ETC}/Caddyfile --adapter caddyfile','nginx':f'/usr/sbin/nginx -c {ETC}/nginx.conf -g "daemon off;"'}
    for name,cmd in definitions.items():
        extra='Environment=HOME=/var/lib/dual-proxy-caddy\nStateDirectory=dual-proxy-caddy\n' if name=='https' else ''
        if name=='nginx':extra=f'ExecReload=/usr/sbin/nginx -s reload -c {ETC}/nginx.conf\n'
        write('/etc/systemd/system/dual-proxy-'+name+'.service',unit(name,cmd,'root' if name=='nginx' else 'dualproxy',extra),0o644)
    run('/usr/sbin/nginx','-t','-c',str(ETC/'nginx.conf'))
    run(str(BIN/'v2ray'),'test','-config',str(ETC/'v2ray.json'))
    run(str(BIN/'xray'),'run','-test','-config',str(ETC/'xray.json'))
    run(str(BIN/'caddy'),'validate','--config',str(ETC/'Caddyfile'),'--adapter','caddyfile')
    # Refresh files after successful renewal, and on subsequent runs if reloading failed.
    renew=f'''#!/bin/sh\nset -eu\ninstall -o root -g dualproxy -m 640 {CERT}fullchain.pem {ETC}/fullchain.pem\ninstall -o root -g dualproxy -m 640 {CERT}privkey.pem {ETC}/privkey.pem\n/usr/sbin/nginx -t -c {ETC}/nginx.conf\n{BIN}/caddy validate --config {ETC}/Caddyfile --adapter caddyfile\nsystemctl reload dual-proxy-nginx\nsystemctl restart dual-proxy-https\n'''
    write(BIN/'renew-deploy',renew,0o700)
    write('/etc/systemd/system/dual-proxy-renew.service',f'[Unit]\nDescription=Renew IP certificate\n[Service]\nType=oneshot\nExecStart={certbot} renew --cert-name dual-proxy-ip --quiet\nExecStartPost={BIN}/renew-deploy\n',0o644)
    write('/etc/systemd/system/dual-proxy-renew.timer','[Unit]\nDescription=Check IP certificate every six hours\n[Timer]\nOnBootSec=10min\nOnUnitActiveSec=6h\nPersistent=true\n[Install]\nWantedBy=timers.target\n',0o644)
    if shutil.which('ufw') and 'Status: active' in subprocess.run(['ufw','status'],capture_output=True,text=True).stdout:
        for name,proto in [('ss','tcp'),('ss','udp'),('vmess','tcp'),('reality','tcp'),('hy2','udp'),('https','tcp'),('subscription','tcp')]:run('ufw','allow',str(p[name])+'/'+proto)
    run('systemctl','daemon-reload')
    for name in definitions:run('systemctl','enable','--now','dual-proxy-'+name+'.service')
    run('systemctl','enable','--now','dual-proxy-renew.timer')
    for name in definitions:run('systemctl','is-active','--quiet','dual-proxy-'+name+'.service')
    print('\n安装完成。请在 VPS 厂商防火墙放行以下端口：\n'+ports,flush=True)
    for f in sorted(OUTPUT.iterdir()):print('\n========== '+f.name+' ==========\n'+f.read_text(),flush=True)
    print('订阅链接及节点含密码，请勿公开。HY2 使用自签名证书且关闭验证，有中间人风险。',flush=True)

if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except (RuntimeError,ValueError,subprocess.CalledProcessError,OSError) as e:sys.exit('部署失败：'+str(e)+'；请检查上述错误和 systemctl/journalctl 输出。')
