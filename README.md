# Google Maps Business Scraper

A powerful tool to find and enrich business leads using Google Maps data.

**Perfect for:** Sales teams, marketers, and business development professionals who want to find leads or enrich existing data with Google reviews.

## What This Tool Does

**Four Modes:**

### 1. Search Mode
Search Google Maps directly for businesses and export to CSV:
```bash
python3 main.py search "dentists in Austin TX" leads.csv
```

### 2. Enrich Mode
Take an existing CSV with business names/addresses and add Google data:
```bash
python3 main.py enrich input.csv output.csv
```

### 3. Website Enrichment Mode
Add social media links and research briefs by scraping business websites:
```bash
python3 main.py search "dentists in Austin TX" leads.csv --enrich-web
```

### 4. AI Email Generation Mode (NEW!)
Generate personalized cold outreach emails using any LLM (OpenAI, Anthropic, Gemini, etc.):
```bash
python3 main.py generate-emails leads.csv output.csv \
  --provider openai --model gpt-4o \
  --product "dental marketing software that helps practices get more patients"
```

**Data Collected:**
- Company Name
- Company Address
- Phone Number
- Website
- Google Review Rating (e.g., 4.5 stars)
- Google Review Count (e.g., 127 reviews)
- Google Maps URL (direct link)
- LinkedIn URL (with `--enrich-web`)
- Facebook URL (with `--enrich-web`)
- Instagram URL (with `--enrich-web`)
- Twitter URL (with `--enrich-web`)
- Research Brief (with `--enrich-web`)
- Generated Email (with `generate-emails`)

## Quick Start (5 Steps)

### Step 1: Install Python

**Mac users:** Python 3 is usually pre-installed. Open Terminal and type:
```bash
python3 --version
```
If you see a version number (like `Python 3.11.4`), you're good! If not, download Python from [python.org](https://www.python.org/downloads/).

**Windows users:** Download and install Python from [python.org](https://www.python.org/downloads/). During installation, **check the box that says "Add Python to PATH"**.

### Step 2: Download This Project

Click the green **"Code"** button on this GitHub page, then click **"Download ZIP"**. Unzip the folder somewhere you can find it (like your Desktop).

### Step 3: Install Required Packages

Open Terminal (Mac) or Command Prompt (Windows) and navigate to the project folder:

**Mac:**
```bash
cd ~/Desktop/google-maps-scraper
pip3 install -r requirements.txt
```

**Windows:**
```bash
cd Desktop\google-maps-scraper
pip install -r requirements.txt
```

### Step 4: Get Your Google Maps API Key

This is the most important step. You need a Google API key to access Google Maps data.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click **"Select a project"** at the top, then **"New Project"**
4. Name it anything (like "Maps Scraper") and click **Create**
5. Wait for it to create, then make sure it's selected
6. Go to **APIs & Services** > **Library** (in the left menu)
7. Search for **"Places API (New)"** and click on it
8. Click the blue **"Enable"** button
9. Go to **APIs & Services** > **Credentials** (in the left menu)
10. Click **"+ Create Credentials"** > **"API Key"**
11. Copy your new API key (it looks like `AIzaSyB...`)

**Important:** Google gives you $200/month in free credits. For most users, this is more than enough. After free credits, it costs about $0.03 per business looked up.

### Step 5: Set Up Your API Key

1. In the project folder, find the file called `.env.example`
2. Make a copy of it and rename the copy to `.env` (just `.env`, no other name)
3. Open `.env` in any text editor (like Notepad or TextEdit)
4. Replace `your_api_key_here` with your actual API key:
   ```
   GOOGLE_MAPS_API_KEY=AIzaSyB1234567890abcdefg
   ```
5. Save the file

## How to Use

### Option 1: Search Mode (Find New Leads)

Search Google Maps for businesses and save to CSV:

```bash
# Basic search
python3 main.py search "dentists in Austin TX" dentists.csv

# Limit results (default is 20)
python3 main.py search "coffee shops in Seattle" coffee.csv --limit 50

# Search by location (lat,lng) with radius in miles
python3 main.py search "dentists" dentists.csv --location 30.2672,-97.7431 --radius 15

# Append to existing file (won't duplicate)
python3 main.py search "dentists in Round Rock TX" dentists.csv --append
```

**Output columns:** Company Name, Address, Phone, Website, Rating, Review Count, Google Maps URL

### Option 2: Website Enrichment (Social Links + Research Brief)

Add social media links and website summaries to your leads:

```bash
# Search and enrich in one step
python3 main.py search "dentists in Austin TX" leads.csv --enrich-web

# Or enrich an existing CSV with website data only
python3 main.py enrich-web leads.csv enriched_leads.csv
```

**Additional columns added:**
- LinkedIn URL, Facebook URL, Instagram URL, Twitter URL
- Research Brief (summary of what the business does)

**Note:** Website enrichment adds ~0.5 seconds per business to respect rate limits.

### Option 3: AI Email Generation (Personalized Cold Outreach)

Generate personalized cold emails for each lead using any LLM provider:

```bash
# Generate emails with OpenAI
python3 main.py generate-emails leads.csv leads_with_emails.csv \
  --provider openai --model gpt-4o \
  --product "dental marketing software that helps practices get more patients"

# Use Anthropic instead
python3 main.py generate-emails leads.csv output.csv \
  --provider anthropic --model claude-sonnet-4-5-20250929 \
  --product "commercial cleaning services for offices"

# Use a custom prompt template
python3 main.py generate-emails leads.csv output.csv \
  --provider openai --model gpt-4o \
  --product "dental marketing software" \
  --prompt-file my_prompt.txt
```

**Supported LLM providers:** OpenAI, Anthropic, Google Gemini, OpenRouter, Perplexity (and 100+ more via litellm)

**API key:** Pass with `--api-key` or set via environment variable (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)

**Custom prompts:** Edit `default_email_prompt.txt` or create your own prompt file with `{variable}` placeholders. See the file for the full list of available variables.

**Cost:** ~$0.005 per email with GPT-4o, ~100 emails for $0.50

### Option 4: Enrich Mode (Add Data to Existing CSV)

Take a CSV with business names/addresses and add Google data:

```bash
# Enrich existing CSV
python3 main.py enrich leads.csv enriched_leads.csv

# Or use legacy syntax (backward compatible)
python3 main.py leads.csv enriched_leads.csv
```

Your input CSV needs columns:
- **Company Name** (or "Business Name")
- **Company Address** (or "Business Address")

Example input CSV:
```
Company Name,Company Address,Contact Email
Starbucks,"1912 Pike Pl, Seattle, WA 98101",contact@example.com
Tesla HQ,"1 Tesla Rd, Austin, TX 78725",info@example.com
```

### What You'll Get

**Search mode** creates a fresh CSV with all business data.

**Enrich mode** adds three new columns to your existing data:
- `Google Review Rating`
- `Google Review Count`
- `Google Maps URL`

If any businesses couldn't be found, they'll be listed in `error_log.csv`.

### Tip for filenames with spaces

Use backslashes before spaces:
```bash
python3 main.py search "dentists" my\ leads\ file.csv
```

## Smart Features

- **AI email generation:** Use `generate-emails` to write personalized cold outreach emails using any LLM provider
- **Customizable prompts:** Edit `default_email_prompt.txt` or use `--prompt-file` for full control over email style
- **Website enrichment:** Use `--enrich-web` to scrape websites for social media links and generate research briefs
- **Append mode:** Build up a lead database over time - use `--append` to add new results without duplicates
- **Location search:** Search by coordinates + radius (in miles) to find businesses in specific areas
- **Skips completed rows:** If you run enrich again on an already-enriched file, it won't re-fetch existing data
- **URL-only mode:** If you have ratings but no URLs, it only fetches the missing URLs (saves API costs)
- **Flexible column names:** Works with "Business Name" or "Company Name" (same for address)
- **Error logging:** Failed lookups are saved separately so you can review them
- **Pagination:** Automatically fetches multiple pages to get large result sets (50, 100+ results)

## Troubleshooting

### "command not found: pip"
Use `pip3` instead of `pip`:
```bash
pip3 install -r requirements.txt
```

### "GOOGLE_MAPS_API_KEY not found"
Make sure you:
1. Created a `.env` file (not `.env.example`)
2. Added your API key after the `=` sign
3. Saved the file

### "Could not find 'Business Name' column"
Your CSV needs a column named either:
- "Business Name" or "Company Name"
- "Business Address" or "Company Address"

Check your CSV headers match one of these.

### "Business not found on Google Maps"
This happens when:
- The business name or address is incomplete
- The business isn't listed on Google Maps
- Try adding more address details (city, state, ZIP)

### Stuck in `dquote>` prompt
You probably copied "smart quotes" from somewhere. Press `Ctrl+C` to cancel, then retype the command manually (don't copy-paste from documents).

## Cost Information

- Google provides **$200/month free** API credits
- Each business lookup costs approximately $0.03
- With free credits, you can look up ~6,000 businesses/month for free
- Monitor your usage at [Google Cloud Console](https://console.cloud.google.com/)

## Need Help?

1. Check the Troubleshooting section above
2. Look at `error_log.csv` for specific error messages
3. Make sure your API key is valid and Places API is enabled

## License

Free to use for personal and commercial purposes.
