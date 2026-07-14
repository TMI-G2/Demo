"""
config.py
---------
Central configuration for the Maltego Risk Transform Server.
Edit this file only — nothing else needs changing for basic setup.
"""

import os

# ── API credentials ────────────────────────────────────────────────────────────
# Set these as environment variables in PowerShell before running:
#   $env:APIFY_API_TOKEN = "apify_api_xxxx"
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "YOUR_APIFY_TOKEN_HERE")

# ── Local LLM (Ollama) ─────────────────────────────────────────────────────────
OLLAMA_MODEL       = "qwen2.5vl:7b"
OLLAMA_TEMPERATURE = 0.1       # low = more consistent JSON output
OLLAMA_MAX_TOKENS  = 4096
OLLAMA_HOST = "100.103.8.99"  # your actual Tailscale IP
OLLAMA_PORT = 11434

# ── Transform server ───────────────────────────────────────────────────────────
TRANSFORM_SERVER_HOST = "0.0.0.0"
TRANSFORM_SERVER_PORT = 8080

# ── Scraping limits ────────────────────────────────────────────────────────────
MAX_COMMENTS = 50             # per profile — keeps prompt size manageable

# ── Known-bad accounts ────────────────────────────────────────────────────────
# Path to a newline-separated list of flagged Instagram handles.
# Set to None to skip the cross-reference step.
KNOWN_BAD_ACCOUNTS_FILE = None   # e.g. "bad_accounts.txt"

# ── Apify actor IDs ───────────────────────────────────────────────────────────
# These are public Apify actors — no install needed, called via API.
# Add new platform actor IDs here as you expand.
APIFY_ACTORS = {
    "instagram_profile":  "apify/instagram-profile-scraper",
    "instagram_comments": "apify/instagram-comment-scraper",
    "twitter_profile":    "dy7gIgPRMhrOrfW0f",
    # ── Future platforms (add actor IDs when ready) ──
    # "linkedin_profile":   "apify/linkedin-profile-scraper",
    # "facebook_profile":   "apify/facebook-profile-scraper",
    
}

# ── Risk rubric ────────────────────────────────────────────────────────────────
# Shared across all platform transforms.
# Edit guidance strings freely — no code changes needed.
RISK_RUBRIC = {
    "pii_exposure": {
        "max_points": 30,
        "guidance": (
            "Check the bio, username, and post captions for any of these: "
            "Full first+last name visible: 8 pts. "
            "Phone number present: 10 pts. "
            "Home address or suburb: 10 pts. "
            "School or workplace named (e.g. 'St John's High', 'Grade 10', 'Works at X'): 8 pts. "
            "Email address present: 7 pts. Cap at 30."
        ),
    },
    "private_account": {
        "max_points": 10,
        "guidance": (
            "Check the account_visibility field ONLY. "
            "account_visibility = 'public'  → score MUST be 10. "
            "account_visibility = 'private' → score MUST be 0. "
            "No other values are possible. Do not use any other reasoning."
        ),
    },
    "bio_risk": {
        "max_points": 15,
        "guidance": (
            "Read the bio field carefully for any of these: "
            "Age or grade year mentioned (e.g. '16', 'Year 11', 'Class of 2027'): 5 pts. "
            "School or university named in bio: 5 pts. "
            "Location pinned or mentioned: 5 pts. "
            "Contact solicitation e.g. 'DM me', 'snap me', 'text me' (NOT email addresses — those are scored in pii_exposure): 3 pts. "
            "Romantic or sexual availability signals: 7 pts. Cap at 15."
        ),
    },
    "comment_disclosure": {
        "max_points": 20,
        "guidance": (
            "Phone or email in comments: 10 pts. "
            "Location, school, or workplace named in comments: 5 pts. "
            "Age or birthday shared in comments: 5 pts."
        ),
    },
    "network_risk": {
        "max_points": 15,
        "guidance": (
            "Following a flagged account: MUST add 10 pts each, cap at 15. "
            "Following accounts with suspicious usernames: MUST add 5 pts. "
            "If none of the above: score MUST be 0."
        ),
    },
    "engagement_pattern": {
        "max_points": 10,
        "guidance": (
            "Sharing personal plans or location with strangers in comments: MUST add 5 pts. "
            "Responding to flattery or gift offers from unknown accounts: MUST add 5 pts. "
            "If none of the above: score MUST be 0."
        ),
    },
}
