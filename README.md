# Google Maps Review Scraper

Automatically enrich your business lead CSV files with Google Maps ratings, review counts, and direct links to their Google Maps pages.

**Perfect for:** Sales teams, marketers, and business development professionals who want to prioritize leads based on their online reputation.

## What This Tool Does

Give it a CSV file with business names and addresses, and it will add:
- **Google Review Rating** (e.g., 4.5 stars)
- **Google Review Count** (e.g., 127 reviews)
- **Google Maps URL** (direct link to their Google Maps page)

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

### Prepare Your CSV File

Your CSV needs at least two columns:
- **Company Name** (or "Business Name")
- **Company Address** (or "Business Address")

Example CSV:
```
Company Name,Company Address,Contact Email
Starbucks,"1912 Pike Pl, Seattle, WA 98101",contact@example.com
Tesla HQ,"1 Tesla Rd, Austin, TX 78725",info@example.com
```

### Run the Script

Open Terminal/Command Prompt, navigate to the project folder, and run:

**Mac:**
```bash
python3 main.py your_input_file.csv your_output_file.csv
```

**Windows:**
```bash
python main.py your_input_file.csv your_output_file.csv
```

**Example:**
```bash
python3 main.py leads.csv enriched_leads.csv
```

**Tip for filenames with spaces:** Use backslashes before spaces:
```bash
python3 main.py my\ leads\ file.csv enriched\ output.csv
```

### What You'll Get

The script creates a new CSV file with three new columns added:
- `Google Review Rating`
- `Google Review Count`
- `Google Maps URL`

If any businesses couldn't be found, they'll be listed in `error_log.csv`.

## Smart Features

- **Skips completed rows:** If you run it again on an already-enriched file, it won't re-fetch data that's already there
- **URL-only mode:** If you have ratings but no URLs, it only fetches the missing URLs (saves API costs)
- **Flexible column names:** Works with "Business Name" or "Company Name" (same for address)
- **Error logging:** Failed lookups are saved separately so you can review them

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
