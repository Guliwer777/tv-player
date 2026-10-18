import sys,types,importlib,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
a=importlib.import_module('tvpVod.polsat_access')
c=importlib.import_module('tvpVod.catalog')
s=importlib.import_module('tvpVod.state')

class AccessTests(unittest.TestCase):
 def tearDown(self):a.clear()
 def test_status_aggregation_is_not_based_on_first_episode(self):
  self.assertEqual(a.aggregate(['no','yes']),'partial')
  self.assertEqual(a.aggregate(['no','no']),'no')
  self.assertEqual(a.aggregate(['yes','yes']),'yes')
  self.assertEqual(a.aggregate(['no','unknown']),'unknown')
  self.assertEqual(a.aggregate(['no'],False),'unknown')
  self.assertEqual(a.aggregate([]),'unknown')
 def test_series_checks_every_episode(self):
  client=Mock();client.record={'clientId':'client','profile':{'id':'profile'}}
  client.call.return_value={'results':[{'id':str(i),'mediaType':'vod'} for i in range(26)],'total':26}
  item=c.Folder(1,'Serial','POLSAT','seasons:123')
  with patch.object(a,'authenticated',return_value={'statusDescription':'no access'}) as rpc:
   self.assertEqual(a.assess(item,threading.Event(),client),'no');self.assertEqual(rpc.call_count,26)
   self.assertEqual(a.assess(item,threading.Event(),client),'no');self.assertEqual(rpc.call_count,26)
 def test_partial_and_rpc_errors(self):
  client=Mock();client.record={'clientId':'client','profile':{'id':'profile'}}
  client.call.return_value={'results':[{'id':'1','mediaType':'vod'},{'id':'2','mediaType':'vod'}],'total':2}
  def reply(record,namespace,method,fields):return {'statusDescription':'has access' if fields['product']['id']=='1' else 'no access'}
  with patch.object(a,'authenticated',side_effect=reply):self.assertEqual(a.assess(c.Folder(1,'Serial','POLSAT','seasons:1'),threading.Event(),client),'partial')
  a.clear()
  with patch.object(a,'authenticated',side_effect=a.PolsatError('Test')):self.assertEqual(a.assess(c.Folder(1,'Serial','POLSAT','seasons:1'),threading.Event(),client),'unknown')
 def test_cancelled_assessment_does_not_query_account(self):
  stop=threading.Event();stop.set()
  with patch.object(a,'Client') as client:
   self.assertEqual(a.assess(c.Folder(1,'Serial','POLSAT','seasons:1'),stop),'unknown');client.assert_not_called()
 def test_access_label_is_transient_and_old_state_remains_compatible(self):
  item=c.Folder(1,'Serial','POLSAT','seasons:1',access_status='brak dostępu')
  self.assertIn('brak dostępu',item.label);encoded=s.encode(item)
  self.assertNotIn('access_status',encoded['data']);self.assertEqual(s.decode(encoded).access_status,'')
  video=c.Material(2,'Film','','https://polsatboxgo.pl/wideo/x/2/ogladaj','POLSAT',False,access_status='brak dostępu')
  self.assertIn('brak dostępu',video.label)

 def test_incomplete_server_page_cannot_mark_whole_series_denied(self):
  client=Mock();client.record={'clientId':'client','profile':{'id':'profile'}}
  client.call.return_value={'results':[{'id':'1','mediaType':'vod'}],'total':26}
  with patch.object(a,'authenticated',return_value={'statusDescription':'no access'}):
   self.assertEqual(a.assess(c.Folder(1,'Serial','POLSAT','seasons:1'),threading.Event(),client),'unknown')

 def test_cancelled_queued_check_does_not_wait_for_previous_series(self):
  stop=threading.Event();done=threading.Event();result=[]
  a._work.acquire()
  def worker():result.append(a.assess(c.Folder(1,'Serial','POLSAT','seasons:1'),stop));done.set()
  thread=threading.Thread(target=worker,daemon=True)
  try:
   thread.start();stop.set();self.assertTrue(done.wait(.8));self.assertEqual(result,['unknown'])
  finally:a._work.release();thread.join(1)
