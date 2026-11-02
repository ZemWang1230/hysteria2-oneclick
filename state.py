"""Generate deployment state and assign collision-checked TCP/UDP ports."""
import ipaddress,json,pathlib,secrets,socket,subprocess,sys,uuid
import clients,services

def allocate(addresses):
    sockets=[];ports=[]
    try:
        for _ in range(2000):
            if len(ports)==7: return ports
            port=20000+secrets.randbelow(10000)
            if port in ports: continue
            trial=[]
            try:
                for family in sorted({4} | {ipaddress.ip_address(a).version for a in addresses}):
                    for typ in (socket.SOCK_STREAM,socket.SOCK_DGRAM):
                        s=socket.socket(socket.AF_INET if family==4 else socket.AF_INET6,typ);trial.append(s)
                        if family==6:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
                        s.bind(('0.0.0.0' if family==4 else '::',port))
            except OSError:
                for s in trial:s.close()
                continue
            sockets.extend(trial);ports.append(port)
        raise RuntimeError('unable to find seven available dual-stack TCP and UDP ports')
    finally:
        for s in sockets:s.close()

def make(addresses,xray):
    addrs=[str(ipaddress.ip_address(a)) for a in addresses]
    if not 1<=len(addrs)<=2 or len({ipaddress.ip_address(a).version for a in addrs})!=len(addrs): raise ValueError('one IPv4 and/or one IPv6 required')
    if not all(ipaddress.ip_address(a).is_global for a in addrs): raise ValueError('public IP addresses required')
    keys=dict(line.split(':',1) for line in subprocess.check_output([xray,'x25519'],text=True).splitlines() if ':' in line)
    ports=dict(zip(['ss','vmess','reality','hy2','https','subscription','v2ray_local'],allocate(addrs)))
    return {'addresses':addrs,'ports':ports,'credentials':{'ss_password':secrets.token_hex(24),'vmess_uuid':str(uuid.uuid4()),'ws_path':'/'+secrets.token_hex(12),'reality_uuid':str(uuid.uuid4()),'reality_private_key':keys['PrivateKey'].strip(),'reality_public_key':keys['Password (PublicKey)'].strip(),'reality_short_id':secrets.token_hex(8),'reality_sni':'www.microsoft.com','hy2_password':secrets.token_hex(24),'https_username':'proxy','https_password':secrets.token_hex(24),'subscription_token':secrets.token_hex(32)}}

def write_artifacts(state,directory,prefix):
    p=pathlib.Path(directory);p.mkdir(mode=0o700,parents=True,exist_ok=True)
    path={'prefix':prefix,'certificate':prefix+'/fullchain.pem','private_key':prefix+'/privkey.pem','hy2_cert':prefix+'/hy2.crt','hy2_key':prefix+'/hy2.key'}
    files=services.render(state,path);files.update(clients.build(state));files['state.json']=json.dumps(state,indent=2)+'\n'
    for name,body in files.items():
        file=p/name;file.write_text(body);file.chmod(0o600)

if __name__=='__main__':
    if len(sys.argv)<5:sys.exit('usage: state.py XRAY OUTPUT PREFIX IP [IP]')
    state=make(sys.argv[4:],sys.argv[1]);write_artifacts(state,sys.argv[2],sys.argv[3])
