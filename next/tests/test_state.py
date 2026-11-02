import ipaddress,os,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import state
class TestState(unittest.TestCase):
 def test_ports(self):
  for a in [['8.8.8.8'],['2001:4860:4860::8888'],['8.8.8.8','2001:4860:4860::8888']]:
   try:p=state.allocate(a)
   except OSError as e:self.skipTest('IPv6 unavailable: '+str(e))
   self.assertEqual(len(set(p)),7);self.assertTrue(all(20000<=x<=29999 for x in p))
 def test_validation(self):
  for a in ([],['127.0.0.1'],['8.8.8.8','8.8.4.4']):
   with self.assertRaises(ValueError):state.make(a,'/unused')
if __name__=='__main__':unittest.main()
