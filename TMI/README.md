# Maltego Risk Transform Server — Setup Guide

## Project structure

```
maltego_transforms/
├── server.py                        ← Start this first, then open Maltego
├── config.py                        ← All settings live here
├── requirements.txt
│
├── transforms/
│   ├── __init__.py                  ← Controls which platforms are active
│   ├── instagram_transform.py       ← ✅ Active
│   ├── linkedin_transform.py        ← 🔲 Stub (ready to implement)
│   ├── facebook_transform.py        ← 🔲 Stub (ready to implement)
│   └── twitter_transform.py         ← 🔲 Stub (ready to implement)
│
└── utils/
    ├── apify_scraper.py             ← All Apify scraping logic
    ├── ollama_scorer.py             ← Local Ollama LLM scoring
    └── entity_builder.py           ← Builds Maltego graph entities
```

---

## Step 1 — Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Step 2 — Set your Apify token

```powershell
$env:APIFY_API_TOKEN = "apify_api_your_token_here"
```

To make this permanent (survives restarts), add it to your Windows
system environment variables:
  Start → Search "Environment Variables" → User variables → New

---

## Step 3 — Make sure Ollama is running

Look for the Ollama icon in your system tray (bottom-right).
If it's not there, start Ollama from the Start menu.

Confirm your model is pulled:
```powershell
ollama list
```
You should see `llama3.1:8b` or `qwen2.5:14b` in the list.
If not: `ollama pull llama3.1:8b`

---

## Step 4 — Start the transform server

```powershell
cd maltego_transforms
python server.py
```

You should see:
```
✓ Apify token found
✓ Ollama running | model: llama3.1:8b
Registered transforms:
  → Instagram: Assess Risk Profile
Server starting on http://localhost:8080
Keep this window open while using Maltego.
```

Leave this terminal open the entire time you use Maltego.

---

## Step 5 — Register the server in Maltego

1. Open Maltego desktop client
2. Go to: **Maltego menu (top-left)** → **Settings** → **Transform Manager**
3. Click **"New Local Transform Server"** (or Add)
4. Fill in:
   - Name: `Social Media Risk Assessment`
   - URL: `http://localhost:8080/`
   - Click **Test Connection** — should say "Connected"
5. Click **Discover Transforms**
   - Maltego will pull the transform list from the server
   - You should see `Instagram: Assess Risk Profile` appear

---

## Step 6 — Run your first transform in Maltego

1. Drag a **Person** entity onto the graph
2. Set its **Value** to an Instagram handle (e.g. `nasa` or `@nasa`)
3. **Right-click** the entity
4. Click **Other Transforms** → **Social Media Risk Assessment** →
   **Instagram: Assess Risk Profile**
5. The transform runs — watch the server terminal for live logs
6. A new colour-coded entity appears on the graph:
   - 🔴 Red = CRITICAL risk
   - 🟠 Orange = HIGH risk
   - 🟡 Yellow = MEDIUM risk
   - 🟢 Green = LOW risk
7. Click the entity to inspect all properties (score, evidence, recommendations)

---

## Adding a new platform later

When you're ready to add LinkedIn, Facebook, or Twitter:

### 1. Add the Apify actor ID to `config.py`
```python
APIFY_ACTORS = {
    "instagram_profile":  "apify/instagram-profile-scraper",
    "instagram_comments": "apify/instagram-comment-scraper",
    "linkedin_profile":   "apify/linkedin-profile-scraper",  # ← add this
}
```

### 2. Implement the scraping function in `utils/apify_scraper.py`
Follow the `fetch_instagram_profile()` pattern exactly.
The function must return a dict with at least: `platform`, `username`,
`bio`, `is_private`, `profile_url`.

### 3. Uncomment the decorator in the platform's transform file
In `transforms/linkedin_transform.py`, uncomment:
```python
from maltego_trx import registry
@registry.register_transform(...)
```

### 4. Uncomment the import in `transforms/__init__.py`
```python
from transforms.linkedin_transform import LinkedInRiskTransform
```

### 5. Restart the server and click Discover Transforms in Maltego
The new transform appears automatically. No other changes needed.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Apify token not set` | Run `$env:APIFY_API_TOKEN = "..."` in the same terminal |
| `Cannot reach Ollama` | Check system tray — start Ollama if icon is missing |
| `Model not found` | Run `ollama pull llama3.1:8b` |
| Transform not appearing in Maltego | Click Discover Transforms again after server restart |
| `Could not fetch @username` | Check handle is correct and account is public |
| JSON parse error in logs | Profile had unusual bio — model's fallback extractor handles it |

---

## Data privacy summary

| Step | Goes online? |
|---|---|
| Apify scrape | ✅ Yes — Apify servers fetch Instagram data |
| Risk scoring (Ollama) | ❌ No — runs entirely on your RTX 5070 |
| Maltego graph entities | ❌ No — local Community Edition only |
| Output files | ❌ No — saved to your disk only |
