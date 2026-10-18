import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon/globalPlugins/tvpVod'))
import canal_account as account


class AccountTests(unittest.TestCase):
    def test_only_required_session_fields_saved_and_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'account.dat'
            with patch.object(account,'protect',side_effect=lambda value,decrypt=False:value):
                account.save({'passId':'own-id','passToken':'own-token','userData':{'email':'private'}},path)
                record=account.load(path)
            self.assertEqual(set(record),{'version','passId','passToken'})
            self.assertNotIn(b'private',path.read_bytes())

    def test_bootstrap_is_restricted_to_polish_official_origin(self):
        script=account.bootstrap({'version':1,'passId':'a; bad=1','passToken':'b"\n'})
        self.assertIn("location.origin !== 'https://www.canalplus.com'",script)
        self.assertIn("location.pathname.startsWith('/pl/')",script)
        self.assertIn('a%3B%20bad%3D1',script)
        self.assertNotIn('a; bad=1',script)

    def test_invalid_session_is_rejected_before_persistence(self):
        with patch.object(account,'protect') as crypt:
            with self.assertRaises(account.AccountError):account.save({'passId':'id'})
            crypt.assert_not_called()

    def test_channel_script_only_accepts_numeric_channel_and_official_origin(self):
        record={'version':1,'passId':'test','passToken':'test'}
        for channel in ('../x','1;alert(1)','１２３'):
            with self.assertRaises(ValueError):account.channel_script(record,channel)
        script=account.channel_script(record,'20318')
        self.assertIn("location.origin!=='https://www.canalplus.com'",script)
        self.assertIn('https://player.canalplus.com/one/prod/v2/bundle-api.js',script)
        self.assertNotIn('QA ',script)
