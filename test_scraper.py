#!/usr/bin/env python3
"""Regression tests for Google Maps scraper behavior."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from config import Config
from main import GoogleMapsReviewScraper


class TestGoogleMapsReviewScraper(unittest.TestCase):
    """Regression tests for previously identified issues."""

    def make_scraper(self):
        """Build scraper without requiring a real API key."""
        with patch.object(Config, "validate", return_value=None):
            scraper = GoogleMapsReviewScraper()
        scraper.api_key = "test-api-key"
        return scraper

    def test_search_place_handles_empty_places_list_as_not_found(self):
        scraper = self.make_scraper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"places": []}
        scraper.session.post = Mock(return_value=mock_response)

        place_id, error = scraper.search_place("Test Biz", "123 Main St")

        self.assertIsNone(place_id)
        self.assertEqual(error, "Business not found on Google Maps")

    def test_search_place_uses_configured_timeout(self):
        scraper = self.make_scraper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"places": [{"id": "places/abc123"}]}
        scraper.session.post = Mock(return_value=mock_response)

        place_id, error = scraper.search_place("Test Biz", "123 Main St")

        self.assertEqual(place_id, "places/abc123")
        self.assertIsNone(error)
        _, kwargs = scraper.session.post.call_args
        self.assertEqual(kwargs.get("timeout"), Config.REQUEST_TIMEOUT)

    def test_process_csv_resets_error_log_for_each_run(self):
        scraper = self.make_scraper()
        scraper.error_log = [{"error": "stale error"}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.csv"
            output_path = Path(tmp_dir) / "output.csv"

            pd.DataFrame(columns=["Company Name", "Company Address"]).to_csv(input_path, index=False)
            scraper.process_csv(str(input_path), str(output_path))

            self.assertEqual(scraper.error_log, [])
            self.assertTrue(output_path.exists())

    def test_append_with_url_column_dedupes_on_google_maps_url(self):
        scraper = self.make_scraper()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "leads.csv"
            existing_df = pd.DataFrame(
                [
                    {
                        "Company Name": "Alpha Dental",
                        "Company Address": "123 Main St",
                        "Google Maps URL": "https://maps.google.com/?cid=111",
                    }
                ]
            )
            existing_df.to_csv(output_path, index=False)

            scraper.search_businesses = Mock(
                return_value=[
                    {
                        "Company Name": "Alpha Dental",
                        "Company Address": "123 Main St",
                        "Phone Number": "",
                        "Website": "",
                        "Google Review Rating": 4.7,
                        "Google Review Count": 12,
                        "Google Maps URL": "https://maps.google.com/?cid=111",
                    },
                    {
                        "Company Name": "Beta Smiles",
                        "Company Address": "456 Oak Ave",
                        "Phone Number": "",
                        "Website": "",
                        "Google Review Rating": 4.8,
                        "Google Review Count": 34,
                        "Google Maps URL": "https://maps.google.com/?cid=222",
                    },
                ]
            )

            scraper.process_search("dentists", str(output_path), max_results=20, append=True)
            result_df = pd.read_csv(output_path)

            self.assertEqual(len(result_df), 2)
            self.assertIn("Beta Smiles", set(result_df["Company Name"]))

    def test_append_without_url_column_dedupes_on_name_and_address(self):
        scraper = self.make_scraper()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "leads.csv"
            existing_df = pd.DataFrame(
                [
                    {
                        "Company Name": "Alpha Dental",
                        "Company Address": "123 Main St, Austin, TX",
                    },
                    {
                        "Company Name": "Beta Smiles",
                        "Company Address": "456 Oak Ave, Austin, TX",
                    },
                ]
            )
            existing_df.to_csv(output_path, index=False)

            scraper.search_businesses = Mock(
                return_value=[
                    {
                        "Company Name": " alpha  dental ",
                        "Company Address": "123   Main St, Austin, TX",
                        "Phone Number": "",
                        "Website": "",
                        "Google Review Rating": 4.7,
                        "Google Review Count": 12,
                        "Google Maps URL": "https://maps.google.com/?cid=111",
                    },
                    {
                        "Company Name": "Gamma Clinic",
                        "Company Address": "789 Pine Rd, Austin, TX",
                        "Phone Number": "",
                        "Website": "",
                        "Google Review Rating": 4.9,
                        "Google Review Count": 21,
                        "Google Maps URL": "https://maps.google.com/?cid=333",
                    },
                ]
            )

            scraper.process_search("dentists", str(output_path), max_results=20, append=True)
            result_df = pd.read_csv(output_path)

            self.assertEqual(len(result_df), 3)
            self.assertEqual((result_df["Company Name"] == "Gamma Clinic").sum(), 1)
            self.assertEqual((result_df["Company Name"].str.strip().str.lower() == "alpha dental").sum(), 1)


if __name__ == "__main__":
    unittest.main()
