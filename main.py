#!/usr/bin/env python3
"""Google Maps Review Scraper - Enrich business leads with review data."""
import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from config import Config


class GoogleMapsReviewScraper:
    """Scraper to enrich business data with Google Maps reviews."""

    def __init__(self):
        """Initialize the scraper with Google Maps API key."""
        Config.validate()
        self.api_key = Config.GOOGLE_MAPS_API_KEY
        self.error_log = []
        self.base_url = "https://places.googleapis.com/v1/places"

    def find_column(self, df, column_name):
        """
        Find column in DataFrame with flexible matching.

        Args:
            df: pandas DataFrame
            column_name: Column name to search for

        Returns:
            Actual column name from DataFrame or None
        """
        # Normalize the search term
        normalized_search = column_name.lower().replace('_', ' ').replace('-', ' ').strip()

        for col in df.columns:
            normalized_col = col.lower().replace('_', ' ').replace('-', ' ').strip()
            if normalized_col == normalized_search:
                return col

        return None

    def search_place(self, business_name, business_address):
        """
        Search for a business on Google Maps using the new Places API.

        Args:
            business_name: Name of the business
            business_address: Address of the business

        Returns:
            tuple: (place_id, error_message) - place_id if found, else None with error
        """
        try:
            # Combine name and address for better search results
            query = f"{business_name}, {business_address}"

            # Use new Places API Text Search
            url = f"{self.base_url}:searchText"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName"
            }
            data = {
                "textQuery": query
            }

            response = requests.post(url, json=data, headers=headers)
            result = response.json()

            if response.status_code == 200 and 'places' in result and result['places']:
                # Return the place ID (format: places/ChIJ...)
                return result['places'][0]['id'], None
            elif response.status_code == 200 and 'places' not in result:
                return None, "Business not found on Google Maps"
            else:
                error_msg = result.get('error', {}).get('message', f"HTTP {response.status_code}")
                return None, f"API error: {error_msg}"

        except Exception as e:
            return None, f"Exception during search: {str(e)}"

    def get_place_details(self, place_id):
        """
        Get review count, rating, and Google Maps URL for a place using the new Places API.

        Args:
            place_id: Google Maps place ID (format: places/ChIJ...)

        Returns:
            tuple: (rating, review_count, maps_url, error_message)
        """
        try:
            # Use new Places API Place Details
            url = f"{self.base_url}/{place_id}"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "rating,userRatingCount,googleMapsUri"
            }

            response = requests.get(url, headers=headers)
            result = response.json()

            if response.status_code == 200:
                rating = result.get('rating')
                review_count = result.get('userRatingCount')
                maps_url = result.get('googleMapsUri')
                return rating, review_count, maps_url, None
            else:
                error_msg = result.get('error', {}).get('message', f"HTTP {response.status_code}")
                return None, None, None, f"API error: {error_msg}"

        except Exception as e:
            return None, None, None, f"Exception getting details: {str(e)}"

    def enrich_business(self, business_name, business_address):
        """
        Enrich a single business with Google Maps review data.

        Args:
            business_name: Name of the business
            business_address: Address of the business

        Returns:
            dict: {'rating': float, 'review_count': int, 'maps_url': str, 'error': str}
        """
        # Add delay to avoid rate limiting
        time.sleep(Config.REQUEST_DELAY)

        # Search for the place
        place_id, error = self.search_place(business_name, business_address)

        if error:
            return {'rating': None, 'review_count': None, 'maps_url': None, 'error': error}

        # Get place details
        rating, review_count, maps_url, error = self.get_place_details(place_id)

        if error:
            return {'rating': None, 'review_count': None, 'maps_url': None, 'error': error}

        return {'rating': rating, 'review_count': review_count, 'maps_url': maps_url, 'error': None}

    def get_place_url_only(self, business_name, business_address):
        """
        Search for a place and return only the Google Maps URL.
        Used when rating/count already exist but URL is missing.

        Args:
            business_name: Name of the business
            business_address: Address of the business

        Returns:
            tuple: (maps_url, error_message)
        """
        # Add delay to avoid rate limiting
        time.sleep(Config.REQUEST_DELAY)

        # Search for the place
        place_id, error = self.search_place(business_name, business_address)
        if error:
            return None, error

        # Fetch only the URL
        try:
            url = f"{self.base_url}/{place_id}"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "googleMapsUri"
            }
            response = requests.get(url, headers=headers)
            result = response.json()

            if response.status_code == 200:
                return result.get('googleMapsUri'), None
            else:
                error_msg = result.get('error', {}).get('message', f"HTTP {response.status_code}")
                return None, f"API error: {error_msg}"
        except Exception as e:
            return None, f"Exception getting URL: {str(e)}"

    def process_csv(self, input_path, output_path):
        """
        Process CSV file and enrich with Google Maps review data.

        Args:
            input_path: Path to input CSV file
            output_path: Path to output CSV file
        """
        # Read CSV
        print(f"Reading CSV from: {input_path}")
        try:
            df = pd.read_csv(input_path)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)

        print(f"Found {len(df)} rows")

        # Find required columns - try multiple variations
        business_name_col = self.find_column(df, 'Business Name') or self.find_column(df, 'Company Name')
        business_address_col = self.find_column(df, 'Business Address') or self.find_column(df, 'Company Address')

        if not business_name_col:
            print("Error: Could not find 'Business Name' or 'Company Name' column in CSV")
            print(f"Available columns: {', '.join(df.columns)}")
            sys.exit(1)

        if not business_address_col:
            print("Error: Could not find 'Business Address' or 'Company Address' column in CSV")
            print(f"Available columns: {', '.join(df.columns)}")
            sys.exit(1)

        print(f"Using columns: '{business_name_col}' and '{business_address_col}'")

        # Check for existing enrichment columns (case-insensitive)
        existing_rating_col = self.find_column(df, 'Google Review Rating')
        existing_count_col = self.find_column(df, 'Google Review Count')
        existing_url_col = self.find_column(df, 'Google Maps URL')

        # Use existing column names or create new ones
        rating_col = existing_rating_col or 'Google Review Rating'
        count_col = existing_count_col or 'Google Review Count'
        url_col = existing_url_col or 'Google Maps URL'

        # Only add columns if they don't exist
        if not existing_rating_col:
            df[rating_col] = None
        if not existing_count_col:
            df[count_col] = None
        if not existing_url_col:
            df[url_col] = None

        # Track statistics
        skipped_complete = 0
        url_only_fetched = 0
        full_fetched = 0

        # Process each business
        print("\nProcessing businesses...")
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Enriching data"):
            business_name = row[business_name_col]
            business_address = row[business_address_col]

            # Skip if either field is empty
            if pd.isna(business_name) or pd.isna(business_address):
                self.error_log.append({
                    'row': idx + 2,  # +2 for header and 0-indexing
                    'business_name': business_name,
                    'business_address': business_address,
                    'error': 'Missing business name or address',
                    'timestamp': datetime.now().isoformat()
                })
                continue

            # Check what data already exists for this row
            existing_rating = row.get(rating_col)
            existing_count = row.get(count_col)
            existing_url = row.get(url_col)

            # Determine what data is valid (not empty, not NaN, not "Not Found")
            def is_valid(val):
                if pd.isna(val):
                    return False
                if isinstance(val, str) and val.strip() in ('', 'Not Found'):
                    return False
                return True

            has_rating = is_valid(existing_rating)
            has_count = is_valid(existing_count)
            has_url = is_valid(existing_url)

            # Skip if all data already exists
            if has_rating and has_count and has_url:
                skipped_complete += 1
                continue

            # If rating and count exist but URL is missing, fetch only URL
            if has_rating and has_count and not has_url:
                url_only_fetched += 1
                maps_url, error = self.get_place_url_only(business_name, business_address)
                if error:
                    self.error_log.append({
                        'row': idx + 2,
                        'business_name': business_name,
                        'business_address': business_address,
                        'error': error,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    df.at[idx, url_col] = maps_url
                continue

            # Otherwise, fetch all data
            full_fetched += 1
            result = self.enrich_business(business_name, business_address)

            if result['error']:
                self.error_log.append({
                    'row': idx + 2,
                    'business_name': business_name,
                    'business_address': business_address,
                    'error': result['error'],
                    'timestamp': datetime.now().isoformat()
                })
            else:
                df.at[idx, rating_col] = result['rating']
                df.at[idx, count_col] = result['review_count']
                df.at[idx, url_col] = result['maps_url']

        # Save enriched CSV
        print(f"\nSaving enriched data to: {output_path}")
        df.to_csv(output_path, index=False)

        # Save error log if there were errors
        if self.error_log:
            error_log_path = Path(output_path).parent / 'error_log.csv'
            print(f"Saving error log to: {error_log_path}")

            with open(error_log_path, 'w', newline='', encoding='utf-8') as f:
                if self.error_log:
                    writer = csv.DictWriter(f, fieldnames=['row', 'business_name', 'business_address', 'error', 'timestamp'])
                    writer.writeheader()
                    writer.writerows(self.error_log)

            print(f"\nCompleted with {len(self.error_log)} errors (see error_log.csv)")
        else:
            print("\nCompleted successfully with no errors!")

        # Summary
        successful = len(df) - len(self.error_log)
        print(f"\nSummary:")
        print(f"  Total businesses: {len(df)}")
        print(f"  Skipped (already complete): {skipped_complete}")
        print(f"  URL only fetched: {url_only_fetched}")
        print(f"  Full data fetched: {full_fetched}")
        print(f"  Successfully enriched: {successful}")
        print(f"  Failed: {len(self.error_log)}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Enrich business leads with Google Maps review data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv output.csv
  %(prog)s leads.csv enriched_leads.csv

Requirements:
  - Google Maps API key in .env file
  - CSV file with 'Business Name' and 'Business Address' columns
        """
    )

    parser.add_argument(
        'input_csv',
        help='Path to input CSV file'
    )

    parser.add_argument(
        'output_csv',
        help='Path to output CSV file'
    )

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.input_csv).exists():
        print(f"Error: Input file not found: {args.input_csv}")
        sys.exit(1)

    # Create scraper and process
    scraper = GoogleMapsReviewScraper()
    scraper.process_csv(args.input_csv, args.output_csv)


if __name__ == '__main__':
    main()
