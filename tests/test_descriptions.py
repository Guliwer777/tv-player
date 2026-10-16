import importlib
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import patch

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
module=importlib.import_module('tvpVod.descriptions')
catalog=importlib.import_module('tvpVod.catalog')

class DescriptionTests(unittest.TestCase):
    def test_pending_selections_are_replaced_instead_of_queued(self):
        started=threading.Event();release=threading.Event();events=queue.Queue();fetched=[]
        def fetch(item):
            fetched.append(item.id)
            if item.id==1:started.set();release.wait(2)
            return str(item.id)
        items=[catalog.Material(i,'Film','','','VOD',False) for i in (1,2,3)]
        with patch.object(module,'material_description',side_effect=fetch):
            loader=module.DescriptionLoader(lambda token,text:events.put((token,text)))
            try:
                loader.request(items[0],1);self.assertTrue(started.wait(2))
                loader.request(items[1],2);loader.request(items[2],3);release.set()
                self.assertEqual(events.get(timeout=2),(1,'1'))
                self.assertEqual(events.get(timeout=2),(3,'3'))
                self.assertEqual(fetched,[1,3])
            finally:release.set();loader.close()

    def test_cached_description_and_no_cache_for_temporary_errors(self):
        item=catalog.Material(123,'Film','','https://vod.tvp.pl/film,123','VOD',False)
        events=queue.Queue()
        with patch.object(module,'material_description',side_effect=[catalog.CatalogError('Offline'),'Pełny opis']) as fetch:
            loader=module.DescriptionLoader(lambda token,text:events.put((token,text)))
            try:
                loader.request(item,1)
                self.assertIn('Nie udało',events.get(timeout=2)[1])
                loader.request(item,2)
                self.assertEqual(events.get(timeout=2),(2,'Pełny opis'))
                loader.request(item,3)
                self.assertEqual(events.get(timeout=2),(3,'Pełny opis'))
                self.assertEqual(fetch.call_count,2)
            finally:loader.close()
