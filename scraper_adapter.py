"""
Streamlit adapter for Google Maps Review Scraper.

This module provides a bridge between the CLI-based scraper and the Streamlit UI.
It bypasses environment variable validation and provides in-memory DataFrame operations.
"""

import pandas as pd
import time

# Import main module components
from main import GoogleMapsReviewScraper, WebsiteEnricher, EmailGenerator


def _search_places_compat(scraper, search_query, max_results):
    """
    Call the scraper search method with compatibility across interfaces.

    Newer scraper versions expose `search_businesses`, while older ones used
    `search_places`.
    """
    if hasattr(scraper, 'search_businesses'):
        return scraper.search_businesses(search_query, max_results=max_results)
    if hasattr(scraper, 'search_places'):
        return scraper.search_places(search_query, max_results)
    raise AttributeError("Scraper is missing both search_businesses and search_places methods")


def _get_place_field(place, *field_names):
    """Return first present, non-None field value from candidate names."""
    for field_name in field_names:
        if field_name in place and place[field_name] is not None:
            return place[field_name]
    return ''


def _has_value(value):
    """True when a value is not NaN/empty string."""
    if pd.isna(value):
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def create_scraper(api_key):
    """
    Create a GoogleMapsReviewScraper instance bypassing Config validation.

    Args:
        api_key: Google Maps API key

    Returns:
        GoogleMapsReviewScraper instance
    """
    return GoogleMapsReviewScraper(api_key=api_key)


def create_email_generator(model, api_key, prompt_text):
    """
    Create an EmailGenerator with in-memory prompt template.

    Args:
        model: LLM model name
        api_key: LLM API key
        prompt_text: Prompt template text (not file path)

    Returns:
        EmailGenerator instance
    """
    generator = EmailGenerator.__new__(EmailGenerator)
    generator.model = model
    generator.api_key = api_key
    generator.prompt_template = prompt_text
    return generator


def search_places(scraper, search_query, max_results=20):
    """
    Search for places using Google Maps API.

    Args:
        scraper: GoogleMapsReviewScraper instance
        search_query: Search query string
        max_results: Maximum number of results

    Returns:
        pandas DataFrame with search results
    """
    results = _search_places_compat(scraper, search_query, max_results)

    df = pd.DataFrame([{
        'Company Name': _get_place_field(r, 'Company Name', 'name'),
        'Company Address': _get_place_field(r, 'Company Address', 'address'),
        'Company Phone': _get_place_field(r, 'Company Phone', 'Phone Number', 'phone', 'nationalPhoneNumber'),
        'Website': _get_place_field(r, 'Website', 'website', 'websiteUri'),
        'Google Review Rating': _get_place_field(r, 'Google Review Rating', 'rating'),
        'Google Review Count': _get_place_field(r, 'Google Review Count', 'review_count', 'userRatingCount')
    } for r in results])

    return df


def enrich_with_reviews(scraper, df, progress_callback=None):
    """
    Enrich DataFrame with Google review data (row by row for progress tracking).

    Args:
        scraper: GoogleMapsReviewScraper instance
        df: pandas DataFrame with place data
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        Enriched DataFrame
    """
    if 'Google Review Rating' not in df.columns:
        df['Google Review Rating'] = ''
    if 'Google Review Count' not in df.columns:
        df['Google Review Count'] = ''

    total = len(df)

    for idx, row in df.iterrows():
        # Skip if already has reviews
        rating = row.get('Google Review Rating')
        count = row.get('Google Review Count')

        if _has_value(rating) and _has_value(count):
            if progress_callback:
                progress_callback(idx + 1, total)
            continue

        # Search for place to get review data
        place_name = row.get('Company Name', '')
        address = row.get('Company Address', '')

        if place_name:
            results = _search_places_compat(scraper, f"{place_name} {address}", max_results=1)
            if results:
                place = results[0]
                df.at[idx, 'Google Review Rating'] = _get_place_field(place, 'Google Review Rating', 'rating')
                df.at[idx, 'Google Review Count'] = _get_place_field(place, 'Google Review Count', 'review_count', 'userRatingCount')

        if progress_callback:
            progress_callback(idx + 1, total)

        time.sleep(0.2)  # Rate limiting

    return df


def enrich_with_website_data(df, progress_callback=None):
    """
    Enrich DataFrame with website data (social links + research brief).

    Args:
        df: pandas DataFrame with website URLs
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        Enriched DataFrame
    """
    enricher = WebsiteEnricher()

    # Add columns if missing
    for col in ['LinkedIn URL', 'Facebook URL', 'Instagram URL', 'Twitter URL', 'Research Brief']:
        if col not in df.columns:
            df[col] = ''

    total = len(df)

    for idx, row in df.iterrows():
        # Skip if already enriched
        existing = row.get('Research Brief')
        if existing and pd.notna(existing) and str(existing).strip() and not str(existing).startswith('Could not'):
            if progress_callback:
                progress_callback(idx + 1, total)
            continue

        # Enrich this row
        result = enricher.enrich_row(row)

        for key, value in result.items():
            df.at[idx, key] = value

        if progress_callback:
            progress_callback(idx + 1, total)

        time.sleep(0.5)  # Rate limiting for website scraping

    return df


def generate_emails(df, generator, product_description, progress_callback=None):
    """
    Generate personalized emails for each lead in DataFrame.

    Args:
        df: pandas DataFrame with lead data
        generator: EmailGenerator instance
        product_description: Product/service description
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        DataFrame with Generated Email column
    """
    if 'Generated Email' not in df.columns:
        df['Generated Email'] = ''

    total = len(df)

    for idx, row in df.iterrows():
        # Skip if already has email
        existing = row.get('Generated Email')
        if existing and pd.notna(existing) and str(existing).strip() and not str(existing).startswith('Error'):
            if progress_callback:
                progress_callback(idx + 1, total)
            continue

        # Generate email
        email, error = generator.generate_email(row, product_description)

        if error:
            df.at[idx, 'Generated Email'] = f"Error: {error}"
        else:
            df.at[idx, 'Generated Email'] = email

        if progress_callback:
            progress_callback(idx + 1, total)

        time.sleep(0.2)  # Rate limiting

    return df


# Default email prompt template
DEFAULT_PROMPT_TEMPLATE = """=== ROLE ===
You are writing a short, personalized cold outreach email to a business owner on behalf of someone who wants to offer them a product or service.

=== RULES ===
- 3-5 sentences maximum
- Reference something SPECIFIC about their business — a detail from the research brief, their review count, or their specialty
- Explain clearly how the product/service helps THIS business specifically (not generic benefits)
- End with a single, low-pressure call to action (e.g., a short call, a reply, a link)
- Sound like a real person, not a marketer — conversational, direct, no fluff
- Do NOT start with "I hope this email finds you well" or "I came across your business"
- Do NOT use words like "thrilled", "excited", "passion", "synergy", "leverage"
- Output ONLY the email body — no subject line, no sign-off, no signature

=== CONTEXT ===
Here is everything we know about this lead:

Company: {company_name}
Location: {company_address}
Phone: {company_phone}
Website: {website}
Google Rating: {rating} ({review_count} reviews)
Research Brief: {research_brief}
LinkedIn: {linkedin_url}
Facebook: {facebook_url}
Instagram: {instagram_url}
Twitter: {twitter_url}

=== PRODUCT/SERVICE ===
{product_description}

=== OUTPUT ===
Write the email now. Only output the email body, nothing else.
"""
