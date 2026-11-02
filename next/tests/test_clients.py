import base64,json,sys,pathlib,unittest
from urllib.parse import urlsplit
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import clients
STATE={'addresses':['8.8.8.8','2001:4860:4860::8888'],'ports':dict(ss=21001,vmess=21002,reality=21003,hy2=21004,https=21005),'credentials':dict(ss_password='ss-password',vmess_uuid='c8e931ed-7f46-4dae-bffc-d2483dfaaa11',reality_uuid='c8e931ed-7f46-4dae-bffc-d2483dfaaa22',reality_sni='www.example.com',reality_public_key='test-pub',reality_short_id='deadbeef',hy2_password='hy-password',https_username='proxy',https_password='ht-password',ws_path='/test')}
class TestClients(unittest.TestCase):
 def test_dual_stack(self):
  out=clients.build(STATE);clash=json.loads(out['clash-verge.yaml']);self.assertEqual(len(clash['proxies']),10);self.assertTrue(clash['ipv6']); self.assertEqual(len(clash['proxy-groups'][0]['proxies']),10)
  links=out['shadowrocket-nodes.txt'].splitlines();self.assertEqual(len(links),8)
  self.assertEqual(base64.b64decode(out['shadowrocket-subscription.txt']).decode().splitlines(),links)
  self.assertEqual(urlsplit(links[4]).hostname,'2001:4860:4860::8888');self.assertEqual(urlsplit(links[7]).hostname,'2001:4860:4860::8888')
  self.assertEqual(len(json.loads(out['shadowrocket-https-manual.json'])),2)
 def test_invalid(self):
  for addresses in ([],['8.8.8.8','8.8.4.4'],['bad']):
   with self.assertRaises(ValueError):clients.build(dict(STATE,addresses=addresses))
if __name__=='__main__':unittest.main()
