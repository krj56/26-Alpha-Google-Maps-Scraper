#!/usr/bin/env python3
"""Google Maps Review Scraper - Enrich business leads with review data."""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from config import Config


class WebsiteEnricher:
    """Extracts social links and content from business websites."""

    SOCIAL_PATTERNS = {
        'LinkedIn URL': [
            r'linkedin\.com/company/[\w-]+',
            r'linkedin\.com/in/[\w-]+'
        ],
        'Facebook URL': [
            r'facebook\.com/[\w.-]+',
            r'fb\.com/[\w.-]+'
        ],
        'Instagram URL': [
            r'instagram\.com/[\w._]+',
        ],
        'Twitter URL': [
            r'twitter\.com/[\w_]+',
            r'x\.com/[\w_]+'
        ]
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; LeadEnricher/1.0)'
        })

    def extract_social_links(self, html_content):
        """Find social media links in HTML content."""
        soup = BeautifulSoup(html_content, 'lxml')
        links = {}

        # Find all anchor tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            for platform, patterns in self.SOCIAL_PATTERNS.items():
                if platform not in links:
                    for pattern in patterns:
                        if re.search(pattern, href, re.IGNORECASE):
                            # Normalize URL
                            if not href.startswith('http'):
                                href = 'https://' + href.lstrip('/')
                            links[platform] = href
                            break

        return links

    def extract_content(self, html_content):
        """Extract title and description from website."""
        soup = BeautifulSoup(html_content, 'lxml')

        # Get title
        title = ''
        if soup.title:
            title = soup.title.string.strip() if soup.title.string else ''

        # Get meta description
        description = ''
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc['content'].strip()

        # Fallback: get first paragraph if no meta description
        if not description:
            first_p = soup.find('p')
            if first_p:
                description = first_p.get_text().strip()[:300]

        return title, description

    def generate_brief(self, title, description, company_name):
        """Generate a research brief from website content."""
        brief = f"{company_name}"
        if description:
            # Clean and truncate description
            clean_desc = ' '.join(description.split())[:200]
            brief = f"{company_name}: {clean_desc}"
        elif title:
            brief = f"{company_name} - {title}"
        return brief

    def fetch_website(self, url, timeout=10):
        """Fetch website content with error handling."""
        if not url or pd.isna(url):
            return None, "No website URL"

        try:
            # Ensure https
            if not url.startswith('http'):
                url = 'https://' + url

            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text, None
        except requests.exceptions.Timeout:
            return None, "Timeout"
        except requests.exceptions.SSLError:
            return None, "SSL Error"
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)[:50]}"

    def enrich_row(self, row):
        """Enrich a single business row with website data."""
        website = row.get('Website', '')
        company_name = row.get('Company Name', '')

        result = {
            'LinkedIn URL': '',
            'Facebook URL': '',
            'Instagram URL': '',
            'Twitter URL': '',
            'Research Brief': ''
        }

        html, error = self.fetch_website(website)
        if error:
            result['Research Brief'] = f"Could not fetch: {error}"
            return result

        # Extract social links
        social_links = self.extract_social_links(html)
        result.update(social_links)

        # Extract content and generate brief
        title, description = self.extract_content(html)
        result['Research Brief'] = self.generate_brief(title, description, company_name)

        return result


class EmailGenerator:
    """Generates personalized cold outreach emails using LLMs."""

    DEFAULT_PROMPT_FILE = Path(__file__).parent / 'default_email_prompt.txt'

    def __init__(self, model, api_key, prompt_file=None):
        self.model = model
        self.api_key = api_key
        self.prompt_template = self._load_prompt(prompt_file)

    def _load_prompt(self, prompt_file=None):
        """Load prompt template from file."""
        path = Path(prompt_file) if prompt_file else self.DEFAULT_PROMPT_FILE
        if not path.exists():
            print(f"Error: Prompt file not found: {path}")
            sys.exit(1)
        return path.read_text(encoding='utf-8')

    def _build_prompt(self, row, product_description):
        """Build the final prompt by filling in variables from lead data."""
        def safe_val(val):
            if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                return 'N/A'
            return str(val).strip()

        return self.prompt_template.format(
            company_name=safe_val(row.get('Company Name', '')),
            company_address=safe_val(row.get('Company Address', '')),
            company_phone=safe_val(row.get('Company Phone', '')),
            website=safe_val(row.get('Website', '')),
            rating=safe_val(row.get('Google Review Rating', '')),
            review_count=safe_val(row.get('Google Review Count', '')),
            research_brief=safe_val(row.get('Research Brief', '')),
            linkedin_url=safe_val(row.get('LinkedIn URL', '')),
            facebook_url=safe_val(row.get('Facebook URL', '')),
            instagram_url=safe_val(row.get('Instagram URL', '')),
            twitter_url=safe_val(row.get('Twitter URL', '')),
            product_description=product_description
        )

    def generate_email(self, row, product_description):
        """Generate a personalized email for a single lead."""
        import litellm

        prompt = self._build_prompt(row, product_description)

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                max_tokens=500,
                temperature=0.7
            )

            return response.choices[0].message.content.strip(), None

        except Exception as e:
            return None, f"LLM error: {str(e)[:100]}"


class GoogleMapsReviewScraper:
    """Scraper to enrich business data with Google Maps reviews."""

    def __init__(self, api_key=None):
        """Initialize the scraper with an explicit or configured Google Maps API key."""
        if api_key:
            self.api_key = api_key
        else:
            Config.validate()
            self.api_key = Config.GOOGLE_MAPS_API_KEY
        self.error_log = []
        self.base_url = "https://places.googleapis.com/v1/places"
        self.session = requests.Session()

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

            response = self.session.post(url, json=data, headers=headers, timeout=Config.REQUEST_TIMEOUT)
            result = response.json()

            if response.status_code == 200 and 'places' in result and result['places']:
                # Return the place ID (format: places/ChIJ...)
                return result['places'][0]['id'], None
            elif response.status_code == 200:
                # Handles both missing 'places' key and empty list
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

            response = self.session.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
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
            response = self.session.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
            result = response.json()

            if response.status_code == 200:
                return result.get('googleMapsUri'), None
            else:
                error_msg = result.get('error', {}).get('message', f"HTTP {response.status_code}")
                return None, f"API error: {error_msg}"
        except Exception as e:
            return None, f"Exception getting URL: {str(e)}"

    def search_businesses(self, query, max_results=20, location=None, radius=None):
        """
        Search Google Maps for businesses matching a query.

        Args:
            query: Search query (e.g., "dentists" or "dentists in Austin TX")
            max_results: Maximum number of results to return
            location: Tuple of (latitude, longitude) for location-based search
            radius: Search radius in meters (used with location)

        Returns:
            list: List of business dictionaries
        """
        businesses = []
        url = f"{self.base_url}:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,nextPageToken"
        }

        data = {"textQuery": query, "pageSize": min(max_results, 20)}

        # Add location bias if coordinates provided
        if location and radius:
            lat, lng = location
            data["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius
                }
            }

        print(f"\nSearching for: {query}")
        if location:
            radius_miles = radius / 1609.34 if radius else 0
            print(f"Location: {location[0]}, {location[1]} (radius: {radius_miles:.1f} miles)")
        print(f"Max results: {max_results}")

        while len(businesses) < max_results:
            time.sleep(Config.REQUEST_DELAY)
            try:
                response = self.session.post(url, json=data, headers=headers, timeout=Config.REQUEST_TIMEOUT)
                result = response.json()
            except Exception as e:
                print(f"Request error: {e}")
                break

            if response.status_code != 200:
                error_msg = result.get('error', {}).get('message', f"HTTP {response.status_code}")
                print(f"API error: {error_msg}")
                break

            if 'places' not in result:
                if len(businesses) == 0:
                    print("No businesses found for this search.")
                break

            for place in result['places']:
                businesses.append({
                    'Company Name': place.get('displayName', {}).get('text', ''),
                    'Company Address': place.get('formattedAddress', ''),
                    'Phone Number': place.get('nationalPhoneNumber', ''),
                    'Website': place.get('websiteUri', ''),
                    'Google Review Rating': place.get('rating'),
                    'Google Review Count': place.get('userRatingCount'),
                    'Google Maps URL': place.get('googleMapsUri', '')
                })
                if len(businesses) >= max_results:
                    break

            print(f"  Found {len(businesses)} businesses so far...")

            # Handle pagination
            if 'nextPageToken' not in result or len(businesses) >= max_results:
                break
            data['pageToken'] = result['nextPageToken']

        return businesses

    def process_search(self, query, output_path, max_results=20, append=False, location=None, radius=None, enrich_web=False):
        """
        Search Google Maps and save results to CSV.

        Args:
            query: Search query
            output_path: Path to output CSV file
            max_results: Maximum results to fetch
            append: If True, append to existing file
            location: Tuple of (latitude, longitude) for location-based search
            radius: Search radius in meters
            enrich_web: If True, also scrape websites for social links and research brief
        """
        businesses = self.search_businesses(query, max_results, location, radius)

        if not businesses:
            return

        df = pd.DataFrame(businesses)

        # Handle append mode
        if append and Path(output_path).exists():
            existing_df = pd.read_csv(output_path)
            new_df = df

            if 'Google Maps URL' in existing_df.columns:
                # Preferred dedupe strategy when URL is available.
                existing_urls = set(existing_df['Google Maps URL'].dropna().astype(str).str.strip())
                new_df = df[~df['Google Maps URL'].fillna('').astype(str).str.strip().isin(existing_urls)]
            else:
                # Fallback dedupe strategy for files without Google Maps URL.
                existing_name_col = self.find_column(existing_df, 'Company Name') or self.find_column(existing_df, 'Business Name')
                existing_address_col = self.find_column(existing_df, 'Company Address') or self.find_column(existing_df, 'Business Address')

                if existing_name_col and existing_address_col:
                    def normalize(val):
                        if pd.isna(val):
                            return ''
                        return re.sub(r'\s+', ' ', str(val)).strip().lower()

                    existing_keys = set(
                        zip(
                            existing_df[existing_name_col].map(normalize),
                            existing_df[existing_address_col].map(normalize)
                        )
                    )
                    new_keys = list(zip(df['Company Name'].map(normalize), df['Company Address'].map(normalize)))
                    keep_mask = [key not in existing_keys for key in new_keys]
                    new_df = df[keep_mask]
                    print("\nAppend mode: 'Google Maps URL' not found, deduping by name + address")
                else:
                    print("\nAppend mode: could not identify name/address columns, skipping dedupe")

            new_count = len(new_df)
            df = pd.concat([existing_df, new_df], ignore_index=True)
            print(f"\nAppending {new_count} new businesses to existing {len(existing_df)} rows")
        else:
            print(f"\nFound {len(businesses)} businesses")

        # Website enrichment
        if enrich_web:
            df = self.enrich_with_website_data(df)

        df.to_csv(output_path, index=False)
        print(f"Saved to: {output_path}")
        print(f"Total rows in file: {len(df)}")

    def enrich_with_website_data(self, df):
        """
        Add website data (social links, research brief) to DataFrame.

        Args:
            df: pandas DataFrame with 'Website' and 'Company Name' columns

        Returns:
            DataFrame with added columns for social links and research brief
        """
        enricher = WebsiteEnricher()

        # New columns to add
        new_columns = [
            'LinkedIn URL', 'Facebook URL', 'Instagram URL', 'Twitter URL',
            'Research Brief'
        ]

        # Initialize columns if not present
        for col in new_columns:
            if col not in df.columns:
                df[col] = ''

        print("\nEnriching with website data...")

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Fetching websites"):
            # Skip if already enriched (has Research Brief that's not an error)
            existing_brief = row.get('Research Brief')
            if existing_brief and pd.notna(existing_brief) and not str(existing_brief).startswith('Could not fetch'):
                continue

            # Skip if no website
            if not row.get('Website') or pd.isna(row.get('Website')):
                df.at[idx, 'Research Brief'] = 'No website available'
                continue

            result = enricher.enrich_row(row)
            for col, value in result.items():
                df.at[idx, col] = value

            time.sleep(Config.WEBSITE_SCRAPE_DELAY)

        return df

    def generate_emails(self, df, model, api_key, product_description, prompt_file=None):
        """Generate personalized emails for each lead in DataFrame."""
        generator = EmailGenerator(model, api_key, prompt_file)

        if 'Generated Email' not in df.columns:
            df['Generated Email'] = ''

        print("\nGenerating personalized emails...")

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Writing emails"):
            # Skip if already has email
            existing = row.get('Generated Email')
            if existing and pd.notna(existing) and str(existing).strip():
                continue

            email, error = generator.generate_email(row, product_description)
            if error:
                df.at[idx, 'Generated Email'] = f"Error: {error}"
            else:
                df.at[idx, 'Generated Email'] = email

            time.sleep(0.2)  # Light rate limiting

        return df

    def process_csv(self, input_path, output_path):
        """
        Process CSV file and enrich with Google Maps review data.

        Args:
            input_path: Path to input CSV file
            output_path: Path to output CSV file
        """
        self.error_log = []  # Reset for each run
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
            if (pd.isna(business_name) or str(business_name).strip() == '' or
                pd.isna(business_address) or str(business_address).strip() == ''):
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
        description='Google Maps Business Scraper - Enrich leads or search for businesses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enrich existing CSV with Google Maps data
  %(prog)s enrich input.csv output.csv

  # Search Google Maps for businesses
  %(prog)s search "dentists in Austin TX" output.csv

  # Search with location (lat,lng) and radius (miles)
  %(prog)s search "dentists" output.csv --location 30.2672,-97.7431 --radius 10

  # Search and append to existing file
  %(prog)s search "dentists" output.csv --append --limit 50

  # Search with website enrichment (social links + research brief)
  %(prog)s search "dentists" output.csv --enrich-web

  # Enrich existing CSV with website data only
  %(prog)s enrich-web input.csv output.csv

  # Generate personalized emails using AI
  %(prog)s generate-emails leads.csv output.csv --provider openai --model gpt-4o --product "dental marketing software"

  # Legacy mode (backward compatible)
  %(prog)s input.csv output.csv
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Enrich command (current functionality)
    enrich_parser = subparsers.add_parser('enrich', help='Enrich existing CSV with Google Maps data')
    enrich_parser.add_argument('input_csv', help='Input CSV file')
    enrich_parser.add_argument('output_csv', help='Output CSV file')

    # Search command (new)
    search_parser = subparsers.add_parser('search', help='Search Google Maps for businesses')
    search_parser.add_argument('query', help='Search query (e.g., "dentists in Austin TX")')
    search_parser.add_argument('output_csv', help='Output CSV file')
    search_parser.add_argument('--limit', type=int, default=20, help='Max results (default: 20)')
    search_parser.add_argument('--append', action='store_true', help='Append to existing file')
    search_parser.add_argument('--location', help='Lat,Lng coordinates (e.g., "30.2672,-97.7431")')
    search_parser.add_argument('--radius', type=float, default=10, help='Search radius in miles (default: 10)')
    search_parser.add_argument('--enrich-web', action='store_true', dest='enrich_web',
        help='Also scrape websites for social links and research brief')

    # Enrich-web command (website enrichment only)
    enrich_web_parser = subparsers.add_parser('enrich-web',
        help='Enrich existing CSV with website data (social links, research brief)')
    enrich_web_parser.add_argument('input_csv', help='Input CSV file with Website column')
    enrich_web_parser.add_argument('output_csv', help='Output CSV file')

    # Generate-emails command (AI email generation)
    email_parser = subparsers.add_parser('generate-emails',
        help='Generate personalized cold emails using AI')
    email_parser.add_argument('input_csv', help='Input CSV (ideally with enrichments)')
    email_parser.add_argument('output_csv', help='Output CSV with Generated Email column')
    email_parser.add_argument('--provider', required=True,
        choices=['openai', 'anthropic', 'gemini', 'openrouter', 'perplexity'],
        help='LLM provider (determines which env var to check for API key)')
    email_parser.add_argument('--model', required=True,
        help='Model name (e.g., gpt-4o, claude-sonnet-4-5-20250929)')
    email_parser.add_argument('--api-key', dest='llm_api_key', default=None,
        help='LLM API key (or set via env var)')
    email_parser.add_argument('--product', required=True,
        help='Description of your product/service')
    email_parser.add_argument('--prompt-file', dest='prompt_file', default=None,
        help='Path to custom prompt template file (default: default_email_prompt.txt)')

    args = parser.parse_args()

    # Handle no command (backward compatibility)
    if args.command is None:
        # Check if old-style args (2 positional = enrich mode)
        if len(sys.argv) == 3 and not sys.argv[1].startswith('-'):
            input_file = sys.argv[1]
            output_file = sys.argv[2]
            if not Path(input_file).exists():
                print(f"Error: Input file not found: {input_file}")
                sys.exit(1)
            scraper = GoogleMapsReviewScraper()
            scraper.process_csv(input_file, output_file)
            return
        parser.print_help()
        sys.exit(1)

    scraper = GoogleMapsReviewScraper()

    if args.command == 'enrich':
        if not Path(args.input_csv).exists():
            print(f"Error: Input file not found: {args.input_csv}")
            sys.exit(1)
        scraper.process_csv(args.input_csv, args.output_csv)

    elif args.command == 'search':
        # Parse location if provided
        location = None
        radius_meters = None
        if args.location:
            try:
                lat, lng = map(float, args.location.split(','))
                location = (lat, lng)
                if args.radius <= 0:
                    print("Error: Radius must be greater than 0")
                    sys.exit(1)
                # Convert miles to meters (1 mile = 1609.34 meters)
                radius_meters = int(args.radius * 1609.34)
            except ValueError:
                print("Error: Location must be in format 'lat,lng' (e.g., '30.2672,-97.7431')")
                sys.exit(1)

        scraper.process_search(
            args.query,
            args.output_csv,
            args.limit,
            args.append,
            location,
            radius_meters,
            args.enrich_web
        )

    elif args.command == 'enrich-web':
        if not Path(args.input_csv).exists():
            print(f"Error: Input file not found: {args.input_csv}")
            sys.exit(1)
        print(f"Reading CSV from: {args.input_csv}")
        try:
            df = pd.read_csv(args.input_csv)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)
        print(f"Found {len(df)} rows")
        df = scraper.enrich_with_website_data(df)
        df.to_csv(args.output_csv, index=False)
        print(f"\nSaved to: {args.output_csv}")

    elif args.command == 'generate-emails':
        if not Path(args.input_csv).exists():
            print(f"Error: Input file not found: {args.input_csv}")
            sys.exit(1)

        # Get API key from arg or environment
        llm_api_key = args.llm_api_key or os.getenv(f'{args.provider.upper()}_API_KEY')
        if not llm_api_key:
            print(f"Error: No API key. Use --api-key or set {args.provider.upper()}_API_KEY env var")
            sys.exit(1)

        print(f"Reading CSV from: {args.input_csv}")
        try:
            df = pd.read_csv(args.input_csv)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)
        print(f"Found {len(df)} rows")

        df = scraper.generate_emails(df, args.model, llm_api_key,
                                      args.product, args.prompt_file)
        df.to_csv(args.output_csv, index=False)
        print(f"\nSaved to: {args.output_csv}")


if __name__ == '__main__':
    main()
