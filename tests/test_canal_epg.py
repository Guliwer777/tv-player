import importlib
import sys
import types
from pathlib import Path
from datetime import datetime,timezone
import unittest

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
epg=importlib.import_module('tvpVod.canal_epg')


class EpgTests(unittest.TestCase):
    def test_current_program_is_end_exclusive_and_sorted(self):
        data={'channels':[{'id':1,'events':[
            {'title':'Drugi','startDate':'2026-10-17T11:00:00Z','endDate':'2026-10-17T12:00:00Z'},
            {'title':'Pierwszy','startDate':'2026-10-17T10:00:00Z','endDate':'2026-10-17T11:00:00Z'},
            {'title':'Błędny','startDate':'bad','endDate':'bad'}]}]}
        rows=epg.programs(data,1)
        self.assertEqual([r['title'] for r in rows],['Pierwszy','Drugi'])
        self.assertEqual(epg.current(rows,datetime(2026,10,17,11,tzinfo=timezone.utc))['title'],'Drugi')
        self.assertEqual(epg.programs(data,2),[])
        self.assertEqual(len(epg.days(rows)),1)


class FullGuideTests(unittest.TestCase):
    def test_schedule_deduplicates_and_rejects_invalid_times(self):
        item={'title':'Mecz','subtitle':'Finał','startTime':1792211400000,'endTime':1792220400000}
        data={'timeSlices':[{'contents':[item,dict(item),{'title':'Zły','startTime':1,'endTime':0}]}]}
        rows=epg.parse_schedule(data)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['subtitle'],'Finał')
        self.assertIsNotNone(rows[0]['start'].tzinfo)

    def test_follows_official_days_and_exact_channel(self):
        from unittest.mock import patch
        guide='https://hodor.canalplus.pro/api/v2/mycanalint/programGuide/test'
        root='https://hodor.canalplus.pro/api/v2/mycanalint/'
        responses={
          'https://www.canalplus.com/pl/program-tv/':'{"URLProgramGuide":"'+guide+'"}',
          guide:{'rubriques':[{'day':0,'URLPage':root+'grid0'},{'day':1,'URLPage':root+'grid1'}]},
          root+'grid0':{'channels':[{'URLChannelSchedule':root+'channels/hash/123/broadcasts/day/0'}]},
          root+'grid1':{'channels':[{'URLChannelSchedule':root+'channels/hash/123/broadcasts/day/1'}]},
          root+'channels/hash/123/broadcasts/day/0':{'timeSlices':[{'contents':[{'title':'Dziś','startTime':1792211400000,'endTime':1792220400000}]}]},
          root+'channels/hash/123/broadcasts/day/1':{'timeSlices':[{'contents':[{'title':'Jutro','startTime':1792297800000,'endTime':1792306800000}]}]},
        }
        with patch.object(epg,'guide_request',side_effect=lambda url,**kw:responses[url]):
            self.assertEqual([r['title'] for r in epg.full_programs('123')],['Dziś','Jutro'])
        with self.assertRaises(epg.CatalogError):epg.guide_request('https://example.com/api')
