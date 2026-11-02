import importlib.util
import pathlib
import unittest
from urllib.parse import parse_qs, urlsplit, unquote
p=pathlib.Path(__file__).resolve().parents[1]/'hy2.py'
spec=importlib.util.spec_from_file_location('hy2',p); hy2=importlib.util.module_from_spec(spec); spec.loader.exec_module(hy2)
class TestHY2(unittest.TestCase):
 def test_config_and_links(self):
  cfg=hy2.server_config(22999,'test:password','/cert','/key')
  self.assertEqual(cfg['listen'],':22999')
  self.assertEqual(cfg['quic']['maxConnReceiveWindow'],67108864)
  self.assertEqual(cfg['masquerade']['proxy']['url'],'https://bing.com')
  for addr in ('8.8.8.8','2001:4860:4860::8888'):
   node=hy2.client_node(addr,22999,'test:password'); uri=urlsplit(hy2.client_uri(addr,22999,'test:password'))
   self.assertEqual(uri.hostname,addr); self.assertEqual(uri.port,22999)
   self.assertEqual(unquote(uri.username),node['password'])
   self.assertTrue(node['skip-cert-verify']); self.assertEqual(parse_qs(uri.query)['insecure'],['1'])
 def test_invalid_input(self):
  for p in (0,65536):
   with self.assertRaises(ValueError): hy2.server_config(p,'x','cert','key')
  with self.assertRaises(ValueError): hy2.client_uri('invalid',443,'x')
if __name__=='__main__': unittest.main()
