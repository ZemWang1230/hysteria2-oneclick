"""Test Xray REALITY against Mihomo over IPv4 and IPv6 on localhost.

Set XRAY_BIN and MIHOMO_BIN. Test-only freedom rule permits loopback.
"""
import contextlib, http.server, json, os, pathlib, socket, ssl, subprocess, tempfile, threading, time, unittest, uuid

XRAY=os.environ.get('XRAY_BIN'); MIHOMO=os.environ.get('MIHOMO_BIN')
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200);self.end_headers();self.wfile.write(b'reality-dual-pass')
 def log_message(self,*args): pass
@unittest.skipUnless(XRAY and MIHOMO,'XRAY_BIN and MIHOMO_BIN required')
class TestXrayReality(unittest.TestCase):
 def test_dual_stack(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);cert=p/'cert.pem';key=p/'key.pem'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=www.microsoft.com','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key);ctx.set_alpn_protocols(['h2']);ctx.minimum_version=ssl.TLSVersion.TLSv1_3
   target=socket.socket();target.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);target.bind(('127.0.0.1',0));target.listen();target.settimeout(.3)
   stop=threading.Event()
   def accept():
    while not stop.is_set():
     try: c,_=target.accept()
     except socket.timeout: continue
     except OSError: break
     def handle(conn):
      try:
       tls=ctx.wrap_socket(conn,server_side=True);tls.sendall(b'\0\0\0\x04\0\0\0\0\0');tls.settimeout(5);tls.recv(65536)
      except (OSError,ssl.SSLError): pass
      finally: conn.close()
     threading.Thread(target=handle,args=(c,),daemon=True).start()
   threading.Thread(target=accept,daemon=True).start()
   web=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=web.serve_forever,daemon=True).start()
   with contextlib.closing(socket.socket(socket.AF_INET6)) as s: s.bind(('::',0));rp=s.getsockname()[1]
   keys=dict(l.split(': ',1) for l in subprocess.check_output([XRAY,'x25519'],text=True).splitlines() if ': ' in l)
   uid=str(uuid.uuid4());name='www.microsoft.com';short='0123456789abcdef'
   cfg={'log':{'loglevel':'warning'},'inbounds':[{'port':rp,'listen':'::','protocol':'vless','settings':{'clients':[{'id':uid,'flow':'xtls-rprx-vision'}],'decryption':'none'},'streamSettings':{'network':'tcp','security':'reality','realitySettings':{'dest':'127.0.0.1:'+str(target.getsockname()[1]),'serverNames':[name],'privateKey':keys['PrivateKey'],'minClientVer':'1.8.2','shortIds':[short]}}}],'outbounds':[{'protocol':'freedom','settings':{'finalRules':[{'action':'allow','ip':['127.0.0.1/32']}]}}]}
   (p/'xray.json').write_text(json.dumps(cfg));server=subprocess.Popen([XRAY,'run','-config',str(p/'xray.json')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    time.sleep(1);self.assertIsNone(server.poll())
    for index,addr in enumerate(('127.0.0.1','::1')):
     with contextlib.closing(socket.socket()) as s:s.bind(('127.0.0.1',0));cp=s.getsockname()[1]
     node={'name':'R','type':'vless','server':addr,'port':rp,'uuid':uid,'network':'tcp','tls':True,'flow':'xtls-rprx-vision','servername':name,'client-fingerprint':'chrome','reality-opts':{'public-key':keys['Password (PublicKey)'],'short-id':short}}
     conf={'mixed-port':cp,'mode':'rule','log-level':'warning','proxies':[node],'rules':['MATCH,R']};home=p/str(index);home.mkdir();(home/'client.json').write_text(json.dumps(conf))
     client=subprocess.Popen([MIHOMO,'-d',str(home),'-f',str(home/'client.json')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     try:
      time.sleep(.8);r=subprocess.run(['curl','-fsS','--max-time','8','--noproxy','','-x','http://127.0.0.1:'+str(cp),'http://127.0.0.1:'+str(web.server_port)],capture_output=True,text=True)
      self.assertEqual((r.returncode,r.stdout),(0,'reality-dual-pass'),(addr,r.stderr))
     finally: client.terminate();client.wait(timeout=5)
   finally:
    server.terminate();server.wait(timeout=5);stop.set();target.close();web.shutdown();web.server_close()
if __name__=='__main__': unittest.main()
