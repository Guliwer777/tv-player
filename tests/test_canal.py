import unittest
import sys,types,importlib
from pathlib import Path
from unittest.mock import patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
canal=importlib.import_module('tvpVod.canal')
catalog=importlib.import_module('tvpVod.catalog')
player=importlib.import_module('tvpVod.player')

class CanalTests(unittest.TestCase):
    def test_only_polish_official_https_pages(self):
        self.assertTrue(canal.official_url(canal.HOME))
        for url in ('http://www.canalplus.com/pl/','https://www.canalplus.com.evil/pl/','https://u@www.canalplus.com/pl/','https://www.canalplus.com:8443/pl/','https://www.canalplus.com/fr/','file:///pl/'):
            self.assertFalse(canal.official_url(url))
    def test_catalog_filters_external_links_and_deduplicates(self):
        html='<a href="/pl/film/">Filmy</a><a href="/pl/film/test/h/123_70001"><img alt="Film test"></a><a href="/pl/film/test/h/123_70001">Film test</a><a href="https://evil.example/pl/film/h/2">Obce</a><a href="/pl/konto/">Konto</a>'
        rows,more=canal.parse(html,canal.HOME,'CANAL+')
        self.assertEqual([x.title for x in rows[1:]],['Filmy','Film test'])
        self.assertTrue(all(x.id<0 and x.kind in ('CANAL','CANAL_LIVE') for x in rows));self.assertFalse(more)
    def test_details_offer_official_player_without_inventing_stream(self):
        url='https://www.canalplus.com/pl/film/test/h/123_70001'
        rows,_=canal.parse('',url,'Film test')
        self.assertIsInstance(rows[0],catalog.Material)
        with patch.object(player,'api',side_effect=AssertionError('TVP API must not be called')):
            self.assertEqual(player.resolve(rows[0],web=True).url,url)
    def test_redirects_cannot_send_requests_to_other_hosts(self):
        with self.assertRaises(catalog.CatalogError):canal.SafeRedirect().redirect_request(None,None,302,'',{},'https://evil.example/pl/')
    def test_browse_routes_to_canal_instead_of_tvp(self):
        folder=catalog.Folder(0,'CANAL+','CANAL','root')
        with patch.object(canal,'fetch',return_value='<a href="/pl/film/">Filmy</a>'):
            rows,_=catalog.browse(folder)
        self.assertEqual(rows[0].resource,'https://www.canalplus.com/pl/film/')
        self.assertEqual(len(rows),1)

class CanalIsolationTests(unittest.TestCase):
    def test_player_uses_separate_profile_and_does_not_pass_tvp_session(self):
        import os,tempfile
        web=importlib.import_module('tvpVod.webPlayer')
        with tempfile.TemporaryDirectory() as folder:
            globals_stub=types.SimpleNamespace(appArgs=types.SimpleNamespace(configPath=folder))
            with patch.dict(sys.modules,{'globalVars':globals_stub}), patch.dict(os.environ,{'TVPVOD_ACCOUNT_FILE':'private-tvp-session.dat'}), patch.object(web.threading,'Thread'), patch.object(web.subprocess,'Popen') as popen:
                web.WebPlayer(0,lambda event:None,player.OfficialSource(canal.HOME),direct=True)
            args=popen.call_args.args[0];env=popen.call_args.kwargs['env']
            self.assertIn('--canal',args);self.assertNotIn('--direct',args)
            self.assertNotIn('TVPVOD_ACCOUNT_FILE',env)
            self.assertEqual(Path(env['WEBVIEW2_USER_DATA_FOLDER']),Path(folder)/'tvpPlayer-canal-webview')

class EdgeLaunchTests(unittest.TestCase):
    def test_pairing_browser_uses_only_fixed_official_url(self):
        browser=importlib.import_module('tvpVod.canal_browser')
        with patch.object(browser.Path,'is_file',return_value=True),patch.object(browser.subprocess,'Popen') as popen:
            browser.open_pairing('firefox')
        args=popen.call_args.args[0]
        self.assertTrue(args[0].endswith('firefox.exe'))
        self.assertEqual(args[1],'https://account.canalplus.com/pl/pl/connect')
        with self.assertRaises(ValueError):browser.open_pairing('injected')

    def test_edge_only_opens_official_page_without_cookies_or_debugging(self):
        browser=importlib.import_module('tvpVod.canal_browser')
        with patch.object(browser,'find_edge',return_value='edge.exe'),patch.object(browser.subprocess,'Popen') as popen:
            browser.open_edge()
            self.assertEqual(popen.call_args.args[0],['edge.exe',canal.HOME])
            for url in ('https://evil.example/','file:///C:/','https://www.canalplus.com:8443/pl/'):
                with self.assertRaises(ValueError):browser.open_edge(url)
            self.assertEqual(popen.call_count,1)

if __name__=='__main__':unittest.main()
