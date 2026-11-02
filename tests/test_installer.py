import hashlib,pathlib,re,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import deploy
ROOT=pathlib.Path(__file__).resolve().parents[1]
class InstallerTest(unittest.TestCase):
 def test_downloaded_sources_match_bootstrap(self):
  script=(ROOT/'install.sh').read_text()
  for name in ('deploy.py','state.py','services.py','clients.py','hy2.py'):
   match=re.search(r'^([0-9a-f]{64}) '+re.escape(name)+r'$',script,re.M)
   self.assertIsNotNone(match);self.assertEqual(match.group(1),hashlib.sha256((ROOT/name).read_bytes()).hexdigest())
 def test_service_user(self):
  unit=deploy.unit('test','/opt/test')
  self.assertIn('User=dualproxy\n',unit);self.assertIn('NoNewPrivileges=true',unit)

class RenewalTest(unittest.TestCase):
 def test_unchanged_changed_and_retry(self):
  import os, subprocess, tempfile
  with tempfile.TemporaryDirectory() as root:
   p=pathlib.Path(root); cert=p/'cert'; etc=p/'etc'; binaries=p/'bin'
   for d in (cert,etc,binaries):d.mkdir()
   for name,value in [('fullchain.pem','old certificate'),('privkey.pem','old key')]:
    (cert/name).write_text(value);(etc/name).write_text(value)
   marker=etc/'applied-cert.sha256';marker.write_text(hashlib.sha256((cert/'fullchain.pem').read_bytes()).hexdigest()+'\n')
   log=p/'calls'; fail=p/'fail'
   def executable(name,body):
    f=binaries/name;f.write_text('#!/bin/sh\nset -eu\n'+body+'\n');f.chmod(0o755);return f
   executable('install','shift 6\ncp "$1" "$2"')
   executable('systemctl',f'echo "$*" >> "{log}"\n[ "$1" != restart ] || [ ! -f "{fail}" ]')
   executable('caddy','exit 0');nginx=executable('nginx','exit 0')
   script=p/'renew';script.write_text(deploy.renewal_script(str(cert)+'/',etc,binaries,nginx));script.chmod(0o700)
   env=dict(os.environ,PATH=str(binaries)+':'+os.environ['PATH'])
   subprocess.run([script],env=env,check=True);self.assertFalse(log.exists())
   (cert/'fullchain.pem').write_text('new certificate');(cert/'privkey.pem').write_text('new key')
   fail.touch();self.assertNotEqual(subprocess.run([script],env=env).returncode,0)
   self.assertNotEqual(marker.read_text().strip(),hashlib.sha256((cert/'fullchain.pem').read_bytes()).hexdigest())
   fail.unlink();subprocess.run([script],env=env,check=True)
   calls=log.read_text().splitlines();self.assertEqual(calls,['reload dual-proxy-nginx','restart dual-proxy-https','reload dual-proxy-nginx','restart dual-proxy-https'])
   subprocess.run([script],env=env,check=True);self.assertEqual(log.read_text().splitlines(),calls)

if __name__=='__main__':unittest.main()
