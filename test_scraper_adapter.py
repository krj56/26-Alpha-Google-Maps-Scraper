#!/usr/bin/env python3
"""Tests for Streamlit adapter compatibility with scraper interfaces."""

import unittest
from unittest.mock import patch

import pandas as pd

import scraper_adapter as adapter


class _NewScraperInterface:
    def __init__(self):
        self.calls = []

    def search_businesses(self, query, max_results=20):
        self.calls.append((query, max_results))
        return [
            {
                "Company Name": "Alpha Dental",
                "Company Address": "123 Main St",
                "Website": "https://alpha.example",
                "Google Review Rating": 4.8,
                "Google Review Count": 52,
            }
        ]


class _LegacyScraperInterface:
    def search_places(self, query, max_results=20):
        return [
            {
                "name": "Legacy Dental",
                "address": "555 Broad St",
                "website": "https://legacy.example",
                "rating": 4.5,
                "review_count": 17,
            }
        ]


class TestScraperAdapter(unittest.TestCase):
    def test_create_scraper_passes_api_key_directly(self):
        with patch("scraper_adapter.GoogleMapsReviewScraper") as scraper_cls:
            scraper = adapter.create_scraper("abc123")

        scraper_cls.assert_called_once_with(api_key="abc123")
        self.assertIs(scraper, scraper_cls.return_value)

    def test_search_places_uses_new_scraper_interface(self):
        scraper = _NewScraperInterface()

        df = adapter.search_places(scraper, "dentists in austin", max_results=5)

        self.assertEqual(scraper.calls, [("dentists in austin", 5)])
        self.assertEqual(len(df), 1)
        self.assertEqual(df.at[0, "Company Name"], "Alpha Dental")
        self.assertEqual(df.at[0, "Google Review Rating"], 4.8)

    def test_search_places_supports_legacy_interface(self):
        scraper = _LegacyScraperInterface()

        df = adapter.search_places(scraper, "legacy query", max_results=3)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.at[0, "Company Name"], "Legacy Dental")
        self.assertEqual(df.at[0, "Google Review Count"], 17)

    def test_enrich_with_reviews_updates_missing_values(self):
        scraper = _NewScraperInterface()
        df = pd.DataFrame(
            [
                {
                    "Company Name": "Alpha Dental",
                    "Company Address": "123 Main St",
                    "Google Review Rating": "",
                    "Google Review Count": "",
                }
            ]
        )

        with patch("scraper_adapter.time.sleep", return_value=None):
            result = adapter.enrich_with_reviews(scraper, df)

        self.assertEqual(result.at[0, "Google Review Rating"], 4.8)
        self.assertEqual(result.at[0, "Google Review Count"], 52)
        self.assertEqual(scraper.calls, [("Alpha Dental 123 Main St", 1)])

    def test_enrich_with_reviews_skips_rows_with_existing_rating_and_count(self):
        scraper = _NewScraperInterface()
        df = pd.DataFrame(
            [
                {
                    "Company Name": "Alpha Dental",
                    "Company Address": "123 Main St",
                    "Google Review Rating": 4.7,
                    "Google Review Count": 10,
                }
            ]
        )

        with patch("scraper_adapter.time.sleep", return_value=None):
            result = adapter.enrich_with_reviews(scraper, df)

        self.assertEqual(result.at[0, "Google Review Rating"], 4.7)
        self.assertEqual(result.at[0, "Google Review Count"], 10)
        self.assertEqual(scraper.calls, [])


if __name__ == "__main__":
    unittest.main()
