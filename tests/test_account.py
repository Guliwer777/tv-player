import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
account=importlib.import_module('tvpVod.tvp_account')

class AccountTests(unittest.TestCase):
    def test_windows_protection_roundtrip_and_host_bound_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'account.dat'
            record={'version':1,'token':'fake-test-token','profile':'test-profile','device':'test-device'}
            account.save(record,path)
            self.assertNotIn(b'fake-test-token',path.read_bytes())
            self.assertEqual(account.load(path),record)
            self.assertEqual(account.headers('https://vod.tvp.pl/api/products/123',path)['API-Authentication'],'fake-test-token')
            for url in ['https://sport.tvp.pl/api/','https://vod.tvp.pl.evil.example/api/','http://vod.tvp.pl/api/','https://vod.tvp.pl:444/api/','https://vod.tvp.pl/static/script.js','https://cdn.tvp.pl/film.m3u8']:
                self.assertEqual(account.headers(url,path),{})

    def test_pair_stores_session_and_no_password_or_code(self):
        response=io.BytesIO(json.dumps({'token':'fake-test-token','profiles':[{'uid':'test-profile'}]}).encode())
        requests=[]
        def open_request(request,**kwargs):
            requests.append(request);return response
        opener=types.SimpleNamespace(open=open_request)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'account.dat'
            with patch.object(account,'build_opener',return_value=opener):account.pair('TESTCODE','device',path)
            record=account.load(path)
            self.assertEqual(record,{'version':1,'token':'fake-test-token','profile':'test-profile','device':'device'})
            self.assertIn('platform=SMART_TV',requests[0].full_url)

    def test_error_reports_only_server_reason_without_pairing_code(self):
        error=HTTPError('https://vod.tvp.pl/api/?code=SECRETTESTCODE',401,'Unauthorized',{},io.BytesIO(b'{"code":"SSO_USER_NOT_AUTHORIZED"}'))
        opener=types.SimpleNamespace(open=lambda *args,**kwargs:(_ for _ in ()).throw(error))
        with patch.object(account,'build_opener',return_value=opener):
            with self.assertRaises(account.AccountError) as result:account.pair('SECRETTESTCODE','device')
        self.assertIn('SSO_USER_NOT_AUTHORIZED',str(result.exception))
        self.assertNotIn('SECRETTESTCODE',str(result.exception))

    def test_corrupt_session_fails_without_silently_using_anonymous_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'account.dat';path.write_bytes(b'not-encrypted')
            with self.assertRaises(account.AccountError):account.load(path)

    def test_invalid_code_and_auth_redirect_rejected(self):
        with patch.object(account,'build_opener') as opener:
            with self.assertRaises(account.AccountError):account.pair('bad&code','device')
            opener.assert_not_called()
        with self.assertRaises(account.AccountError):account.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example/')
