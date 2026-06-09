"""
utils/apify_scraper.py
----------------------
Apify scraping functions shared across all platform transforms.
Each platform transform imports only what it needs from here.

To add a new platform:
  1. Add its Apify actor ID to config.APIFY_ACTORS
  2. Add a new fetch_<platform>_profile() function below
  3. Import and call it from your new transform file
"""

import logging
import unicodedata
import re
from typing import Optional

from apify_client import ApifyClient
import config

log = logging.getLogger(__name__)


def get_client() -> ApifyClient:
    return ApifyClient(config.APIFY_API_TOKEN)


def sanitise(text: Optional[str]) -> str:
    """Normalise unicode, collapse whitespace, strip — safe for CSV and LLM prompts."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\r\n\t\u00a0\u200b]+", " ", text)
    return re.sub(r" {2,}", " ", text).strip()


# ── INSTAGRAM ─────────────────────────────────────────────────────────────────

def fetch_instagram_profile(username: str) -> dict:
    """
    Fetch Instagram profile metadata via Apify.
    Returns a normalised dict or empty dict on failure.
    """
    log.info("[Apify/Instagram] Fetching profile @%s", username)
    client = get_client()

    try:
        run = client.actor(config.APIFY_ACTORS["instagram_profile"]).call(run_input={
            "usernames":       [username],
            "scrapeFollowing": True,
            "resultsLimit":    1,
        })
        items = list(client.dataset(run.default_dataset_id).iterate_items())
        if not items:
            log.warning("[Apify/Instagram] No data for @%s", username)
            return {}

        raw = items[0]
        # Extract post URLs from latestPosts for comment scraping
        latest_posts = raw.get("latestPosts", []) or []
        post_urls = [
            p.get("url", "")
            for p in latest_posts
            if p.get("url", "")
        ]

        profile = {
            "platform":           "instagram",
            "username":           raw.get("username", username),
            "full_name":          sanitise(raw.get("fullName", "")),
            "bio":                sanitise(raw.get("biography", "")),
            "is_private":         bool(raw.get("private", False)),
            "account_visibility": "private" if raw.get("private", False) else "public",
            "is_verified":        bool(raw.get("verified", False)),
            "followers":          raw.get("followersCount", 0) or 0,
            "following":          raw.get("followsCount", 0) or 0,
            "post_count":         raw.get("postsCount", 0) or 0,
            "profile_url":        f"https://www.instagram.com/{username}/",
            "post_urls":          post_urls[:5],  # top 5 posts for comment scraping
            "following_list":     [
                u.get("username", "").lower()
                for u in (raw.get("followingList") or [])
                if u.get("username")
            ],
        }
        log.info(
            "[Apify/Instagram] @%s | followers=%d | private=%s",
            profile["username"], profile["followers"], profile["is_private"],
        )
        return profile

    except Exception as exc:
        log.error("[Apify/Instagram] Failed for @%s: %s", username, exc)
        return {}


def fetch_instagram_comments(username: str, post_urls: list = None) -> list:
    """Fetch comments using post URLs extracted from the profile."""
    if not post_urls:
        log.info("[Apify/Instagram] No post URLs available for @%s — skipping comments.", username)
        return []

    log.info("[Apify/Instagram] Fetching comments for @%s (%d posts)…", username, len(post_urls))
    client = get_client()

    try:
        run = client.actor(config.APIFY_ACTORS["instagram_comments"]).call(run_input={
            "directUrls":   post_urls,
            "resultsLimit": config.MAX_COMMENTS,
        })
        items = list(client.dataset(run.default_dataset_id).iterate_items())
        comments = [
            {
                "commenter": item.get("ownerUsername", ""),
                "text":      sanitise(item.get("text", "")),
                "timestamp": item.get("timestamp", ""),
            }
            for item in items
        ]
        log.info("[Apify/Instagram] Got %d comments for @%s", len(comments), username)
        return comments

    except Exception as exc:
        log.error("[Apify/Instagram] Comments failed for @%s: %s", username, exc)
        return []


# ── LINKEDIN (stub — ready to implement) ─────────────────────────────────────

def fetch_linkedin_profile(profile_url: str) -> dict:
    """
    TODO: Implement LinkedIn profile scraping.

    Steps:
      1. Add "linkedin_profile" actor ID to config.APIFY_ACTORS
      2. Implement scraping logic matching the pattern above
      3. Return the same normalised dict structure with platform="linkedin"

    Key fields to extract:
      full_name, headline, location, about (bio), experience,
      education, connections_count, profile_url
    """
    raise NotImplementedError(
        "LinkedIn transform not yet implemented. "
        "See utils/apify_scraper.py fetch_linkedin_profile() stub."
    )


# ── FACEBOOK (stub — ready to implement) ──────────────────────────────────────

def fetch_facebook_profile(profile_url: str) -> dict:
    """
    TODO: Implement Facebook profile scraping.

    Note: Facebook is the most locked-down platform.
    Expect to retrieve: name, bio, profile picture, public posts only.
    Friends list and groups are not accessible via any scraper.

    Steps:
      1. Add "facebook_profile" actor ID to config.APIFY_ACTORS
      2. Implement logic below matching the normalised dict structure
      3. Return with platform="facebook"
    """
    raise NotImplementedError(
        "Facebook transform not yet implemented. "
        "See utils/apify_scraper.py fetch_facebook_profile() stub."
    )


# ── TWITTER / X (stub — ready to implement) ───────────────────────────────────

def fetch_twitter_profile(username: str) -> dict:
    """
    TODO: Implement Twitter/X profile scraping.

    Note: Twitter/X has heavily restricted its API since 2023.
    Apify maintains working scrapers that bypass this — use:
      apify/twitter-scraper  or  apify/tweet-scraper

    Key fields to extract:
      username, display_name, bio (description), is_verified,
      followers_count, following_count, tweet_count, tweets (list)

    Steps:
      1. Add "twitter_profile" actor ID to config.APIFY_ACTORS
      2. Implement scraping logic below
      3. Return with platform="twitter"
    """
    raise NotImplementedError(
        "Twitter/X transform not yet implemented. "
        "See utils/apify_scraper.py fetch_twitter_profile() stub."
    )
