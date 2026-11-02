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
if __name__=='__main__':unittest.main()
