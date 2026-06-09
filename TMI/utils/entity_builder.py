"""
utils/entity_builder.py
-----------------------
Builds Maltego graph entities from risk scoring results.
Shared by all platform transforms — keeps entity structure consistent
across Instagram, LinkedIn, Facebook, Twitter etc.

Risk level → node colour mapping (Maltego bookmark colours):
  CRITICAL  →  Red       (bookmark 1)
  HIGH      →  Orange    (bookmark 3)
  MEDIUM    →  Yellow    (bookmark 4)
  LOW       →  Green     (bookmark 5)
"""

import logging
from maltego_trx.maltego import MaltegoTransform

log = logging.getLogger(__name__)

# Maltego bookmark colour integers
RISK_COLOURS = {
    "CRITICAL": 1,    # Red
    "HIGH":     3,    # Orange
    "MEDIUM":   4,    # Yellow
    "LOW":      5,    # Green
    "ERROR":    2,    # Blue (used to flag processing errors)
}

# Display-friendly risk level labels
RISK_LABELS = {
    "CRITICAL": "🔴 CRITICAL",
    "HIGH":     "🟠 HIGH",
    "MEDIUM":   "🟡 MEDIUM",
    "LOW":      "🟢 LOW",
    "ERROR":    "⚠ ERROR",
}


def add_risk_entity(response: MaltegoTransform, result: dict, profile: dict) -> None:
    """
    Add a fully populated risk profile entity to the Maltego response graph.

    This is the main entity the investigator sees on the graph — it represents
    the scored subject with all risk data attached as inspectable properties.

    Parameters
    ----------
    response : MaltegoTransform
        The active Maltego response object to add entities to.
    result : dict
        The structured risk score dict returned by ollama_scorer.score_profile().
    profile : dict
        The raw profile dict from apify_scraper (used for supplementary fields).
    """
    username    = result.get("username", "unknown")
    platform    = result.get("platform", "unknown").capitalize()
    score       = result.get("total_risk_score", -1)
    risk_level  = result.get("risk_level", "ERROR")
    cat_scores  = result.get("category_scores", {})
    summary     = result.get("analyst_summary", "")
    recs        = result.get("top_recommendations", [])

    # ── Primary entity on the graph ──────────────────────────────────────────
    # Using maltego.Person as the entity type so it works without a custom
    # entity definition. When you have Maltego Professional you can define
    # a custom "SocialRiskProfile" entity type for a cleaner graph.
    entity = response.addEntity("maltego.Person", f"@{username}")

    # Colour-code the node by risk level
    entity.setBookmark(RISK_COLOURS.get(risk_level, 2))

    # ── Core risk properties ─────────────────────────────────────────────────
    entity.addProperty(
        fieldName="risk_score",
        displayName="Risk Score",
        matchingRule="loose",
        value=f"{score}/100" if score >= 0 else "ERROR",
    )
    entity.addProperty(
        fieldName="risk_level",
        displayName="Risk Level",
        matchingRule="loose",
        value=RISK_LABELS.get(risk_level, risk_level),
    )
    entity.addProperty(
        fieldName="platform",
        displayName="Platform",
        matchingRule="loose",
        value=platform,
    )
    entity.addProperty(
        fieldName="profile_url",
        displayName="Profile URL",
        matchingRule="loose",
        value=profile.get("profile_url", ""),
    )
    entity.addProperty(
        fieldName="analyst_summary",
        displayName="Analyst Summary",
        matchingRule="loose",
        value=summary,
    )

    # ── Per-category scores ───────────────────────────────────────────────────
    for category, data in cat_scores.items():
        cat_score   = data.get("score", 0)
        cat_max     = _get_max_points(category)
        cat_evidence = data.get("evidence", "")
        cat_reason   = data.get("reasoning", "")

        entity.addProperty(
            fieldName=f"cat_{category}_score",
            displayName=f"{_label(category)} ({cat_score}/{cat_max})",
            matchingRule="loose",
            value=f"{cat_score}/{cat_max} — {cat_reason}",
        )
        if cat_evidence:
            entity.addProperty(
                fieldName=f"cat_{category}_evidence",
                displayName=f"{_label(category)} Evidence",
                matchingRule="loose",
                value=cat_evidence,
            )

    # ── Recommendations ───────────────────────────────────────────────────────
    for i, rec in enumerate(recs, 1):
        entity.addProperty(
            fieldName=f"recommendation_{i}",
            displayName=f"Recommendation {i}",
            matchingRule="loose",
            value=rec,
        )

    # ── Supplementary profile fields ──────────────────────────────────────────
    if profile.get("full_name"):
        entity.addProperty("full_name", "Full Name", "loose", profile["full_name"])
    if profile.get("bio"):
        entity.addProperty("bio", "Bio", "loose", profile["bio"])
    if profile.get("followers") is not None:
        entity.addProperty("followers", "Followers", "loose", str(profile["followers"]))
    if profile.get("following") is not None:
        entity.addProperty("following", "Following", "loose", str(profile["following"]))

    log.info("[EntityBuilder] Added entity @%s (%s) → %s", username, platform, risk_level)


def add_flagged_account_entities(
    response: MaltegoTransform,
    flagged_following: list,
    subject_username: str,
) -> None:
    """
    Add a separate red-flagged entity for each known-bad account
    the subject follows, with a link back to the subject.

    These appear as connected nodes on the Maltego graph,
    making network relationships immediately visible to the investigator.
    """
    for handle in flagged_following:
        flagged_entity = response.addEntity("maltego.Person", f"@{handle}")
        flagged_entity.setBookmark(RISK_COLOURS["CRITICAL"])
        flagged_entity.addProperty(
            "flag_reason", "Flag Reason", "loose",
            f"Followed by @{subject_username} — present in known-bad accounts list",
        )
        log.info("[EntityBuilder] Added flagged network entity @%s", handle)


def add_ui_message(response: MaltegoTransform, result: dict) -> None:
    """
    Show a status message in the Maltego output panel.
    Gives the investigator an at-a-glance summary without opening properties.
    """
    score      = result.get("total_risk_score", -1)
    risk_level = result.get("risk_level", "ERROR")
    username   = result.get("username", "?")
    platform   = result.get("platform", "?")
    summary    = result.get("analyst_summary", "")

    if score < 0:
        msg_type = "PartialError"
        message  = f"[{platform}] @{username} — scoring failed. Check Ollama is running."
    else:
        msg_type = "Inform"
        message  = (
            f"[{platform}] @{username} | Score: {score}/100 | "
            f"{RISK_LABELS.get(risk_level, risk_level)}\n{summary}"
        )

    response.addUIMessage(message, messageType=msg_type)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _label(category: str) -> str:
    """Convert snake_case category name to a readable label."""
    return category.replace("_", " ").title()


def _get_max_points(category: str) -> int:
    """Look up the max points for a category from the rubric config."""
    try:
        import config
        return config.RISK_RUBRIC.get(category, {}).get("max_points", "?")
    except Exception:
        return "?"
