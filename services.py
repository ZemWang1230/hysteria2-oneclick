"""Render reference-compatible server configurations; no side effects."""
import json
import hy2

def render(state, paths):
    addrs=state['addresses']; kinds={':' in x for x in addrs}
    if not 1 <= len(addrs) <= 2 or len(kinds)!=len(addrs): raise ValueError('one IPv4 and/or IPv6 required')
    v4=False in kinds;v6=True in kinds
    listen='::' if v6 else '0.0.0.0'
    port=state['ports'];cred=state['credentials'];cert=paths['certificate'];key=paths['private_key']
    ss={'server':listen,'server_port':port['ss'],'password':cred['ss_password'],'method':'aes-128-gcm','mode':'tcp_and_udp','ipv6_only':not v4}
    vm={'log':{'loglevel':'warning'},'inbounds':[{'listen':'127.0.0.1','port':port['v2ray_local'],'protocol':'vmess','settings':{'clients':[{'id':cred['vmess_uuid'],'alterId':0}]},'streamSettings':{'network':'ws','wsSettings':{'path':cred['ws_path']}}}],'outbounds':[{'protocol':'freedom'}]}
    reality={'log':{'loglevel':'warning'},'inbounds':[{'listen':listen,'port':port['reality'],'protocol':'vless','settings':{'clients':[{'id':cred['reality_uuid'],'flow':'xtls-rprx-vision'}],'decryption':'none'},'streamSettings':{'network':'tcp','security':'reality','realitySettings':{'dest':cred['reality_sni']+':443','serverNames':[cred['reality_sni']],'privateKey':cred['reality_private_key'],'minClientVer':'1.8.2','shortIds':[cred['reality_short_id']]}}}],'outbounds':[{'protocol':'freedom'}]}
    hysteria=hy2.server_config(port['hy2'],cred['hy2_password'],paths['hy2_cert'],paths['hy2_key'])
    # Nginx: no existing global config touched. Access logging is disabled so
    # the unguessable subscription bearer token never reaches access logs.
    bind=lambda n: ('listen 0.0.0.0:'+str(n)+' ssl;\n' if v4 else '')+('listen [::]:'+str(n)+' ssl ipv6only=on;\n' if v6 else '')
    token=cred['subscription_token']
    if not token.isalnum() or not cred['ws_path'].startswith('/') or not cred['ws_path'][1:].isalnum(): raise ValueError('unsafe token or path')
    nginx='''user www-data;
pid %(pid)s;
worker_processes 1;
error_log stderr warn;
events { worker_connections 1024; }
http {
 client_body_temp_path %(temp)s/client;
 proxy_temp_path %(temp)s/proxy;
 fastcgi_temp_path %(temp)s/fastcgi;
 uwsgi_temp_path %(temp)s/uwsgi;
 scgi_temp_path %(temp)s/scgi;
 access_log off;
 server {
  %(vm_bind)s
  ssl_certificate %(cert)s;
  ssl_certificate_key %(key)s;
  ssl_protocols TLSv1.2 TLSv1.3;
  location = %(path)s {
   proxy_pass http://127.0.0.1:%(local)s;
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   proxy_set_header Host $host;
  }
  location / { return 404; }
 }
 server {
  %(sub_bind)s
  ssl_certificate %(cert)s;
  ssl_certificate_key %(key)s;
  ssl_protocols TLSv1.2 TLSv1.3;
  add_header Cache-Control "no-store" always;
  location = /%(token)s/clash { alias %(prefix)s/clash-verge.yaml; default_type text/plain; }
  location = /%(token)s/shadowrocket { alias %(prefix)s/shadowrocket-subscription.txt; default_type text/plain; }
  location = /%(token)s/shadowrocket.conf { alias %(prefix)s/shadowrocket.conf; default_type text/plain; }
  location / { return 404; }
 }
}
'''%{'prefix':paths['prefix'],'temp':paths.get('nginx_temp',paths['prefix']+'/tmp'),'pid':paths.get('nginx_pid',paths['prefix']+'/nginx.pid'),'vm_bind':bind(port['vmess']),'sub_bind':bind(port['subscription']),'cert':cert,'key':key,'path':cred['ws_path'],'local':port['v2ray_local'],'token':token}
    # Reference project's Caddy build includes the forward_proxy module.
    caddy='''{
 admin off
 auto_https off
}
:%(port)s {
 tls %(cert)s %(key)s
 route {
  forward_proxy {
   basic_auth %(user)s %(password)s
   hide_ip
   hide_via
  }
  respond "Not found" 404
 }
}
'''%{'port':port['https'],'cert':cert,'key':key,'user':cred['https_username'],'password':cred['https_password']}
    return {'ss.json':json.dumps(ss,indent=2)+'\n','v2ray.json':json.dumps(vm,indent=2)+'\n','xray.json':json.dumps(reality,indent=2)+'\n','hysteria.json':json.dumps(hysteria,indent=2)+'\n','nginx.conf':nginx,'Caddyfile':caddy}
