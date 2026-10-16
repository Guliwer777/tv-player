import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
api=importlib.import_module('tvpVod.sport_api')
sport=importlib.import_module('tvpVod.sport')
catalog=importlib.import_module('tvpVod.catalog')
backend=importlib.import_module('tvpVod.player')

class SportTests(unittest.TestCase):
    def test_schedule_filters_ended_deduplicates_and_uses_video_not_article_id(self):
        def event(identifier,start,end,**extra):
            return dict(video_id=identifier,title='Wydarzenie',broadcast_start=start*1000,broadcast_end=end*1000,**extra)
        future=event(123,200,300,news={'_id':999,'url':'/999/article'})
        active=event(456,90,150,video={'url':'https://evil.example/video'})
        p={'items':[{'title':'Sport','items':[future,active,event(789,1,99)]},{'items':[future]}]}
        result=api.parse_schedule(p,100)
        self.assertEqual([x['id'] for x in result],[456,123])
        self.assertTrue(result[0]['active']);self.assertFalse(result[1]['active'])
        self.assertEqual(result[0]['url'],'https://sport.tvp.pl/456/transmisja')
        self.assertEqual(result[1]['url'],'https://sport.tvp.pl/123/transmisja')

    def test_polish_clock_handles_summer_and_winter(self):
        from datetime import datetime,timezone
        for date,wanted in [('2026-07-01T10:00:00','01.07.2026, 12:00'),('2026-12-01T10:00:00','01.12.2026, 11:00')]:
            timestamp=datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp()
            self.assertEqual(api.local_time(timestamp),wanted)
            with patch('zoneinfo.ZoneInfo',side_effect=KeyError('no tzdata')):
                self.assertEqual(api.local_time(timestamp),wanted)

    def test_free_live_hls_and_drm_dash_selection(self):
        p={'live':True,'formats':[{'mimeType':'application/x-mpegurl','url':'https://cdn.tvp.pl/live.m3u8'},
            {'mimeType':'application/dash+xml','url':'https://cdn.tvp.pl/live.mpd'}]}
        with patch.object(api,'fetch',return_value=json.dumps(p)):
            self.assertEqual(api.playlist(123)['protocol'],'HLS')
            self.assertTrue(api.playlist(123)['isLive'])
        p.update(drm=True,licenseServers={'WIDEVINE':'https://licence.tvp.pl/wv'})
        with patch.object(api,'fetch',return_value=json.dumps(p)):
            self.assertEqual(api.playlist(123)['protocol'],'DASH')
            self.assertEqual(api.playlist(123)['servers'],{'com.widevine.alpha':'https://licence.tvp.pl/wv'})

    def test_unavailable_geo_and_unsafe_sources_fail_without_bypass(self):
        samples=[{'formats':[]},{'geoBlocked':True},{'formats':[{'mimeType':'application/x-mpegurl','url':'http://cdn.tvp.pl/live'}]}]
        for p in samples:
            with patch.object(api,'fetch',return_value=json.dumps(p)):
                with self.assertRaises(ValueError):api.playlist(123)

    def test_sport_route_avoids_vod_api_and_descriptions(self):
        item=catalog.Material(123,'Mecz','Opis transmisji','https://sport.tvp.pl/123/mecz','LIVE',False)
        with patch.object(api,'playlist',return_value={'manifest':'https://cdn.tvp.pl/live'}),patch.object(backend,'api') as vod:
            source=backend.resolve(item,allow_drm=True,web=True)
            self.assertEqual(source,backend.OfficialSource(item.url,'LIVE'));vod.assert_not_called()
        with patch.object(catalog,'api') as vod:
            self.assertEqual(catalog.material_description(item),'Opis transmisji');vod.assert_not_called()

    def test_native_folders_and_live_channel(self):
        folders,_=sport.browse(catalog.Folder(0,'Sport','SPORT','root'))
        self.assertEqual([x.resource for x in folders[:2]],['now','upcoming'])
        self.assertEqual(folders[2].kind,'LIVE')
        self.assertEqual(folders[2].id,51696827)
        with patch.object(api,'schedule',return_value=[]):
            self.assertEqual(sport.browse(folders[0]),([],False))
            self.assertEqual(sport.browse(folders[1]),([],False))
