import pathlib
import unittest

from services.providers.base import ProviderError, ProviderNotReady
from services.providers.live_config import LiveConfig
from services.providers.live_provider import LiveProvider, find_row, parse_rows

SAMPLE = (pathlib.Path(__file__).parent / "fixtures" / "sample_response.txt").read_text(encoding="utf-8")

SILVER = (pathlib.Path(__file__).parent / "fixtures" / "sample_silver_response.txt").read_text(encoding="utf-8")


def cfg(**kw):
    base = dict(provider_name="X", url="https://example.invalid/x?_=", api_key="", min_interval=10,
                permission_confirmed=True, row_map={"gold24": "2275"}, value_column=2)
    return LiveConfig(**{**base, **kw})


class ParserTests(unittest.TestCase):
    def test_rows_and_names(self):
        rows = {r.id: r for r in parse_rows(SAMPLE)}
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows["2275"].name, "GOLD INDIAN-BIS 995 1KG (12th Nov)")
        self.assertEqual(rows["2275"].values, ("140583", "140883", "142233", "140687"))
        self.assertEqual(rows["2157"].values[0], "-")
        self.assertEqual(rows["2147"].name, "GOLD($).")

    def test_id_match_second_column(self):
        recs = LiveProvider(cfg()).parse(SAMPLE)
        self.assertEqual([(r.key, r.value) for r in recs], [("gold24", 140883.0)])

    def test_name_match_ignores_changing_date(self):
        moved = SAMPLE.replace("(12th Nov)", "(19th Nov)")
        p = LiveProvider(cfg(row_map={"gold24": "GOLD INDIAN-BIS 995 1KG"}))
        self.assertEqual(p.parse(moved)[0].value, 140883.0)

    def test_name_match_with_bracket_text(self):
        row = find_row(parse_rows(SAMPLE), "GOLD RTGS 995 (WITH GST)")
        self.assertEqual(row.id, "2278")

    def test_dash_value_is_an_error_not_a_rate(self):
        with self.assertRaises(ProviderError):
            LiveProvider(cfg(row_map={"gold24": "2157"}, value_column=1)).parse(SAMPLE)

    def test_missing_or_ambiguous_row(self):
        with self.assertRaises(ProviderError):
            LiveProvider(cfg(row_map={"gold24": "9999"})).parse(SAMPLE)
        twice = SAMPLE + " 2300    GOLD INDIAN-BIS 995 1KG (13th Nov)  1 2 3 4\n"
        with self.assertRaises(ProviderError):
            LiveProvider(cfg(row_map={"gold24": "GOLD INDIAN-BIS 995 1KG"})).parse(twice)

    def test_column_out_of_range(self):
        with self.assertRaises(ProviderError):
            LiveProvider(cfg(value_column=9)).parse(SAMPLE)

    def test_html_or_empty_response_rejected(self):
        for bad in ("<html><body>Error</body></html>", "", "no rows here"):
            with self.assertRaises(ProviderError):
                LiveProvider(cfg()).parse(bad)


class GateTests(unittest.TestCase):
    def test_disabled_without_permission_or_mapping(self):
        self.assertFalse(LiveProvider(cfg(permission_confirmed=False)).available())
        self.assertFalse(LiveProvider(cfg(row_map={})).available())
        self.assertFalse(LiveProvider(cfg(min_interval=0)).available())
        with self.assertRaises(ProviderNotReady):
            LiveProvider(cfg(permission_confirmed=False)).fetch()

    def test_available_when_complete(self):
        self.assertTrue(LiveProvider(cfg()).available())


class TwoSourceTests(unittest.TestCase):
    def provider(self):
        return LiveProvider(cfg(url="https://gold.invalid/x?_=", row_map={"gold24": "2275", "silver": "4642"},
                                url_map={"silver": "https://silver.invalid/y?_="}))

    def test_silver_row_second_column(self):
        rows = {r.id: r for r in parse_rows(SILVER)}
        self.assertEqual(rows["4642"].values, ("-", "185804", "186778", "183027"))
        self.assertEqual(self.provider().parse(SILVER, ["silver"])[0].value, 185804.0)

    def test_fetch_combines_two_feeds(self):
        p, calls = self.provider(), []
        p._download = lambda url: (calls.append(url), SILVER if "silver" in url else SAMPLE)[1]
        self.assertEqual({r.key: r.value for r in p.fetch()}, {"gold24": 140883.0, "silver": 185804.0})
        self.assertEqual(len(calls), 2)

    def test_one_failing_feed_refreshes_nothing(self):
        p = self.provider()

        def dl(url):
            if "silver" in url:
                raise ProviderError("silver feed down")
            return SAMPLE
        p._download = dl
        with self.assertRaises(ProviderError):
            p.fetch()

    def test_shared_feed_downloaded_once(self):
        p, calls = LiveProvider(cfg(row_map={"gold24": "2275", "gold22": "2206"})), []
        p._download = lambda url: (calls.append(url), SAMPLE)[1]
        self.assertEqual(len(p.fetch()), 2)
        self.assertEqual(len(calls), 1)

    def test_every_mapped_rate_needs_a_url(self):
        c = cfg(url="", row_map={"gold24": "2275", "silver": "4642"}, url_map={"silver": "https://s.invalid/"})
        self.assertTrue(any("LIVE_URL" in g for g in c.missing()))
        self.assertFalse(LiveProvider(c).available())


if __name__ == "__main__":
    unittest.main()
