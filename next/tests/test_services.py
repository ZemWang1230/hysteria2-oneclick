import json,sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import services
P={'prefix':'/tmp/proxy-next','certificate':'/tmp/proxy-next/fullchain.pem','private_key':'/tmp/proxy-next/privkey.pem','hy2_cert':'/tmp/proxy-next/hy2.crt','hy2_key':'/tmp/proxy-next/hy2.key'}
S={'addresses':['8.8.8.8','2001:4860:4860::8888'],'ports':dict(ss=20001,vmess=20002,reality=20003,hy2=20004,https=20005,subscription=20006,v2ray_local=20007),'credentials':dict(ss_password='sspass',vmess_uuid='a',reality_uuid='b',reality_sni='www.example.com',reality_private_key='priv',reality_short_id='abcd',hy2_password='hypw',https_username='proxy',https_password='pw',ws_path='/abc',subscription_token='abcd1234')}
class TestServices(unittest.TestCase):
 def test_stack(self):
  f=services.render(S,P);self.assertFalse(json.loads(f['ss.json'])['ipv6_only']);self.assertEqual(json.loads(f['v2ray.json'])['inbounds'][0]['listen'],'127.0.0.1');self.assertIn('listen [::]:20002 ssl ipv6only=on',f['nginx.conf']);self.assertIn('listen 0.0.0.0:20002 ssl',f['nginx.conf']);self.assertIn('access_log off;',f['nginx.conf']);self.assertIn('basic_auth proxy pw',f['Caddyfile']);self.assertEqual(json.loads(f['hysteria.json'])['listen'],':20004')
 def test_ipv4_only(self):
  f=services.render(dict(S,addresses=['8.8.8.8']),P);self.assertEqual(json.loads(f['ss.json'])['server'],'0.0.0.0');self.assertNotIn('listen [::]',f['nginx.conf'])
 def test_ipv6_only(self):
  f=services.render(dict(S,addresses=['2001:4860:4860::8888']),P);self.assertTrue(json.loads(f['ss.json'])['ipv6_only']);self.assertNotIn('listen 0.0.0.0:',f['nginx.conf'])
if __name__=='__main__': unittest.main()
