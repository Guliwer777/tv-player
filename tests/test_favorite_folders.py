import importlib,sys,types,tempfile,unittest,json
from pathlib import Path
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
s=importlib.import_module('tvpVod.state')

class FavoriteFolderTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'settings.json';self.store=s.Store(self.path)
  self.item=s.Material(10,'Film','','https://example.test/film','VOD',False)
 def test_old_favorites_load_at_root(self):
  self.store.add_favorite(self.item)
  data=json.loads(self.path.read_text(encoding='utf-8'));data.pop('favoriteFolders');self.path.write_text(json.dumps(data),encoding='utf-8')
  loaded=s.Store(self.path)
  self.assertEqual(len(loaded.favorites),1);self.assertEqual(loaded.favorite_folders,[])
 def test_group_survives_settings_bookmarks_and_restart(self):
  folder=self.store.create_favorite_folder('Filmy')['id'];self.store.add_favorite(self.item,folder)
  self.store.configure({'volume':50});self.store.add(self.item,10,{},'Zakładka')
  loaded=s.Store(self.path)
  self.assertEqual(loaded.favorites[0]['folder'],folder);self.assertEqual(loaded.favorite_folders[0]['name'],'Filmy')
  self.assertEqual(loaded.settings['volume'],50);self.assertEqual(len(loaded.bookmarks),1)
 def test_deduplicates_per_folder_and_remove_is_scoped(self):
  folder=self.store.create_favorite_folder('Sport')['id']
  self.assertTrue(self.store.add_favorite(self.item));self.assertTrue(self.store.add_favorite(self.item,folder))
  self.assertFalse(self.store.add_favorite(self.item,folder));self.store.remove_favorite(self.item,folder)
  self.assertEqual(len(self.store.favorites),1);self.assertNotIn('folder',self.store.favorites[0])
 def test_delete_folder_moves_entries_to_root_without_duplicates(self):
  folder=self.store.create_favorite_folder('Filmy')['id'];self.store.add_favorite(self.item);self.store.add_favorite(self.item,folder)
  self.store.remove_favorite_folder(folder)
  loaded=s.Store(self.path);self.assertEqual(len(loaded.favorites),1);self.assertEqual(loaded.favorite_folders,[])
 def test_move_does_not_duplicate_existing_target(self):
  folder=self.store.create_favorite_folder('Filmy')['id'];self.store.add_favorite(self.item);self.store.add_favorite(self.item,folder)
  self.store.move_favorite(self.item,None,folder)
  self.assertEqual(len(self.store.favorites),1);self.assertEqual(self.store.favorites[0]['folder'],folder)
 def test_invalid_folder_names_and_unknown_destination(self):
  self.store.create_favorite_folder(' Sport ')
  for name in ('','sport','x'*121):
   with self.assertRaises(ValueError):self.store.create_favorite_folder(name)
  with self.assertRaises(ValueError):self.store.add_favorite(self.item,'missing')
