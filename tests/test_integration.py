"""Dual-stack reference components; executable paths supplied via environment.

Nginx runs single-process with the current user in this isolated test only.
"""
import contextlib,hashlib,http.server,json,os,pathlib,socket,ssl,subprocess,sys,tempfile,threading,time,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import clients,services,state
ENV=['SS_BIN','V2RAY_BIN','XRAY_BIN','HY2_BIN','CADDY_BIN','NGINX_BIN','MIHOMO_BIN']
def freeport():
 with contextlib.closing(socket.socket()) as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'dual-stack-five-pass')
 def log_message(self,*a):pass
@unittest.skipUnless(all(os.environ.get(k) for k in ENV),'binary environment incomplete')
class TestIntegration(unittest.TestCase):
 def test_services(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);cert=p/'cert.pem';key=p/'key.pem';procs=[]
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,IP:::1','-keyout',str(key),'-out',str(cert)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
   fp=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
   config=state.make(['8.8.8.8','2001:4860:4860::8888'],os.environ['XRAY_BIN']);config['addresses']=['127.0.0.1','::1']; files=clients.build(config)
   paths={'prefix':str(p),'certificate':str(cert),'private_key':str(key),'hy2_cert':str(cert),'hy2_key':str(key)}
   files.update(services.render(config,paths))
   for name,content in files.items(): (p/name).write_text(content)
   # Allow the local-only test destination; production keeps Caddy's default ACL.
   caddy=(p/'Caddyfile').read_text().replace('  forward_proxy {','  forward_proxy {\n   acl {\n    allow 127.0.0.1/32\n   }'); (p/'Caddyfile').write_text(caddy)
   for name in ('client','proxy','fastcgi','uwsgi','scgi'): (p/'tmp'/name).mkdir(parents=True)
   # This sandbox disallows setuid/chown. Production uses nginx master and www-data workers.
   nginx=(p/'nginx.conf').read_text().replace('user www-data;','user root;\nmaster_process off;\ndaemon off;');(p/'nginx.conf').write_text(nginx)
   ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key);ctx.set_alpn_protocols(['h2']);ctx.minimum_version=ssl.TLSVersion.TLSv1_3
   fallback=socket.socket();fallback.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);fallback.bind(('127.0.0.1',0));fallback.listen();fallback.settimeout(.3);stop=threading.Event()
   def serve_fallback():
    while not stop.is_set():
     try: c,_=fallback.accept()
     except socket.timeout: continue
     except OSError: break
     def handle(conn):
      try:
       t=ctx.wrap_socket(conn,server_side=True);t.sendall(b'\0\0\0\x04\0\0\0\0\0');t.settimeout(5);t.recv(65536)
      except (OSError,ssl.SSLError):pass
      finally:conn.close()
     threading.Thread(target=handle,args=(c,),daemon=True).start()
   threading.Thread(target=serve_fallback,daemon=True).start()
   xray=json.loads((p/'xray.json').read_text());xray['inbounds'][0]['streamSettings']['realitySettings']['dest']='127.0.0.1:'+str(fallback.getsockname()[1]);xray['outbounds'][0]['settings']={'finalRules':[{'action':'allow','ip':['127.0.0.1/32']}]};(p/'xray.json').write_text(json.dumps(xray))
   web=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=web.serve_forever,daemon=True).start()
   commands=[[os.environ['SS_BIN'],'-c',str(p/'ss.json')],[os.environ['V2RAY_BIN'],'run','-c',str(p/'v2ray.json')],[os.environ['XRAY_BIN'],'run','-config',str(p/'xray.json')],[os.environ['HY2_BIN'],'server','--disable-update-check','-c',str(p/'hysteria.json')],[os.environ['CADDY_BIN'],'run','--config',str(p/'Caddyfile')],[os.environ['NGINX_BIN'],'-c',str(p/'nginx.conf'),'-p',str(p)]]
   try:
    for i,cmd in enumerate(commands):
     log=(p/('service'+str(i)+'.log')).open('w');procs.append((subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT),log))
    time.sleep(2)
    for i,(proc,log) in enumerate(procs):
     log.flush();self.assertIsNone(proc.poll(),(i,(p/('service'+str(i)+'.log')).read_text()[-2000:]))
    for i,node in enumerate(json.loads(files['clash-verge.yaml'])['proxies']):
     if node['type'] in ('vmess','http'):node['fingerprint']=fp
     cp=freeport();home=p/('client'+str(i));home.mkdir();conf={'mixed-port':cp,'mode':'rule','log-level':'warning','ipv6':True,'proxies':[node],'rules':['MATCH,'+node['name']]};(home/'config.json').write_text(json.dumps(conf))
     clientlog=(home/'client.log').open('w');client=subprocess.Popen([os.environ['MIHOMO_BIN'],'-d',str(home),'-f',str(home/'config.json')],stdout=clientlog,stderr=subprocess.STDOUT)
     try:
      time.sleep(.7);r=subprocess.run(['curl','-fsS','--noproxy','','--max-time','9','-x','http://127.0.0.1:'+str(cp),'http://127.0.0.1:'+str(web.server_port)],capture_output=True,text=True)
      clientlog.flush(); self.assertEqual((r.returncode,r.stdout),(0,'dual-stack-five-pass'),(node['name'],r.stderr,(home/'client.log').read_text()[-1500:],(p/'service4.log').read_text()[-1000:]))
     finally:client.terminate();client.wait(timeout=5);clientlog.close()
    token=config['credentials']['subscription_token'];sport=config['ports']['subscription']
    for ip in ('127.0.0.1','[::1]'):
     base='https://'+ip+':'+str(sport)+'/'
     ok=subprocess.run(['curl','-fsS','--noproxy','*','--cacert',str(cert),base+token+'/clash'],capture_output=True,text=True,timeout=8)
     self.assertEqual(ok.returncode,0,(ip,ok.stderr));self.assertEqual(len(json.loads(ok.stdout)['proxies']),10)
     bad=subprocess.run(['curl','-sS','--noproxy','*','--cacert',str(cert),'-o','/dev/null','-w','%{http_code}',base+'wrong/clash'],capture_output=True,text=True,timeout=8)
     self.assertEqual(bad.stdout,'404')
   finally:
    for proc,log in reversed(procs):
     if proc.poll() is None:proc.terminate()
     proc.wait(timeout=5);log.close()
    stop.set();fallback.close();web.shutdown();web.server_close()
if __name__=='__main__':unittest.main()
