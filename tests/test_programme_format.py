import importlib,sys,types,unittest
from pathlib import Path
from datetime import datetime,timezone
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
f=importlib.import_module('tvpVod.programmeFormat')
class FormatTests(unittest.TestCase):
 def test_replay_notice_placement(self):
  self.assertEqual(f.parts('Film','CZAS','Kanał',replay=True,signal='channel'),'Film — CZAS — Kanał — Można cofnąć')
  self.assertEqual(f.parts('Film','CZAS','Kanał',replay=True,signal='title'),'Film — Można cofnąć — CZAS — Kanał')
  self.assertNotIn('Można',f.parts('Film','CZAS','Kanał',replay=False,signal='title'))
 def test_all_six_orders_preserve_fields(self):
  self.assertEqual(len(f.ORDERS),6)
  for order,label in f.ORDERS:
   text=f.parts('FILM','CZAS','KANAL',order)
   self.assertEqual(text.split(' — '),[{'title':'FILM','time':'CZAS','channel':'KANAL'}[k] for k in order.split(',')])
 def test_invalid_order_falls_back_and_optional_fields_are_omitted(self):
  self.assertEqual(f.parts('Film','18:00','Kino','bad'),'Film — 18:00 — Kino')
  self.assertEqual(f.parts('Film','','Kino'),'Film — Kino')
 def test_dates_optional(self):
  row={'title':'Film','start':datetime(2026,10,17,16,tzinfo=timezone.utc),'end':datetime(2026,10,17,18,tzinfo=timezone.utc)}
  self.assertIn('17.10.2026',f.event_label(row,'Kino'))
  self.assertNotIn('17.10.2026',f.event_label(row,'Kino',date=False))
