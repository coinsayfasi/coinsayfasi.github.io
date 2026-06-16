# Pinterest daily auto-pinner

Posts a few quality pins per day from the SEO pages in this repo (`sitemap.xml`)
to Pinterest, with branded images, SEO descriptions + hashtags, and a link back
to each page. Runs on GitHub Actions (free) — no server needed.

## Files
- `poster.py` — picks unpinned pages, builds content, posts (or dry-runs).
- `pin_image.py` — 1000×1500 branded card, optional free Pexels photo backdrop.
- `pinterest_api.py` — Pinterest API v5 client (boards + image pins).
- `state.json` — remembers which page URLs were already pinned (no duplicates).
- `../../.github/workflows/pinterest-daily.yml` — daily cron.

## Setup
1. **Pexels API key** (free): https://www.pexels.com/api/ → add as repo secret
   `PEXELS_API_KEY`. (Optional — without it, plain branded cards are used.)
2. **Pinterest access token** (free): create an app at
   https://developers.pinterest.com/apps/ with scopes `boards:read`,
   `boards:write`, `pins:write` → add as repo secret `PINTEREST_ACCESS_TOKEN`.
   - New apps start in *Trial* access (pins to your own account). Request
     *Standard* access for full use — free, short review.
3. Repo → Settings → Secrets and variables → Actions → add both secrets.
4. Boards are auto-created by name on first run (Türkiye Gezilecek Yerler /
   Travel Packing Tips / Landlord & Rental Tips).

## Test locally (dry-run, no token needed)
```bash
pip install -r requirements.txt
cd _automation/pinterest
python poster.py            # writes preview PNGs to ./preview/, posts nothing
```
With a token set in the environment it posts for real.

## Tuning
- `PINS_PER_RUN` (default 3) — keep it small to stay quality, not spammy.
- Cron time + themes/hashtags/CTAs live at the top of `poster.py`.
