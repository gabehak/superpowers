# SoFi Tournament Sprint — Setup & Execution Guide

**Timeline:** May 19 – July 10, 2026  
**Goal:** 10–15 restaurant clients @ $997–$1,997 each

---

## Day 0: Get API Keys (TODAY — 2 hours)

Sign up and grab API keys for these 5 services:

| Service | URL | Cost | What to get |
|---------|-----|------|-------------|
| Anthropic (Claude) | console.anthropic.com | ~$6 | API key |
| Firecrawl | firecrawl.dev | $13/mo | API key |
| Hunter.io | hunter.io | Free (50/mo) | API key |
| Airtable | airtable.com | Free | Personal Access Token + Workspace ID |
| Apify | apify.com | $4 credits | API key |

Save all keys to a `.env` file (never commit this):
```
ANTHROPIC_API_KEY=sk-ant-...
FIRECRAWL_API_KEY=fc-...
HUNTER_API_KEY=...
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...   # filled after step 2
AIRTABLE_ORG_ID=wsp...
```

---

## Step 1: Scrape Leads (Apify — 30 min)

1. Go to apify.com → Marketplace → search "Google Maps Scraper"
2. Run with these queries (one at a time):
   - `sports bar Inglewood CA`
   - `restaurant Westchester CA`
   - `bar Culver City CA`
   - `sports bar West LA`
   - `brewpub Culver City`
   - `watch party venue Inglewood`
   - `Iranian restaurant Westwood CA`
   - `Turkish restaurant Los Angeles CA`
3. Export each run as CSV
4. Merge all CSVs into one file: `apify_raw.csv`

Expected columns: `Name, Address, Website, Phone, Rating, ReviewCount, PlaceId`

---

## Step 2: Filter Leads

```bash
pip install requests anthropic
python scripts/filter_leads.py apify_raw.csv sofi_leads_qualified.csv
```

Expected output: 150–200 qualified leads from ~500 raw rows.

---

## Step 3: Enrich Emails (Hunter.io)

```bash
export HUNTER_API_KEY=your_key_here
python scripts/enrich_emails.py --input sofi_leads_qualified.csv --output sofi_leads_enriched.csv
```

Hunter free tier = 50 lookups/month. For 150+ leads, consider Apollo.io bulk export instead.

---

## Step 4: Create Airtable Base (one-time)

```bash
export AIRTABLE_API_KEY=pat...
export AIRTABLE_ORG_ID=wsp...
python scripts/create_airtable_base.py
```

Copy the `AIRTABLE_BASE_ID` it prints, add to `.env`.

---

## Step 5: Load Leads into Airtable

```bash
export AIRTABLE_API_KEY=pat...
export AIRTABLE_BASE_ID=app...
python scripts/load_airtable.py --input sofi_leads_enriched.csv
```

---

## Step 6: Run Audits (Python — or n8n)

### Option A: Python (run now, no n8n needed)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export FIRECRAWL_API_KEY=fc-...

# Test on 3 leads first
python scripts/run_audit.py --input sofi_leads_enriched.csv --limit 3

# Full run
python scripts/run_audit.py --input sofi_leads_enriched.csv --output sofi_leads_audited.csv
```

### Option B: n8n (automated, runs every 2 hours)
1. Go to n8n.cloud (or self-host on Hetzner ~$4/mo)
2. Create new workflow → Import from file
3. Import: `workflows/n8n_workflow.json`
4. Set credentials: Airtable token, env vars for API keys
5. Activate workflow

---

## Step 7: Load Audited Leads

```bash
python scripts/load_airtable.py --input sofi_leads_audited.csv
```

---

## Step 8: Send Emails (Smartlead)

1. Sign up at smartlead.ai ($77/mo)
2. Add your 6 warmed inboxes
3. Export Airtable "Outreach Queue" view as CSV (sorted by priority_score DESC)
4. Import to Smartlead campaign
5. Use `templates/email_variants.md` — map Airtable fields to variables:
   - `{first_name}` → FirstName
   - `{neighborhood}` → Neighborhood
   - `{personalization_hook}` → Personalization_Hook
   - `{top_competitor}` → (set static = "Springbok Bar & Grill" or nearest competitor)
   - `{ranking_gap_1/2/3}` → Ranking_Gap_1/2/3
6. Set sequence: send 25/inbox/day during warmup week, then scale to 50/inbox/day

---

## Execution Checklist

### Week 1 (May 19–24)
- [ ] Get all 5 API keys
- [ ] Run Apify scrape (8 queries)
- [ ] Filter leads → ~150–200 qualified
- [ ] Enrich emails with Hunter
- [ ] Create Airtable base
- [ ] Load leads
- [ ] Run audits (Python or n8n)
- [ ] Set up Smartlead + inbox warmup
- [ ] Build Framer landing page (sofi-seo.com)
- [ ] Set up Cal.com 15-min booking slot
- [ ] Set up Stripe payment links ($997, $1497, $1997)

### Week 2 (May 25 – June 1)
- [ ] Send first 300 emails (25/inbox/day × 6 inboxes × 2 days)
- [ ] Monitor Smartlead replies
- [ ] Update Airtable Status as replies come in
- [ ] Book calls from interested replies
- [ ] Close first 5–8 deals
- [ ] Deliver audits to closed clients

### Week 3+ (June 2 – July 10)
- [ ] FOMO window: re-engage non-responders (price: $1,497)
- [ ] Post-USA match (June 12): new campaign with proof
- [ ] Final push (June 26–July 10): $1,997 full tournament run

---

## Priority Order for Outreach

After loading audited leads, sort Airtable "Outreach Queue" view by:
1. `Audit_Priority_Score` DESC (highest urgency first)
2. Filter: `Audit_Verdict = not_ready OR partial`
3. Filter: `Estimated_Traffic_Loss = high OR medium`

These are your hottest leads — they have the most to lose.

---

## Revenue Tracking

Track in Airtable "Closes" table. Quick math:
- 6 closes × $997 = **$5,982** (conservative)
- 10 closes × $1,497 = **$14,970** (realistic)  
- 15 closes × $1,997 = **$29,955** (strong, full tournament)

After $131 infrastructure: **net margin ~87%**
