"""
utils/ollama_scorer.py
-----------------------
Local Ollama LLM risk scoring — zero data leaves the machine.
Uses format="json" for guaranteed valid JSON output every run.
"""
 
import json
import logging
import re
 
import ollama
import config
 
log = logging.getLogger(__name__)
 
SYSTEM_PROMPT = """\
You are a child online safety analyst. You assess social media profiles for
personal safety risk exposure. You are precise, evidence-based, and always
respond in valid JSON only — no markdown, no explanation outside the JSON.\
"""
 
# ── PII Pre-scanner ───────────────────────────────────────────────────────────
# Catches things the LLM misses due to abbreviations or weak inference.
 
INSTITUTION_KEYWORDS = [
    "university", "college", "school", "academy", "institute", "uni",
    "hs", "ocad", "uoft", "mcmaster", "ubc", "queens", "ryerson", "tmu",
    "york", "waterloo", "carleton", "ottawa", "concordia", "dalhousie",
    "grade ", "year ", "class of", "form ", "sixth form",
]
 
 
def prescan_bio(bio: str) -> dict:
    """
    Regex + keyword scan of the bio field.
    Returns a dict of confirmed findings to inject into the prompt.
    The LLM is told to treat these as already confirmed — no inference needed.
    """
    if not bio:
        return {}
 
    findings = {}
    bio_lower = bio.lower()
 
    # Email address
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", bio, re.IGNORECASE)
    if email_match:
        findings["email"] = email_match.group()
 
    # Phone number (various formats)
    phone_match = re.search(
        r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", bio
    )
    if phone_match:
        findings["phone"] = phone_match.group()
 
    # Age (standalone 2-digit number, e.g. "27", "16")
    age_match = re.search(r"\b(1[3-9]|[2-5]\d)\b", bio)
    if age_match:
        findings["age"] = age_match.group()
 
    # Grade/year patterns
    grade_match = re.search(
        r"\b(grade\s*\d+|year\s*\d+|class of \d{4}|form \d+)\b", bio_lower
    )
    if grade_match:
        findings["grade"] = grade_match.group()
 
    # Institution keywords
    for kw in INSTITUTION_KEYWORDS:
        if kw in bio_lower:
            findings["institution"] = bio.strip()
            break
 
    # Location signals
    location_match = re.search(
        r"\b(toronto|vancouver|montreal|calgary|ottawa|edmonton|"
        r"new york|london|sydney|melbourne|los angeles|chicago)\b",
        bio_lower,
    )
    if location_match:
        findings["location"] = location_match.group()
 
    return findings
 
 
def build_prompt(profile: dict, comments: list, flagged_following: list) -> str:
    profile_clean = {k: v for k, v in profile.items() if k != "following_list"}
    flagged_str   = (
        ", ".join(f"@{h}" for h in flagged_following)
        if flagged_following else "None"
    )
 
    # Run pre-scanner on bio
    bio = profile.get("bio", "") or ""
    pii_findings = prescan_bio(bio)
    pii_str = (
        f"BIO PII FINDINGS (score these under pii_exposure and bio_risk ONLY):\n"
        f"{json.dumps(pii_findings, ensure_ascii=False)}"
    ) if pii_findings else "None detected"
 
    return f"""
You are scoring an INSTAGRAM profile for online safety risk.
 
PROFILE DATA:
{json.dumps(profile_clean, ensure_ascii=False, indent=2)}
 
PRE-SCANNED PII FINDINGS (confirmed by regex — treat as facts, score them accordingly):
{pii_str}
 
COMMENTS UNDER THEIR POSTS ({min(len(comments), config.MAX_COMMENTS)} shown):
{json.dumps(comments[:config.MAX_COMMENTS], ensure_ascii=False, indent=2)}
 
FLAGGED ACCOUNTS IN THEIR FOLLOWING LIST:
{flagged_str}
 
SCORING RUBRIC (score each category from 0 to its max_points, total = 100):
{json.dumps(config.RISK_RUBRIC, ensure_ascii=False, indent=2)}
 
INSTRUCTIONS:
- The PRE-SCANNED PII FINDINGS are confirmed facts. You MUST score them.
- Score comment_disclosure and engagement_pattern from the COMMENTS only.
- Score every rubric category. Quote specific text or data as evidence.
- total_risk_score = sum of all category scores (must equal 0-100).
- risk_level: "LOW" (0-30), "MEDIUM" (31-60), "HIGH" (61-80), "CRITICAL" (81-100).
- Return ONLY this exact JSON structure, nothing else:
 
{{
  "username": "...",
  "platform": "instagram",
  "total_risk_score": <integer 0-100>,
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "category_scores": {{
    "pii_exposure":       {{"score": <int>, "evidence": "...", "reasoning": "..."}},
    "private_account":    {{"score": <int>, "evidence": "...", "reasoning": "..."}},
    "bio_risk":           {{"score": <int>, "evidence": "...", "reasoning": "..."}},
    "comment_disclosure": {{"score": <int>, "evidence": "...", "reasoning": "..."}},
    "network_risk":       {{"score": <int>, "evidence": "...", "reasoning": "..."}},
    "engagement_pattern": {{"score": <int>, "evidence": "...", "reasoning": "..."}}
  }},
  "top_recommendations": ["...", "...", "..."],
  "analyst_summary": "2-3 sentence plain-English summary for a parent or guardian."
}}
"""
 
 
def score_profile(
    profile: dict,
    comments: list,
    flagged_following: list,
) -> dict:
    """Score a profile locally using Ollama. Nothing is sent to any external API."""
    username = profile.get("username", "unknown")
    log.info("[Ollama] Scoring @%s with %s …", username, config.OLLAMA_MODEL)
 
    client = ollama.Client(host=f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}")
 
    # Trim comments before building prompt to avoid context overflow
    MAX_COMMENTS = 20
    MAX_COMMENT_LEN = 150
    trimmed_comments = [
        c[:MAX_COMMENT_LEN] if isinstance(c, str) else c
        for c in comments[:MAX_COMMENTS]
    ]
 
    prompt = build_prompt(profile, trimmed_comments, flagged_following)
    log.info("[Ollama] Prompt length: %d characters", len(prompt))
 
    try:
        response = client.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            format="json",
            options={
                "num_predict": 1024,
                "temperature": 0.1,
            },
        )
 
        raw = response.message.content.strip()
        log.info("[Ollama] Full raw response: %r", raw)
 
        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
 
        result = json.loads(raw)
 
        # ── Post-process: override values the model gets wrong ────────────────
 
        bio = profile.get("bio", "") or ""
        pii_findings = prescan_bio(bio)
 
        # 1. Force pii_exposure score from pre-scan findings
        pii_score = 0
        pii_evidence = []
        if "email" in pii_findings:
            pii_score += 7
            pii_evidence.append(f"Email: {pii_findings['email']}")
        if "phone" in pii_findings:
            pii_score += 10
            pii_evidence.append(f"Phone: {pii_findings['phone']}")
        if "institution" in pii_findings:
            pii_score += 8
            pii_evidence.append(f"Institution: {pii_findings['institution']}")
        pii_score = min(pii_score, 30)
        if "category_scores" not in result:
            result["category_scores"] = {}
        result["category_scores"]["pii_exposure"] = {
            "score":     pii_score,
            "evidence":  ", ".join(pii_evidence) if pii_evidence else "No PII detected",
            "reasoning": "Scored by pre-scanner.",
        }
 
        # 2. Force bio_risk score from pre-scan findings
        bio_score = 0
        bio_evidence = []
        if "age" in pii_findings or "grade" in pii_findings:
            bio_score += 5
            bio_evidence.append(f"Age/grade: {pii_findings.get('age') or pii_findings.get('grade')}")
        if "institution" in pii_findings:
            bio_score += 5
            bio_evidence.append("Institution in bio")
        if "location" in pii_findings:
            bio_score += 5
            bio_evidence.append(f"Location: {pii_findings['location']}")
        bio_score = min(bio_score, 15)
        result["category_scores"]["bio_risk"] = {
            "score":     bio_score,
            "evidence":  ", ".join(bio_evidence) if bio_evidence else "No bio risk detected",
            "reasoning": "Scored by pre-scanner.",
        }
 
        # 3. Force private_account score from actual scraped data
        visibility = profile.get("account_visibility", "public")
        result["category_scores"]["private_account"] = {
            "score":     10 if visibility == "public" else 0,
            "evidence":  f"account_visibility = '{visibility}'",
            "reasoning": "Public account has full exposure." if visibility == "public"
                         else "Private account restricts content access.",
        }
 
        # 4. Recalculate total from category scores
        computed_total = sum(
            v.get("score", 0)
            for v in result["category_scores"].values()
            if isinstance(v, dict)
        )
        result["total_risk_score"] = computed_total
 
        # 5. Recalculate risk_level from computed total
        score = result["total_risk_score"]
        if score <= 30:
            result["risk_level"] = "LOW"
        elif score <= 60:
            result["risk_level"] = "MEDIUM"
        elif score <= 80:
            result["risk_level"] = "HIGH"
        else:
            result["risk_level"] = "CRITICAL"
            
        # 6. Patch analyst summary risk level label to match computed level
        if "analyst_summary" in result:
            for old in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                result["analyst_summary"] = result["analyst_summary"].replace(
                    f"{old.lower()} risk level",
                    f"{result['risk_level'].lower()} risk level",
                )
 
        result["username"] = profile.get("username", result.get("username", "unknown"))
        result["platform"] = "instagram"
 
        log.info(
            "[Ollama] @%s → %d/100 (%s)",
            username,
            result.get("total_risk_score", 0),
            result.get("risk_level", "?"),
        )
        return result
 
    except json.JSONDecodeError:
        log.warning("[Ollama] JSON parse failed — attempting extraction fallback")
        return _extract_json_fallback(raw, username)
 
    except Exception as exc:
        log.error("[Ollama] Unexpected error for @%s: %s", username, exc)
        return _error_result(username, str(exc))
 
 
def _extract_json_fallback(raw: str, username: str) -> dict:
    """Try to extract a JSON object if the model wrapped it in extra text."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return _error_result(username, "Could not parse model output as JSON")
 
 
def _error_result(username: str, error: str) -> dict:
    return {
        "username":            username,
        "platform":            "instagram",
        "total_risk_score":    -1,
        "risk_level":          "ERROR",
        "category_scores":     {},
        "top_recommendations": [],
        "analyst_summary":     f"Scoring failed: {error}",
        "error":               error,
    }
 
 
def check_ollama_available() -> bool:
    try:
        client    = ollama.Client(host=f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}")
        models    = client.list()
        available = [m.model for m in models.models]
        base      = config.OLLAMA_MODEL.split(":")[0]
        found     = any(base in m for m in available)
        if not found:
            log.error("Model '%s' not found. Run: ollama pull %s",
                      config.OLLAMA_MODEL, config.OLLAMA_MODEL)
        return found
    except Exception as exc:
        log.error("Cannot reach Ollama: %s — is it running?", exc)
        return False