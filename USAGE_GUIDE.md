# Complete Guide: How to Use the Restaurant Data Scraper

## Table of Contents
1. [Initial Setup](#initial-setup)
2. [Basic Usage](#basic-usage)
3. [Advanced Usage Scenarios](#advanced-usage-scenarios)
4. [Understanding Your Data](#understanding-your-data)
5. [Exporting to HubSpot](#exporting-to-hubspot)
6. [Tips & Best Practices](#tips--best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Initial Setup

### Step 1: Install Python Dependencies

```bash
# Navigate to the project directory
cd Data-scraper

# Install required packages
pip install -r requirements.txt
```

**What gets installed:**
- `requests` - Makes HTTP requests to APIs
- `beautifulsoup4` & `lxml` - Scrapes restaurant websites
- `python-dotenv` - Loads API keys from .env file
- `rich` - Creates beautiful terminal output
- `click` - Handles command-line interface

### Step 2: Set Up Your API Keys

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your text editor
nano .env   # or use vim, code, etc.
```

**Edit `.env` to include:**
```bash
# Required for Google Places search
GOOGLE_PLACES_API_KEY=AIzaSyD...your_actual_key

# Optional: only needed for direct HubSpot push
HUBSPOT_API_KEY=pat-na1-...your_actual_token
```

**How to get API keys:**

**Google Places API** (Recommended):
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Places API (New)"
4. Go to Credentials → Create Credentials → API Key
5. Copy the key to your `.env` file

**HubSpot API** (Optional):
1. Log into HubSpot
2. Settings (gear icon) → Integrations → Private Apps
3. Create a private app
4. Grant scopes: `crm.objects.companies.write` and `crm.objects.companies.read`
5. Copy the access token to your `.env` file

### Step 3: Verify Setup

```bash
python -m restaurant_scraper check-config
```

You should see:
```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Service           ┃ Status      ┃ Notes                   ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Google Places API │ Configured  │ Key: AIzaSyD...         │
│ HubSpot API       │ Connected   │ Key: pat-na1...         │
│ Yelp Scraping     │ Available   │ No API key needed       │
└───────────────────┴─────────────┴─────────────────────────┘
```

---

## Basic Usage

### Scenario 1: Quick Search (Yelp - No API Key Needed)

**Use Case:** You want to test the scraper without setting up API keys.

```bash
python -m restaurant_scraper scrape "Austin, TX" --source yelp -n 10
```

**What happens:**
1. Scraper searches Yelp for restaurants in Austin, TX
2. Gets up to 10 results
3. Scrapes each restaurant's website for email, owner, social media
4. Saves results to `output/austin_tx_20260217_143052.csv`

**Output:**
```
Found 10 restaurants.

Fetching Google Place details...
Scraping websites for contact info... ━━━━━━━━━━━━━━━━━━━━ 10/10

Restaurant Results (10 found)
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ #  ┃ Name                ┃ Phone         ┃ Email           ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ 1  │ Franklin Barbecue   │ (512)555-0100 │ info@franklin...│
│ 2  │ Uchi                │ (512)555-0200 │ reservations@...│
└────┴─────────────────────┴───────────────┴─────────────────┘

CSV exported to: output/austin_tx_20260217_143052.csv
```

### Scenario 2: Google Places Search (More Accurate)

**Use Case:** You want comprehensive, accurate data with ratings and hours.

```bash
python -m restaurant_scraper scrape "San Francisco, CA" --source google -n 20
```

**What you get:**
- Venue name, address, phone from Google Places
- Google ratings, price level, hours of operation
- Cuisine type
- Website enrichment (email, owner, social media)

### Scenario 3: Search Both Sources for Maximum Coverage

**Use Case:** You want the most comprehensive list possible.

```bash
python -m restaurant_scraper scrape "Chicago, IL" --source both -n 50
```

**What happens:**
1. Searches Google Places for up to 50 restaurants
2. Searches Yelp for up to 50 restaurants
3. Deduplicates by restaurant name
4. Enriches all unique restaurants with website data
5. Merges data from both sources (better coverage)

---

## Advanced Usage Scenarios

### Scenario 4: Fast Scrape (Skip Website Enrichment)

**Use Case:** You only need basic info (name, address, phone) and want it fast.

```bash
python -m restaurant_scraper scrape "Miami, FL" --no-enrich -n 30
```

**Benefit:**
- 5-10x faster
- No website scraping delays
- Good for bulk lead generation where you'll manually qualify later

### Scenario 5: Custom Output File

**Use Case:** You're running multiple searches and want organized files.

```bash
# Organize by project or campaign
python -m restaurant_scraper scrape "Denver, CO" -o leads/denver_q1_campaign.csv

# Organize by date
python -m restaurant_scraper scrape "Portland, OR" -o leads/2026-02-17_portland.csv
```

### Scenario 6: Specific Neighborhood or Area

**Use Case:** Target a specific neighborhood or ZIP code.

```bash
# By neighborhood
python -m restaurant_scraper scrape "SoHo, New York, NY" -n 25

# By ZIP code
python -m restaurant_scraper scrape "90210, CA" -n 15

# By landmark
python -m restaurant_scraper scrape "Times Square, NYC" --radius 1000 -n 20
```

**Note:** `--radius` parameter (in meters) only works with Google Places.

### Scenario 7: Get Raw Data Format

**Use Case:** You want data for your own CRM or database (not HubSpot).

```bash
python -m restaurant_scraper scrape "Seattle, WA" --raw-format -n 25
```

**Difference:**
- **HubSpot format:** Column names like `name`, `phone`, `website`, `domain`
- **Raw format:** Column names like `venue_name`, `phone_number`, `venue_website`, etc.

---

## Understanding Your Data

### What Data Gets Collected

| Field | Example | Source |
|-------|---------|--------|
| **Venue Name** | "The French Laundry" | Google Places / Yelp |
| **Website** | "https://thomaskeller.com" | Google Places / Yelp |
| **Phone** | "(707) 944-2380" | Google Places / Yelp / Website |
| **Email** | "info@thomaskeller.com" | Website scraping |
| **Address** | "6640 Washington St, Yountville, CA" | Google Places / Yelp |
| **Owner** | "Thomas Keller" | Website scraping |
| **Facebook** | "https://facebook.com/frenchlaundry" | Website scraping |
| **Instagram** | "@thefrenchlaundry" | Website scraping |
| **Twitter/X** | "@FrenchLaundry" | Website scraping |
| **LinkedIn** | "company/french-laundry" | Website scraping |
| **TikTok** | "@frenchlaundry" | Website scraping |
| **Rating** | "4.7" | Google Places / Yelp |
| **Price Level** | "$$$$" | Google Places / Yelp |
| **Hours** | "Mon-Sun: 5:30 PM - 9:00 PM" | Google Places |
| **Cuisine** | "French, Fine Dining" | Google Places |

### CSV File Structure

**HubSpot Format** (default):
```csv
name,website,domain,phone,address,city,state,zip,country,facebook,instagram,...
The French Laundry,https://thomaskeller.com,thomaskeller.com,(707)944-2380,...
```

**Raw Format** (`--raw-format`):
```csv
venue_name,venue_website,phone_number,email_address,venue_address,...
The French Laundry,https://thomaskeller.com,(707)944-2380,info@thomaskeller.com,...
```

### Where Files Are Saved

```bash
Data-scraper/
├── output/
│   ├── san_francisco_ca_20260217_143052.csv
│   ├── austin_tx_20260217_150230.csv
│   └── chicago_il_20260217_162145.csv
```

---

## Exporting to HubSpot

### Method 1: Manual CSV Import (Recommended for Beginners)

**Step-by-step:**

1. Run the scraper:
```bash
python -m restaurant_scraper scrape "Los Angeles, CA" -n 50
```

2. Note the output file path:
```
CSV exported to: output/los_angeles_ca_20260217_143052.csv
```

3. Go to HubSpot:
   - Navigate to **Contacts** → **Companies** → **Import**
   - Click **"Start an import"**
   - Select **"File from computer"**
   - Upload your CSV file

4. Map the columns:
   - Most columns auto-map (name → Company Name, phone → Phone Number)
   - Verify the mappings look correct
   - Click **"Finish Import"**

5. Review imported companies in HubSpot

### Method 2: Direct API Push (Advanced)

**Use Case:** Automate the entire process without manual CSV upload.

```bash
python -m restaurant_scraper scrape "Boston, MA" --hubspot-push -n 30
```

**What happens:**
1. Scrapes restaurants
2. Saves CSV file (as backup)
3. Tests HubSpot connection
4. Pushes each restaurant directly to HubSpot as a company
5. Shows results:
```
HubSpot results: 28 created, 2 failed
  • Company already exists: Franklin Barbecue
  • Invalid phone number format: +1...
```

**Requirements:**
- `HUBSPOT_API_KEY` must be set in `.env`
- API token needs `crm.objects.companies.write` scope

---

## Tips & Best Practices

### 1. Start Small, Then Scale
```bash
# Start with 10 results to test
python -m restaurant_scraper scrape "New York, NY" -n 10

# Once comfortable, scale up
python -m restaurant_scraper scrape "New York, NY" -n 100
```

### 2. Use Both Sources for Best Coverage
```bash
# Combine Google + Yelp for maximum leads
python -m restaurant_scraper scrape "Nashville, TN" --source both -n 50
```

### 3. Be Specific with Locations
```bash
# Good: Specific neighborhoods
python -m restaurant_scraper scrape "Downtown Austin, TX"

# Better: Include cuisine type or category in search
python -m restaurant_scraper scrape "Italian restaurants, Brooklyn, NY"

# Best: Use exact coordinates for precision
python -m restaurant_scraper scrape "37.7749,-122.4194" --radius 2000
```

### 4. Respect Rate Limits
- **Google Places API:** 1000 requests/day (free tier)
- **Yelp scraping:** May get blocked if too aggressive
- **Website scraping:** 1-2 second delay per site (built-in)

**Recommendation:** Run searches in batches rather than one huge search.

### 5. Organize Your Output
```bash
# Create folders for different campaigns
mkdir -p output/q1_2026 output/q2_2026

# Use descriptive filenames
python -m restaurant_scraper scrape "Seattle, WA" -o output/q1_2026/seattle_italian.csv
```

### 6. Save API Calls with --no-enrich
```bash
# If you only need contact info from Google/Yelp
python -m restaurant_scraper scrape "Phoenix, AZ" --no-enrich -n 100
```

### 7. Check Your Data Before Importing
```bash
# Open the CSV and review
cat output/austin_tx_20260217_143052.csv | head -20

# Or use a spreadsheet program
libreoffice output/austin_tx_20260217_143052.csv
```

---

## Troubleshooting

### Problem: "GOOGLE_PLACES_API_KEY not set"

**Solution:**
```bash
# Make sure .env file exists
ls -la .env

# Verify the key is in the file
cat .env

# Should show:
# GOOGLE_PLACES_API_KEY=AIzaSy...your_key

# If not, add it:
echo "GOOGLE_PLACES_API_KEY=your_actual_key" >> .env
```

### Problem: "No restaurants found"

**Possible causes:**
1. **Location too specific or misspelled**
   ```bash
   # Try broader location
   python -m restaurant_scraper scrape "Austin, TX" instead of "123 Main St"
   ```

2. **Radius too small (Google Places)**
   ```bash
   # Increase radius
   python -m restaurant_scraper scrape "Rural Town, MT" --radius 50000
   ```

3. **API quota exceeded**
   ```bash
   # Check API usage in Google Cloud Console
   # Or switch to Yelp:
   python -m restaurant_scraper scrape "Austin, TX" --source yelp
   ```

### Problem: "Could not connect to HubSpot"

**Solution:**
```bash
# Test your API key
python -m restaurant_scraper check-config

# Verify the key has correct permissions:
# - crm.objects.companies.read
# - crm.objects.companies.write

# Regenerate key if needed in HubSpot Settings → Integrations → Private Apps
```

### Problem: Missing emails or owner information

**Expected behavior:**
- Website scraping finds emails in ~40-60% of cases
- Owner names found in ~20-30% of cases
- Some restaurants don't publish this information

**Not a bug** - this is normal for web scraping.

### Problem: Duplicate restaurants

**Solution:**
The scraper automatically deduplicates by name, but if you see duplicates:
- They may have slightly different names ("Joe's Pizza" vs "Joe's Pizzeria")
- Manually review and clean the CSV before importing

### Problem: Slow performance

**Speed it up:**
```bash
# Skip website enrichment
python -m restaurant_scraper scrape "LA, CA" --no-enrich -n 50

# Use smaller result sets
python -m restaurant_scraper scrape "LA, CA" -n 20

# Use only Yelp (faster than Google Place Details)
python -m restaurant_scraper scrape "LA, CA" --source yelp --no-enrich
```

---

## Common Workflows

### Workflow 1: Building a Sales Lead List

```bash
# Step 1: Get restaurants in target city
python -m restaurant_scraper scrape "Denver, CO" --source both -n 100 -o leads/denver_all.csv

# Step 2: Review the CSV, filter by criteria (rating, has website, etc.)

# Step 3: Import to HubSpot
# Go to HubSpot → Import → Upload leads/denver_all.csv

# Step 4: Create targeted outreach campaigns in HubSpot
```

### Workflow 2: Market Research

```bash
# Get comprehensive data with website enrichment
python -m restaurant_scraper scrape "Portland, OR" --source both -n 200

# Analyze:
# - How many have websites vs no websites?
# - Email availability rate
# - Social media presence
# - Average ratings and price points
```

### Workflow 3: Multi-City Campaign

```bash
# Create a script or run manually:
python -m restaurant_scraper scrape "San Francisco, CA" -o campaigns/west_coast/sf.csv -n 50
python -m restaurant_scraper scrape "Los Angeles, CA" -o campaigns/west_coast/la.csv -n 50
python -m restaurant_scraper scrape "San Diego, CA" -o campaigns/west_coast/sd.csv -n 50
python -m restaurant_scraper scrape "Seattle, WA" -o campaigns/west_coast/sea.csv -n 50

# Combine CSVs and import to HubSpot as one campaign
```

---

## Getting Help

```bash
# Show all available commands
python -m restaurant_scraper --help

# Show help for scrape command
python -m restaurant_scraper scrape --help

# Check current configuration
python -m restaurant_scraper check-config
```

**Command Options Quick Reference:**
```
--source, -s      google|yelp|both (default: google)
--max-results, -n Number of results (default: 20)
--radius, -r      Search radius in meters (default: 5000)
--enrich          Scrape websites for extra data (default: yes)
--no-enrich       Skip website scraping
--output, -o      Custom output file path
--hubspot-push    Push directly to HubSpot API
--hubspot-format  Use HubSpot CSV columns (default: yes)
--raw-format      Use raw column names
--verbose, -v     Show debug logs
```

---

## Next Steps

1. **Test with a small search** to verify everything works
2. **Review the output CSV** to see what data you're getting
3. **Scale up** to larger searches once comfortable
4. **Import to HubSpot** and start your outreach campaigns

Happy scraping! 🍕🍔🍜
