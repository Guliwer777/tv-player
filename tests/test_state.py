import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

if "tvpVod" not in sys.modules:
    package = types.ModuleType("tvpVod")
    package.__path__ = [str(Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod")]
    sys.modules["tvpVod"] = package
state = importlib.import_module("tvpVod.state")
catalog = importlib.import_module("tvpVod.catalog")


class PersistenceTests(unittest.TestCase):
    def test_watched_persists_across_all_other_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';store=state.Store(path)
            movie=catalog.Material(123,'Film','','https://vod.tvp.pl/film,123','VOD',False)
            live=catalog.Material(456,'Kanał','','https://vod.tvp.pl/live,456','LIVE',False)
            self.assertTrue(store.mark_watched(movie))
            self.assertFalse(store.mark_watched(movie))
            self.assertFalse(store.mark_watched(live))
            store.add_favorite(movie);store.configure({'volume':60})
            store.add(movie,20,{},'Zakładka');store.save_session(movie,30,{})
            loaded=state.Store(path)
            self.assertTrue(loaded.is_watched(movie));self.assertFalse(loaded.is_watched(live))
            self.assertEqual(len(loaded.favorites),1);self.assertEqual(len(loaded.bookmarks),1)

    def test_favorites_persist_deduplicate_and_survive_other_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';store=state.Store(path)
            movie=catalog.Material(123,'Film','','https://vod.tvp.pl/film,123','VOD',False)
            folder=catalog.Folder(123,'Sezon','SEASON','products/vods/serials/1/seasons/123/episodes')
            self.assertTrue(store.add_favorite(movie))
            self.assertFalse(store.add_favorite(movie))
            self.assertTrue(store.add_favorite(folder))
            store.configure({'volume':65})
            store.add(movie,12,{},'Zakładka')
            store.save_session(movie,42,{})
            loaded=state.Store(path)
            self.assertEqual([state.decode(x) for x in loaded.favorites],[movie,folder])
            loaded.remove_favorite(movie)
            loaded=state.Store(path)
            self.assertEqual([state.decode(x) for x in loaded.favorites],[folder])
            self.assertEqual(len(loaded.bookmarks),1)
            self.assertEqual(loaded.last_session['position'],42)

    def test_command_timeout_choices_persist_and_invalid_values_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';store=state.Store(path)
            for value,label in state.COMMAND_TIMEOUT_CHOICES:
                store.configure({'commandTimeout':value})
                self.assertEqual(state.Store(path).settings['commandTimeout'],value)
            for invalid in (True,999,'15',None,[]):
                store.configure({'commandTimeout':invalid})
                self.assertEqual(state.Store(path).settings['commandTimeout'],5)

    def test_command_feedback_saved_and_invalid_value_defaults_to_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            store=state.Store(path)
            self.assertEqual(store.settings['commandFeedback'],'speech')
            for value in ('sound','none','speech'):
                store.configure({'commandFeedback':value})
                self.assertEqual(state.Store(path).settings['commandFeedback'],value)
            store.configure({'commandFeedback':'invalid'})
            self.assertEqual(state.Store(path).settings['commandFeedback'],'speech')

    def test_quality_is_saved_and_unknown_value_reverts_to_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            store=state.Store(path)
            store.configure({'quality':'800000'})
            self.assertEqual(state.Store(path).settings['quality'],'800000')
            store.configure({'quality':'invalid'})
            self.assertEqual(state.Store(path).settings['quality'],'auto')

    def test_last_session_survives_restart_bookmark_and_settings_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = state.Store(path)
            material = catalog.Material(12, "Odcinek", "", "", "EPISODE", False)
            context = {"current": state.pack_frame([material], None, 0, "Odcinki", 0), "history": []}
            store.save_session(material, 125.375, context)
            store.configure({"volume": 45})
            bookmark = store.add(material, 1, context, "Zakładka")
            store.remove(bookmark["id"])
            reloaded = state.Store(path)
            self.assertEqual(reloaded.last_session["position"], 125.375)
            self.assertEqual(state.decode(reloaded.last_session["material"]), material)
            self.assertEqual(reloaded.last_session["context"], context)
            self.assertEqual(reloaded.settings["volume"], 45)

    def test_bookmark_restores_fractional_time_navigation_and_settings_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = state.Store(path)
            material = catalog.Material(12, "Odcinek 1100", "Opis", "https://vod.tvp.pl/a", "EPISODE", False)
            folder = catalog.Folder(10, "Sezon", "SEASON", "products/vods/serials/1/seasons/10/episodes")
            frame = state.pack_frame([material, state.MenuEntry("Następna strona", "next")], folder, 50, "M jak miłość", 0)
            context = {"current": frame, "history": [state.pack_frame([state.MenuEntry("Kategorie", "categories")], None, 0, "TVP VOD", 0)]}
            bookmark = store.add(material, 125.375, context, "Odcinek")
            store.configure({"afterEnd": "next", "seekStep": 30})
            reloaded = state.Store(path)
            saved = reloaded.find(bookmark["id"])
            self.assertEqual(saved["position"], 125.375)
            items, restored_folder, offset, heading, selection = state.unpack_frame(saved["context"]["current"])
            self.assertEqual(items[selection], material)
            self.assertEqual(restored_folder, folder)
            self.assertEqual((offset, heading), (50, "M jak miłość"))
            self.assertEqual(reloaded.settings["afterEnd"], "next")
            reloaded.remove(bookmark["id"])
            self.assertEqual(state.Store(path).bookmarks, [])

    def test_failed_write_keeps_existing_bookmarks_in_memory_and_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            store = state.Store(Path(directory) / "state.json")
            material = catalog.Material(1, "Film", "", "", "VOD", False)
            store.add(material, 1.5, {}, "Pierwsza")
            before = store.path.read_bytes()
            with patch.object(Path, "replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    store.add(material, 2.5, {}, "Druga")
            self.assertEqual(len(store.bookmarks), 1)
            self.assertEqual(store.path.read_bytes(), before)

    def test_live_and_invalid_positions_cannot_be_bookmarked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = state.Store(Path(directory) / "state.json")
            for kind, position in (("LIVE", 5), ("VOD", float("nan")), ("VOD", -1)):
                with self.assertRaises(ValueError):
                    store.add(catalog.Material(1, "Title", "", "", kind, False), position, {}, "Test")


class NextEpisodeTests(unittest.TestCase):
    def test_last_episode_moves_to_first_episode_of_next_nonempty_season(self):
        current = catalog.Material(12, "Odcinek 2", "", "", "EPISODE", False)
        following = catalog.Material(13, "Odcinek 3", "", "", "EPISODE", False,episode_number=3)
        folder = catalog.Folder(10, "Sezon 1", "SEASON", "products/vods/serials/1/seasons/10/episodes")
        with patch.object(catalog, "browse", side_effect=[([current], False), ([], False), ([following], False)]), \
             patch.object(catalog, "api", side_effect=[{"number":2,"season":{"id":10,"number":1,"serial":{"id":1}}},[{"id":30,"number":3},{"id":10,"number":1},{"id":20,"number":2}]]) as api:
            material, next_folder, items = catalog.following_episode(current, folder)
        self.assertEqual(api.call_args.args[0], "products/vods/serials/1/seasons")
        self.assertEqual(material.id, 13)
        self.assertEqual(next_folder.resource, "products/vods/serials/1/seasons/30/episodes")

    def test_final_episode_stops_and_movies_do_not_autoplay(self):
        episode = catalog.Material(12, "Episode", "", "", "EPISODE", False)
        folder = catalog.Folder(10, "Season", "SEASON", "products/vods/serials/1/seasons/10/episodes")
        with patch.object(catalog, "browse", return_value=([episode], False)), patch.object(catalog, "api", return_value={"season":{"id":10,"number":1,"serial":{"id":1}}}):
            self.assertIsNone(catalog.following_episode(episode, folder))
        self.assertIsNone(catalog.following_episode(catalog.Material(1, "Film", "", "", "VOD", False), None))
