"""
transforms/instagram_transform.py
----------------------------------
Maltego Local Transform: Instagram Risk Assessment

Input entity  : maltego.Person  (Value = Instagram handle, with or without @)
Output entities: maltego.Person nodes colour-coded by risk level,
                 plus flagged network nodes for any known-bad accounts followed.

How it appears in Maltego:
  Right-click any Person entity → Other Transforms →
  "Instagram: Assess Risk Profile"

Data flow (all local after Apify scrape):
  1. Apify scrapes Instagram profile + comments  [internet]
  2. Ollama scores the data against the rubric   [local GPU only]
  3. Entities are added to the Maltego graph     [local]
"""

import logging
from datetime import datetime
import json


from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform


import config
from utils.apify_scraper import fetch_instagram_profile, fetch_instagram_comments
from utils.ollama_scorer import score_profile
from utils.entity_builder import (
    add_risk_entity,
    add_flagged_account_entities,
    add_ui_message,
)
from dashboard import store_result

log = logging.getLogger(__name__)


def _load_bad_accounts() -> set:
    """Load the known-bad accounts list from disk if configured."""
    if not config.KNOWN_BAD_ACCOUNTS_FILE:
        return set()
    try:
        from pathlib import Path
        lines = Path(config.KNOWN_BAD_ACCOUNTS_FILE).read_text(encoding="utf-8").splitlines()
        return {
            l.strip().lstrip("@").lower()
            for l in lines
            if l.strip() and not l.startswith("#")
        }
    except FileNotFoundError:
        log.warning("Bad accounts file not found: %s", config.KNOWN_BAD_ACCOUNTS_FILE)
        return set()


class instagram_transform(DiscoverableTransform):
    """
    End-to-end Instagram risk assessment transform.

    Steps
    -----
    1. Extract Instagram handle from the Maltego entity value.
    2. Fetch profile metadata + comments via Apify.
    3. Cross-reference following list against known-bad accounts.
    4. Score everything locally with Ollama.
    5. Return colour-coded entities and a UI summary to Maltego.
    """
    
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
    
        # ── 1. Extract handle ────────────────────────────────────────────────
        raw_value = request.Value.strip()
        username  = raw_value.lstrip("@").split("/")[-1].strip()
        

        if not username:
            response.addUIMessage(
                "No Instagram handle provided. Set the entity value to a username.",
                messageType="PartialError",
            )
            return

        log.info("[InstagramTransform] Starting assessment for @%s", username)

        # ── 2. Scrape profile ────────────────────────────────────────────────
        profile = fetch_instagram_profile(username)
        if not profile:
            response.addUIMessage(
                f"Could not fetch @{username} from Instagram. "
                "Check the handle is correct and your Apify token is valid.",
                messageType="PartialError",
            )
            return

        # ── 3. Scrape comments (public accounts only) ────────────────────────
        comments = []
        if not profile.get("is_private"):
            comments = fetch_instagram_comments(username, profile.get("post_urls", []))
        else:
            response.addUIMessage(
                f"@{username} is a private account — comment scraping skipped. "
                "Profile metadata and bio will still be scored.",
                messageType="Inform",
            )

        # ── 4. Cross-reference following list using bad accounts file ────────────────────────────────
        
        bad_accounts     = _load_bad_accounts()
        flagged_following = [
            h for h in profile.get("following_list", [])
            if h in bad_accounts
        ]
        if flagged_following:
            log.warning(
                "[InstagramTransform] @%s follows %d flagged account(s): %s",
                username, len(flagged_following), flagged_following,
            )
        
        # ── 5. Score locally with Ollama ─────────────────────────────────────
        result = score_profile(profile, comments, flagged_following)

        # Stamp metadata onto result for audit trail
        result["_meta"] = {
            "transform":         "InstagramRiskTransform",
            "scraped_at":        datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_used":        config.OLLAMA_MODEL,
            "comments_analysed": len(comments),
            "following_size":    len(profile.get("following_list", [])),
            "flagged_following": flagged_following,
            "data_left_machine": False,
        }

        # ── 6. Build Maltego graph entities ──────────────────────────────────
        add_ui_message(response, result)
        add_risk_entity(response, result, profile)

        if flagged_following:
            add_flagged_account_entities(response, flagged_following, username)

        # Store result in memory for dashboard (no files written to disk)
        store_result(result)

        log.info(
            "[InstagramTransform] Complete: @%s → %d/100 (%s)",
            username,
            result.get("total_risk_score", -1),
            result.get("risk_level", "ERROR"),
        )
