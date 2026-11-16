# Connecting the live rate feed

The live adapter is built and tested on a sample retyped from your screenshot, but it stays OFF until you switch it on.

1. Make sure you may use the feed on your shop display (provider's permission or terms).
2. Copy `.env.example` to `.env` and edit it: set `LIVE_PERMISSION_CONFIRMED=yes`, the interval, and the row mapping.
3. Restart `python app.py`. In the admin panel, "Live" now appears under Mode. Select it and save.
4. **Check the first numbers against the provider's own page.** If they differ, tell me.
5. Silver uses its own feed: add `LIVE_URL_SILVER` and `LIVE_MAP_SILVER=4642` (see `.env.example`). Make sure you may use that provider too.
   If either feed fails, no rate is refreshed, so the whole board turns STALE together. Old rates are never shown as live.

If the feed changes format or goes down, the board keeps the last rates, turns grey and shows STALE. It never shows old rates as live.
