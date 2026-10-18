import importlib
import sys
import types
from pathlib import Path
import unittest

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
live=importlib.import_module('tvpVod.canal_live')


class ChannelsTests(unittest.TestCase):
    def test_denied_channels_excluded_and_duplicates_removed(self):
        rows=live.parse_channels({'PDS':{'ChannelsGroups':{'ChannelsGroup':[{'Channels':[
            {'Name':'TVP Sport','EpgId':'20318','AccessRights':{'NoAccess':'false'}},
            {'Name':'TVP Sport','EpgId':'20318'},
            {'Name':'Premium','EpgId':'900','AccessRights':{'NoAccess':'true'}},
            {'Name':'Premium2','EpgId':'901','AccessRights':{'NoAccess':True}},
            {'Name':'Invalid','EpgId':'../secret'}]}]}}})
        self.assertEqual([item.title for item in rows],['TVP Sport'])
        self.assertEqual(rows[0].url,'https://www.canalplus.com/pl/#tvp-player-channel=20318')
        self.assertEqual(rows[0].kind,'CANAL_LIVE')

    def test_empty_catalogue_does_not_pretend_success(self):
        with self.assertRaises(live.CatalogError):live.parse_channels({})


class ChannelGroupsTests(unittest.TestCase):
    def test_recognized_channels_and_specific_variants(self):
        cases = {'TVP 1 HD':'general', 'TVP 3 Kraków':'general',
                 'TVP Sport':'sport', 'EUROSPORT2 HD':'sport',
                 'CANAL+ SPORT 5':'sport', 'TVN 24 HD':'news',
                 'TVN 7 HD':'general', 'DISNEY JUNIOR':'kids',
                 '4FUN KIDS':'kids', 'KINO POLSKA MUZYKA':'music',
                 'NATIONAL GEOGRAPHIC HD':'documentary',
                 'Nieznany nowy kanał':'other'}
        for name, expected in cases.items():
            with self.subTest(name=name):self.assertEqual(live.channel_group(name),expected)

    def test_categories_preserve_every_available_channel_once(self):
        rows=live.parse_channels({'PDS':{'ChannelsGroups':{'ChannelsGroup':[{'Channels':[
            {'Name':name,'EpgId':str(i)} for i,name in enumerate(
                ['TVP Sport','TVP 1 HD','DISNEY JUNIOR','Nowy kanał'],1)]}]}}})
        folders,_=live.grouped(rows)
        self.assertEqual(folders[0].resource,'live:all')
        self.assertEqual(live.grouped(rows,'all')[0],rows)
        partition=[]
        for folder in folders[1:]:partition+=live.grouped(rows,folder.resource.split(':')[1])[0]
        self.assertCountEqual(partition,rows)
        self.assertEqual(len(partition),len(rows))
        self.assertTrue(any(f.resource=='live:other' for f in folders))
        with self.assertRaises(live.CatalogError):live.grouped(rows,'unknown')
