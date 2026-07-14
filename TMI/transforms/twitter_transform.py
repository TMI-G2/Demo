"""
transforms/twitter_transform.py
---------------------------------
Maltego Local Transform: Twitter/X Risk Assessment

Input entity  : maltego.Person  (Value = Twitter handle, with or without @)
Output entities: maltego.Person nodes colour-coded by risk level.

Data flow (all local after Apify scrape):
  1. Apify scrapes Twitter/X profile metadata  [internet]
  2. Ollama scores the data against the rubric  [local GPU only]
  3. Entities are added to the Maltego graph    [local]
"""

import logging
from datetime import datetime

from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform

import config
from utils.apify_scraper import fetch_twitter_profile
from utils.ollama_scorer import score_profile
from utils.entity_builder import (
    add_risk_entity,
    add_flagged_account_entities,
    add_ui_message,
)
from dashboard import store_result

log = logging.getLogger(__name__)


def _load_bad_accounts() -> set:
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


class twitter_transform(DiscoverableTransform):
    """
    End-to-end Twitter/X risk assessment transform.

    Steps
    -----
    1. Extract Twitter handle from the Maltego entity value.
    2. Fetch profile metadata via Apify.
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
                "No Twitter/X handle provided. Set the entity value to a username.",
                messageType="PartialError",
            )
            return

        log.info("[TwitterTransform] Starting assessment for @%s", username)

        # ── 2. Scrape profile ────────────────────────────────────────────────
        profile = fetch_twitter_profile(username)
        if not profile:
            response.addUIMessage(
                f"Could not fetch @{username} from Twitter/X. "
                "Check the handle is correct and your Apify token is valid.",
                messageType="PartialError",
            )
            return

        # ── 3. Protected account handling ────────────────────────────────────
        if profile.get("is_private"):
            response.addUIMessage(
                f"@{username} is a protected account — tweet scraping skipped. "
                "Profile metadata and bio will still be scored.",
                messageType="Inform",
            )

        # ── 4. Cross-reference against known-bad accounts ────────────────────
        bad_accounts      = _load_bad_accounts()
        flagged_following = [
            h for h in profile.get("following_list", [])
            if h in bad_accounts
        ]
        if flagged_following:
            log.warning(
                "[TwitterTransform] @%s follows %d flagged account(s): %s",
                username, len(flagged_following), flagged_following,
            )

        # ── 5. Score locally with Ollama ─────────────────────────────────────
        result = score_profile(profile, [], flagged_following)

        # Stamp metadata onto result for audit trail
        result["_meta"] = {
            "transform":         "TwitterRiskTransform",
            "scraped_at":        datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_used":        config.OLLAMA_MODEL,
            "comments_analysed": 0,
            "following_size":    len(profile.get("following_list", [])),
            "flagged_following": flagged_following,
            "data_left_machine": False,
        }

        # ── 6. Build Maltego graph entities ──────────────────────────────────
        add_ui_message(response, result)
        add_risk_entity(response, result, profile)

        if flagged_following:
            add_flagged_account_entities(response, flagged_following, username)

        # Store result in memory for dashboard
        store_result(result)

        log.info(
            "[TwitterTransform] Complete: @%s → %d/100 (%s)",
            username,
            result.get("total_risk_score", -1),
            result.get("risk_level", "ERROR"),
        )