import importlib,sys,types,unittest,threading,ast
from pathlib import Path
from unittest.mock import patch
p=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));p.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
c=importlib.import_module('tvpVod.catalog');purchase=importlib.import_module('tvpVod.purchase');player=importlib.import_module('tvpVod.player')
class PurchaseTests(unittest.TestCase):
 def item(self,kind='VOD',url='https://vod.tvp.pl/filmy,test,1'):
  return c.Material(1,'Test','',url,kind,True)
 def test_only_official_material_page_is_opened(self):
  browser=importlib.import_module('tvpVod.canal_browser')
  with patch.object(browser,'open_url') as opened:
   purchase.open_page(self.item(),'firefox')
   opened.assert_called_once_with('https://vod.tvp.pl/filmy,test,1','firefox',allowed_hosts=('vod.tvp.pl',))
 def test_reject_foreign_checkout_and_embedded_credentials(self):
  for url in ('https://vod.tvp.pl.evil/x','https://user@vod.tvp.pl/x','http://vod.tvp.pl/x','https://vod.tvp.pl:444/x'):
   with self.assertRaises(ValueError):purchase.page(self.item(url=url))
 def test_paid_label_does_not_replace_real_account_rights(self):
  with patch.object(player,'api',return_value={'sources':{'HLS':[{'src':'https://cdn.tvp.pl/video.m3u8'}]}}):
   self.assertEqual(player.resolve(self.item(),web=True).url,self.item().url)
 def test_only_explicit_tvp_payment_denial_is_purchase(self):
  with patch.object(player,'api',return_value={'code':'ITEM_NOT_PAID'}):
   with self.assertRaises(purchase.PurchaseRequired):player.resolve(self.item(),web=True)
  with patch.object(player,'api',side_effect=c.CatalogError('network')):
   with self.assertRaises(c.CatalogError) as error:player.resolve(self.item(),web=True)
   self.assertNotIsInstance(error.exception,purchase.PurchaseRequired)
 def test_other_provider_material_pages(self):
  for kind,url in [('POLSAT','https://polsatboxgo.pl/wideo/test/1/ogladaj'),('CANAL','https://www.canalplus.com/pl/filmy/test/p/1'),('PLAYERPL','https://player.pl/filmy/test,1')]:
   self.assertEqual(purchase.page(self.item(kind,url))[0],url)

 def test_automatic_next_does_not_open_checkout(self):
  path=Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod/playbackDialog.py'
  tree=ast.parse(path.read_text(encoding='utf-8'));cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PlaybackDialog');method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='offer_purchase')
  namespace={'__package__':'tvpVod'};exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),namespace)
  messages=[];dialog=types.SimpleNamespace(alive=True,automatic_transition=True,report_error=messages.append)
  with patch.object(purchase,'open_page') as opened:namespace['offer_purchase'](dialog,'Brak dostępu');opened.assert_not_called()
  self.assertTrue(dialog.purchase_pending);self.assertEqual(messages,['Brak dostępu'])
