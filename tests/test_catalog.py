import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod/catalog.py"
spec = importlib.util.spec_from_file_location("catalog", source)
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def item(self, **changes):
        return {"id": 1, "title": "Próba", "webUrl": "https://vod.tvp.pl/film,1",
                "lead": "<p>Opis &amp; treść</p>", **changes}

    def test_untrusted_links_are_ignored(self):
        for url in ("javascript:alert(1)", "https://vod.tvp.pl.evil.org/a", "file:///a", "https://evil@vod.tvp.pl/a"):
            self.assertEqual(catalog.parse_items({"items": [self.item(webUrl=url)]}), [])

    def test_html_is_plain_text(self):
        self.assertEqual(catalog.parse_items({"items": [self.item()]})[0].description, "Opis & treść")

    def test_search_combines_and_deduplicates_all_types(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return {"items": [self.item()]}
        self.assertEqual(len(catalog.search("żółć & kot", fetch)), 1)
        self.assertEqual(len(urls), 3)
        self.assertIn("/EPISODE?", urls[-1])
        self.assertIn("%26", urls[0])

    def test_exact_film_precedes_related_series_and_same_named_episode(self):
        records=[self.item(id=2,title='Inny serial',type='SERIAL'),
                 self.item(id=3,title='Pan Tadeusz',type='EPISODE'),
                 self.item(id=4,title='Pan Tadeusz – zwiastun',type='VOD'),
                 self.item(id=2450939,title='PAN TADEUSZ',type='VOD')]
        result=catalog.search(' pan tadeusz ',lambda url:{'items':records})
        self.assertEqual([item.id for item in result],[2450939,3,4,2])

    def test_full_description_preferred_and_empty_html_falls_back_to_lead(self):
        self.assertEqual(catalog.description_from({'description':'<p>Pełny opis</p><p>Drugi akapit</p>','lead':'Skrót'}),'Pełny opis\nDrugi akapit')
        self.assertEqual(catalog.description_from({'description':'<p>&nbsp;</p>','lead':'Opis skrócony'}),'Opis skrócony')

    def test_missing_list_description_is_fetched_from_item_details(self):
        item=catalog.parse_items({'items':[self.item(lead='',description='')]})[0]
        with patch.object(catalog,'api',return_value={'description':'<p>Opis w szczegółach</p>'}) as request:
            self.assertEqual(catalog.material_description(item),'Opis w szczegółach')
            request.assert_called_once_with('products/vods/1')

    def test_category_hierarchy_preserves_parent_filter(self):
        root = catalog.Folder(18, "seriale", "CATEGORY", "products/vods|mainCategoryId[]")
        with patch.object(catalog, "api", return_value=[{"id": 185, "name": "archiwalne"}]):
            children, more = catalog.browse(root)
        self.assertEqual(children[0].title, "Wszystkie materiały")
        with patch.object(catalog, "api", return_value={"items": [self.item()], "meta": {"totalCount": 120}}) as api:
            _, more = catalog.browse(children[1], 50)
            self.assertEqual(api.call_args.kwargs["mainCategoryId[]"], 18)
            self.assertEqual(api.call_args.kwargs["categoryId[]"], 185)
            self.assertTrue(more)

    def test_seasons_then_episodes(self):
        series = catalog.series_folder(catalog.Material(10, "Serial", "", "", "SERIAL", False))
        with patch.object(catalog, "api", return_value=[{"id": 20, "title": "Sezon 1"}]):
            seasons, _ = catalog.browse(series)
        self.assertEqual(seasons[0].resource, "products/vods/serials/10/seasons/20/episodes")

    def test_unknown_format_is_error(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.parse_items({"unexpected": []})


if __name__ == "__main__":
    unittest.main()
