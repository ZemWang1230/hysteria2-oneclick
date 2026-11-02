"""Local dual-stack end-to-end HY2 check: set HYSTERIA_BIN to official binary."""
import contextlib, http.server, importlib.util, json, os, pathlib, socket, subprocess, tempfile, threading, time, unittest

binary=os.environ.get('HYSTERIA_BIN')
spec=importlib.util.spec_from_file_location('hy2',pathlib.Path(__file__).resolve().parents[1]/'hy2.py'); hy2=importlib.util.module_from_spec(spec);spec.loader.exec_module(hy2)
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200);self.end_headers();self.wfile.write(b'hy2-dual-pass')
 def log_message(self,*args): pass
@unittest.skipUnless(binary,'HYSTERIA_BIN not set')
class TestHysteria(unittest.TestCase):
 def test_dual_stack(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp); cert=p/'cert.pem'; key=p/'key.pem'
   subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-days','1','-subj','/CN=bing.com','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   with contextlib.closing(socket.socket(socket.AF_INET6,socket.SOCK_DGRAM)) as s: s.bind(('::',0)); port=s.getsockname()[1]
   (p/'server.json').write_text(json.dumps(hy2.server_config(port,'test-password',cert,key)))
   server=subprocess.Popen([binary,'server','--disable-update-check','-c',str(p/'server.json')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   web=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=web.serve_forever,daemon=True).start()
   try:
    time.sleep(1); self.assertIsNone(server.poll(),server.stdout.read().decode() if server.poll() is not None else '')
    for addr in ('127.0.0.1','::1'):
     with contextlib.closing(socket.socket()) as s: s.bind(('127.0.0.1',0)); local=s.getsockname()[1]
     remote='['+addr+']' if ':' in addr else addr
     client={'server':remote+':'+str(port),'auth':'test-password','tls':{'sni':'bing.com','insecure':True},'socks5':{'listen':'127.0.0.1:'+str(local)}}
     (p/'client.json').write_text(json.dumps(client)); process=subprocess.Popen([binary,'client','--disable-update-check','-c',str(p/'client.json')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     try:
      time.sleep(.7)
      r=subprocess.run(['curl','-fsS','--noproxy','','--proxy','socks5h://127.0.0.1:'+str(local),'--max-time','8','http://127.0.0.1:'+str(web.server_port)],capture_output=True,text=True)
      self.assertEqual((r.returncode,r.stdout),(0,'hy2-dual-pass'),(addr,r.stderr))
     finally: process.terminate();process.wait(timeout=5)
   finally:
    server.terminate();server.wait(timeout=5);server.stdout.close();web.shutdown();web.server_close()
if __name__=='__main__': unittest.main()
