"""Configuration management for Google Maps scraper."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Google Maps API Key (required)
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

    # Search region for better results (optional)
    SEARCH_REGION = os.getenv('SEARCH_REGION', 'US')

    # Request timeout in seconds
    REQUEST_TIMEOUT = 10

    # Delay between API requests (in seconds) to avoid rate limiting
    REQUEST_DELAY = 0.1

    # Delay between website scrape requests (in seconds)
    WEBSITE_SCRAPE_DELAY = 0.5

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        if not cls.GOOGLE_MAPS_API_KEY:
            raise ValueError(
                "GOOGLE_MAPS_API_KEY not found in environment variables.\n"
                "Please create a .env file with your API key.\n"
                "See .env.example for reference."
            )

        if cls.GOOGLE_MAPS_API_KEY == 'your_api_key_here':
            raise ValueError(
                "Please replace 'your_api_key_here' with your actual Google Maps API key in .env file"
            )
