import importlib,sys,types,tempfile,unittest,io,hashlib
from pathlib import Path
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
from zipfile import ZipFile
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
d=importlib.import_module('tvpVod.diagnostics');u=importlib.import_module('tvpVod.updates')

class SupportTests(unittest.TestCase):
 def test_secrets_urls_paths_and_email_redacted(self):
  text='Shaka 1001 HTTP 403 https://cdn.example/video?token=secret\nAuthorization: Bearer verysecret\npassword=hunter2\nCookie: session=private\nC:\\Users\\Mirek\\file.dat\nme@example.com'
  result=d.sanitize(text)
  for private in ('secret','hunter2','private','Mirek','example.com'):self.assertNotIn(private,result)
  self.assertIn('1001 HTTP 403',result)
 def test_report_does_not_read_account_files(self):
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'tvpVod-account.dat').write_text('private-account-secret')
   d.record('TVP VOD','HTTP 403 https://example.com/token',folder)
   report=d.report(folder,'TVP VOD')
   self.assertIn('HTTP 403',report);self.assertNotIn('private-account-secret',report);self.assertNotIn('example.com',report)
 def test_email_contains_diagnostic_attachment(self):
  message=BytesParser(policy=policy.default).parsebytes(d.mail_draft('Nie działa TVP','Błąd 1001'))
  self.assertEqual(message['To'],d.CONTACT);self.assertEqual(message['X-Unsent'],'1')
  files=list(message.iter_attachments());self.assertEqual(len(files),1)
  self.assertIn('Błąd 1001',files[0].get_payload(decode=True).decode())
 def test_log_is_bounded(self):
  with tempfile.TemporaryDirectory() as folder:
   for _ in range(80):d.record('test','x '*1000,folder)
   self.assertLessEqual(len(Path(folder,'tvPlayer-diagnostics.log').read_text()),64000)

class UpdateTests(unittest.TestCase):
 def test_download_digest_and_manifest_verified_before_publish(self):
  blob=io.BytesIO()
  with ZipFile(blob,'w') as z:z.writestr('manifest.ini','name = tvpVod\nversion = 0.31.0-dev\n')
  payload=blob.getvalue()
  class Response(io.BytesIO):url='https://release-assets.githubusercontent.com/asset'
  release=self.release('0.31.0-dev');asset=u.choose_release([release],'0.30.0-dev')
  asset.update(size=len(payload),digest='sha256:'+hashlib.sha256(payload).hexdigest())
  with tempfile.TemporaryDirectory() as folder:
   with patch.object(u.urllib.request,'urlopen',return_value=Response(payload)):
    path=u.download(asset,folder);self.assertEqual(path.read_bytes(),payload)
   asset['digest']='sha256:wrong'
   with patch.object(u.urllib.request,'urlopen',return_value=Response(payload)):
    with self.assertRaisesRegex(ValueError,'kontrolna'):u.download(asset,folder)
   self.assertEqual(path.read_bytes(),payload);self.assertFalse(list(path.parent.glob('*.part')))
 def release(self,version):
  return {'tag_name':'v'+version,'html_url':u.RELEASES+'/tag/v'+version,'assets':[{'name':'tvplayer-'+version+'.nvda-addon','size':20000,'browser_download_url':u.RELEASES+'/download/v'+version+'/tvplayer.nvda-addon'}]}
 def test_numeric_versions_and_no_downgrade(self):
  self.assertGreater(u.version_key('0.30.0-dev'),u.version_key('0.9.9-dev'))
  self.assertIsNone(u.choose_release([self.release('0.28.7-dev')],'0.30.0-dev'))
  self.assertEqual(u.choose_release([self.release('0.31.0-dev'),self.release('0.32.0-dev')],'0.30.0-dev')['version'],'v0.32.0-dev')
 def test_wrong_repo_draft_and_asset_paths_rejected(self):
  r=self.release('0.31.0-dev');r['draft']=True;self.assertIsNone(u.choose_release([r],'0.30.0-dev'))
  r=self.release('0.31.0-dev');r['assets'][0]['browser_download_url']='https://example.com/file.nvda-addon'
  self.assertIsNone(u.choose_release([r],'0.30.0-dev'))
  self.assertFalse(u.asset_url('https://github.com/Guliwer777/tv-player/releases/download/../file'))
 def test_no_download_outside_trusted_repository(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(u.urllib.request,'urlopen') as network:
   with self.assertRaises(ValueError):u.download({'url':'https://example.com/x','name':'x.nvda-addon'},folder)
   network.assert_not_called()

if __name__=='__main__':unittest.main()
