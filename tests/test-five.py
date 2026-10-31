#!/usr/bin/env python3
"""Offline five-protocol loopback test; requires Mihomo 1.19.33, curl, OpenSSL."""
import contextlib, hashlib, http.server, importlib.util, json, pathlib, socket, ssl, subprocess, sys, tempfile, threading, time

binary=str(pathlib.Path(sys.argv[1]).resolve())
renderer=pathlib.Path(__file__).resolve().parents[1]/'render.py'
spec=importlib.util.spec_from_file_location('renderer',renderer); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'five-protocol-pass')
 def log_message(self,*args): pass
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp); cert=p/'cert.pem'; key=p/'key.pem'; out=p/'out'
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 mod.generate('127.0.0.1',str(out),binary,str(cert),str(key))
 server=json.loads((out/'server.json').read_text()); client=json.loads((out/'clash-verge.yaml').read_text())
 assert len(server['listeners'])==len(client['proxies'])==5
 assert [x['port'] for x in server['listeners']]==[x['port'] for x in client['proxies']]
 assert len(set(x['port'] for x in server['listeners']))==5
 for node in client['proxies']: assert not node.get('skip-cert-verify',False)
 for f in ('server.json','clash-verge.yaml'):
  subprocess.run([binary,'-t','-f',str(out/f),'-d',str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
 http=http.server.HTTPServer(('127.0.0.1',0),Handler); threading.Thread(target=http.serve_forever,daemon=True).start()
 with contextlib.closing(socket.socket()) as sock: sock.bind(('127.0.0.1',0)); targetport=sock.getsockname()[1]
 target=subprocess.Popen(['openssl','s_server','-quiet','-accept',str(targetport),'-cert',str(cert),'-key',str(key),'-alpn','h2','-tls1_3'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 # Local test deliberately permits local HTTP destination; production rejects private IPs.
 server['mode']='direct'; server['log-level']='warning'
 for inbound in server['listeners']:
  if 'certificate' in inbound: inbound['certificate']=cert.read_text(); inbound['private-key']=key.read_text()
  if inbound['name']=='reality': inbound['reality-config']['dest']='127.0.0.1:'+str(targetport)
 (out/'test-server.json').write_text(json.dumps(server))
 proc=subprocess.Popen([binary,'-f',str(out/'test-server.json'),'-d',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  time.sleep(1.5)
  assert proc.poll() is None
  for node in client['proxies']:
   if (node.get('tls') and node['name']!='REALITY') or node['type']=='hysteria2': node['fingerprint']=fingerprint
   with contextlib.closing(socket.socket()) as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
   conf={'mixed-port':port,'allow-lan':False,'mode':'rule','log-level':'warning','proxies':[node],'rules':['MATCH,'+node['name']]}
   home=p/('client-'+node['name']); home.mkdir(); f=home/'config.json'; f.write_text(json.dumps(conf))
   c=subprocess.Popen([binary,'-f',str(f),'-d',str(home)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    time.sleep(1)
    r=subprocess.run(['curl','-fsS','--max-time','10','--noproxy','','-x','http://127.0.0.1:'+str(port),'http://127.0.0.1:'+str(http.server_port)+'/'],capture_output=True,text=True)
    assert r.returncode==0 and r.stdout=='five-protocol-pass', (node['name'],r.stderr)
    print('PASS',node['name'])
   finally: c.terminate(); c.wait(timeout=5)
   if node['name'] in ('SS','HTTPS','HY2'):
    bad=dict(node)
    if node['name']=='HY2': bad['fingerprint']='00'*32
    else: bad['password']='incorrect-password'
    conf['proxies']=[bad]; f.write_text(json.dumps(conf))
    c=subprocess.Popen([binary,'-f',str(f),'-d',str(home)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
     time.sleep(1)
     r=subprocess.run(['curl','-fsS','--max-time','5','--noproxy','','-x','http://127.0.0.1:'+str(port),'http://127.0.0.1:'+str(http.server_port)+'/'],capture_output=True,text=True)
     assert r.returncode != 0, 'wrong credentials/certificate accepted: '+node['name']
     print('PASS rejection',node['name'])
    finally: c.terminate(); c.wait(timeout=5)

  # Exercise production routing for literal and DNS-resolved local destinations.
  proc.terminate(); proc.wait(timeout=5)
  server['mode']='rule'
  (out/'test-server.json').write_text(json.dumps(server))
  proc=subprocess.Popen([binary,'-f',str(out/'test-server.json'),'-d',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  time.sleep(1.5)
  node=client['proxies'][0]
  with contextlib.closing(socket.socket()) as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
  conf={'mixed-port':port,'mode':'rule','log-level':'warning','proxies':[node],'rules':['MATCH,'+node['name']]}
  home=p/'private-test'; home.mkdir(); f=home/'config.json'; f.write_text(json.dumps(conf))
  c=subprocess.Popen([binary,'-f',str(f),'-d',str(home)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   time.sleep(1)
   for host in ('127.0.0.1','localhost'):
    r=subprocess.run(['curl','-fsS','--max-time','5','--noproxy','','-x','http://127.0.0.1:'+str(port),'http://'+host+':'+str(http.server_port)+'/'],capture_output=True,text=True)
    assert r.returncode != 0, 'private destination unexpectedly reachable: '+host
   print('PASS private IPv4 literal and localhost rejection')
  finally: c.terminate(); c.wait(timeout=5)
 finally:
  proc.terminate(); proc.wait(timeout=5); target.terminate(); target.wait(timeout=5); http.shutdown()
