#!/usr/bin/env python3
import base64, ipaddress, json, os, pathlib, secrets, socket, subprocess, sys, uuid
from urllib.parse import quote, urlencode

def generate(ip, directory, binary, certificate, private_key, host='www.microsoft.com'):
    ipaddress.IPv4Address(ip)
    p = pathlib.Path(directory); p.mkdir(mode=0o700, parents=True, exist_ok=True)
    sockets=[]; ports=[]
    try:
        while len(ports)<5:
            port=20000+secrets.randbelow(10000)
            if port in ports: continue
            sockets_here=[]
            try:
                for typ in (socket.SOCK_STREAM,socket.SOCK_DGRAM):
                    s=socket.socket(socket.AF_INET,typ); sockets_here.append(s); s.bind(('0.0.0.0',port))
            except OSError:
                for s in sockets_here: s.close()
                continue
            sockets.extend(sockets_here); ports.append(port)
    finally:
        for s in sockets: s.close()
    ss, vm, vl, hy, ht = ports
    keys=dict(line.split(':',1) for line in subprocess.check_output([binary,'generate','reality-keypair'],universal_newlines=True).splitlines() if ':' in line)
    priv,public=keys['PrivateKey'].strip(),keys['PublicKey'].strip()
    sid=secrets.token_hex(8); vu=str(uuid.uuid4()); ru=str(uuid.uuid4()); path='/'+secrets.token_hex(12)
    sp,hp,pp=[secrets.token_hex(24) for _ in range(3)]; username='proxy'
    tls={'certificate':certificate,'private-key':private_key}
    listeners=[
      {'name':'ss','type':'shadowsocks','listen':'0.0.0.0','port':ss,'cipher':'chacha20-ietf-poly1305','password':sp,'udp':False},
      {'name':'vmess','type':'vmess','listen':'0.0.0.0','port':vm,'users':[{'username':'owner','uuid':vu,'alterId':0}],'ws-path':path,**tls},
      {'name':'reality','type':'vless','listen':'0.0.0.0','port':vl,'users':[{'username':'owner','uuid':ru,'flow':'xtls-rprx-vision'}],'reality-config':{'dest':host+':443','private-key':priv,'short-id':[sid],'server-names':[host]}},
      {'name':'hysteria2','type':'hysteria2','listen':'0.0.0.0','port':hy,'users':{'owner':hp},'alpn':['h3'],**tls},
      {'name':'https','type':'http','listen':'0.0.0.0','port':ht,'users':[{'username':username,'password':pp}],**tls}]
    server={'mode':'rule','log-level':'warning','listeners':listeners,'rules':['IP-CIDR,127.0.0.0/8,REJECT,no-resolve','IP-CIDR,10.0.0.0/8,REJECT,no-resolve','IP-CIDR,172.16.0.0/12,REJECT,no-resolve','IP-CIDR,192.168.0.0/16,REJECT,no-resolve','IP-CIDR,169.254.0.0/16,REJECT,no-resolve','MATCH,DIRECT']}
    proxies=[{'name':'SS','type':'ss','server':ip,'port':ss,'cipher':'chacha20-ietf-poly1305','password':sp,'udp':False},
      {'name':'VMess-WS-TLS','type':'vmess','server':ip,'port':vm,'uuid':vu,'alterId':0,'cipher':'auto','tls':True,'servername':ip,'network':'ws','ws-opts':{'path':path},'skip-cert-verify':False},
      {'name':'REALITY','type':'vless','server':ip,'port':vl,'uuid':ru,'network':'tcp','tls':True,'flow':'xtls-rprx-vision','servername':host,'client-fingerprint':'chrome','reality-opts':{'public-key':public,'short-id':sid}},
      {'name':'HY2','type':'hysteria2','server':ip,'port':hy,'password':hp,'sni':ip,'skip-cert-verify':False},
      {'name':'HTTPS','type':'http','server':ip,'port':ht,'username':username,'password':pp,'tls':True,'sni':ip,'skip-cert-verify':False}]
    client={'mixed-port':7890,'allow-lan':False,'mode':'rule','log-level':'warning','ipv6':False,'proxies':proxies,'proxy-groups':[{'name':'PROXY','type':'select','proxies':[x['name'] for x in proxies]}],'rules':['IP-CIDR,'+ip+'/32,DIRECT,no-resolve','IP-CIDR,127.0.0.0/8,DIRECT,no-resolve','IP-CIDR,10.0.0.0/8,DIRECT,no-resolve','IP-CIDR,172.16.0.0/12,DIRECT,no-resolve','IP-CIDR,192.168.0.0/16,DIRECT,no-resolve','MATCH,PROXY']}
    b64=lambda x:base64.urlsafe_b64encode(x.encode()).decode().rstrip('=')
    vmess={'v':'2','ps':'VMess-WS-TLS','add':ip,'port':str(vm),'id':vu,'aid':'0','scy':'auto','net':'ws','type':'none','host':ip,'path':path,'tls':'tls','sni':ip}
    nodes=['ss://'+b64('chacha20-ietf-poly1305:'+sp)+'@'+ip+':'+str(ss)+'#SS', 'vmess://'+base64.b64encode(json.dumps(vmess,separators=(',',':')).encode()).decode(), 'vless://'+ru+'@'+ip+':'+str(vl)+'?'+urlencode({'encryption':'none','security':'reality','type':'tcp','sni':host,'fp':'chrome','pbk':public,'sid':sid,'flow':'xtls-rprx-vision'})+'#REALITY', 'hysteria2://'+hp+'@'+ip+':'+str(hy)+'/?'+urlencode({'sni':ip,'insecure':'0'})+'#HY2']
    # Shadowrocket HTTPS URI support differs by version; supply explicit fields instead.
    info='HTTPS 正向代理：类型 HTTPS；地址 {}；端口 {}；用户名 {}；密码 {}；TLS 验证开启。\n'.format(ip,ht,username,pp)
    shadow='[General]\nbypass-system = true\nskip-proxy = localhost, *.local, '+ip+'\nipv6 = false\ndns-server = system\n\n[Rule]\nIP-CIDR,'+ip+'/32,DIRECT,no-resolve\nIP-CIDR,127.0.0.0/8,DIRECT,no-resolve\nIP-CIDR,10.0.0.0/8,DIRECT,no-resolve\nIP-CIDR,172.16.0.0/12,DIRECT,no-resolve\nIP-CIDR,192.168.0.0/16,DIRECT,no-resolve\nFINAL,PROXY\n'
    for name,data in [('server.json',json.dumps(server,indent=2)),('clash-verge.yaml',json.dumps(client,indent=2)),('shadowrocket-nodes.txt','\n'.join(nodes)+'\n'+info),('shadowrocket.conf',shadow),('ports.json',json.dumps(dict(zip(['SS/TCP','VMess/TCP','REALITY/TCP','HY2/UDP','HTTPS/TCP'],ports)),indent=2))]:
        f=p/name; f.write_text(data+'\n'); f.chmod(0o600)

if __name__=='__main__':
    if len(sys.argv)!=6: sys.exit('render.py IP DIRECTORY MIHOMO CERT KEY')
    generate(*sys.argv[1:])
