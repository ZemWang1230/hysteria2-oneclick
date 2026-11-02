"""Generate dual-stack Clash and Shadowrocket client artifacts locally.

HTTPS node share links are intentionally omitted from Shadowrocket URI lists:
there is no verified interoperable URI syntax for the closed-source client.
Its connection details are included for manual entry instead.
"""
import base64, ipaddress, json
from urllib.parse import quote, urlencode
import hy2

def authority(ip, port):
    parsed=ipaddress.ip_address(ip)
    return ('['+str(parsed)+']' if parsed.version==6 else str(parsed))+':'+str(port)

def build(state):
    addresses=[str(ipaddress.ip_address(x)) for x in state['addresses']]
    if not addresses or len(addresses)!=len(set(addresses)) or len(addresses)>2:
        raise ValueError('expected one IPv4 and/or one IPv6 address')
    if len({ipaddress.ip_address(x).version for x in addresses}) != len(addresses):
        raise ValueError('at most one address per family')
    ports=state['ports']; secret=state['credentials']; names=[]; proxies=[]; links=[]; manuals=[]
    for ip in addresses:
        suffix='IPv'+str(ipaddress.ip_address(ip).version)
        ss='SS-'+suffix; vm='VMess-'+suffix; re='REALITY-'+suffix; hy='HY2-'+suffix; ht='HTTPS-'+suffix
        for key in ('ss','vmess','reality','hy2','https'):
            if not 1<=int(ports[key])<=65535: raise ValueError('invalid port')
        path=secret['ws_path']; host=secret['reality_sni']; u=secret['https_username']; pw=secret['https_password']
        proxies.extend([
            {'name':ss,'type':'ss','server':ip,'port':ports['ss'],'cipher':'aes-128-gcm','password':secret['ss_password'],'udp':True},
            {'name':vm,'type':'vmess','server':ip,'port':ports['vmess'],'uuid':secret['vmess_uuid'],'alterId':0,'cipher':'auto','network':'ws','tls':True,'servername':ip,'skip-cert-verify':False,'ws-opts':{'path':path}},
            {'name':re,'type':'vless','server':ip,'port':ports['reality'],'uuid':secret['reality_uuid'],'network':'tcp','tls':True,'flow':'xtls-rprx-vision','servername':host,'client-fingerprint':'chrome','reality-opts':{'public-key':secret['reality_public_key'],'short-id':secret['reality_short_id']}},
            hy2.client_node(ip,ports['hy2'],secret['hy2_password']),
            {'name':ht,'type':'http','server':ip,'port':ports['https'],'username':u,'password':pw,'tls':True,'sni':ip,'skip-cert-verify':False},
        ])
        names.extend([ss,vm,re,hy,ht])
        b64=lambda data:base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')
        vminfo={'v':'2','ps':vm,'add':ip,'port':str(ports['vmess']),'id':secret['vmess_uuid'],'aid':'0','scy':'auto','net':'ws','type':'none','host':ip,'path':path,'tls':'tls','sni':ip}
        q=urlencode({'encryption':'none','security':'reality','type':'tcp','sni':host,'fp':'chrome','pbk':secret['reality_public_key'],'sid':secret['reality_short_id'],'flow':'xtls-rprx-vision'})
        links.extend(['ss://'+b64('aes-128-gcm:'+secret['ss_password'])+'@'+authority(ip,ports['ss'])+'#'+ss,
                      'vmess://'+base64.b64encode(json.dumps(vminfo,separators=(',',':')).encode()).decode(),
                      'vless://'+quote(secret['reality_uuid'],safe='')+'@'+authority(ip,ports['reality'])+'?'+q+'#'+re,
                      hy2.client_uri(ip,ports['hy2'],secret['hy2_password'])])
        manuals.append({'name':ht,'address':ip,'port':ports['https'],'username':u,'password':pw,'tls':True,'verify_certificate':True})
    rules=['IP-CIDR,'+ip+'/32,DIRECT,no-resolve' if ipaddress.ip_address(ip).version==4 else 'IP-CIDR6,'+ip+'/128,DIRECT,no-resolve' for ip in addresses]
    rules+=['IP-CIDR,127.0.0.0/8,DIRECT,no-resolve','IP-CIDR,10.0.0.0/8,DIRECT,no-resolve','IP-CIDR,172.16.0.0/12,DIRECT,no-resolve','IP-CIDR,192.168.0.0/16,DIRECT,no-resolve','IP-CIDR6,::1/128,DIRECT,no-resolve','IP-CIDR6,fc00::/7,DIRECT,no-resolve','IP-CIDR6,fe80::/10,DIRECT,no-resolve','MATCH,PROXY']
    clash={'mixed-port':7890,'allow-lan':False,'mode':'rule','log-level':'warning','ipv6':True,'proxies':proxies,'proxy-groups':[{'name':'PROXY','type':'select','proxies':names}],'rules':rules}
    conf='[General]\nbypass-system = true\nipv6 = true\ndns-server = system\n\n[Rule]\n'+ '\n'.join(r.replace('MATCH,','FINAL,') for r in rules)+'\n'
    return {'clash-verge.yaml':json.dumps(clash,indent=2,ensure_ascii=False)+'\n',
            'shadowrocket-nodes.txt':'\n'.join(links)+'\n',
            'shadowrocket-subscription.txt':base64.b64encode(('\n'.join(links)+'\n').encode()).decode()+'\n',
            'shadowrocket.conf':conf,
            'shadowrocket-https-manual.json':json.dumps(manuals,indent=2,ensure_ascii=False)+'\n'}
