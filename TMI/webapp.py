"""
webapp.py
----------
Front-facing web application for Instagram PII risk scoring.
Runs on port 5001 (separate from the Maltego transform server on 8080).

Start with:
  python webapp.py

Then open in any browser on your network:
  http://localhost:5001          (desktop)
  http://100.x.x.x:5001         (laptop via Tailscale)

The page accepts an Instagram username, runs the full pipeline
(Apify scrape → Ollama scoring), and displays results on the same page.
No data is stored. Nothing is sent to external AI services.
"""

import sys
import os

# Add parent directory to path so we can import existing pipeline modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import threading
from flask import Flask, request, jsonify, render_template_string

import config
from utils.apify_scraper import fetch_instagram_profile, fetch_instagram_comments
from utils.ollama_scorer import score_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory job store — maps job_id → result dict
# No files written to disk, no data persisted between sessions
_jobs: dict = {}
_jobs_lock = threading.Lock()


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TMI — Know Your Exposure</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:         #F7F8FC;
    --surface:    #FFFFFF;
    --border:     #E4E7EF;
    --text:       #111827;
    --muted:      #6B7280;
    --accent:     #2563EB;
    --accent-lt:  #EFF6FF;
    --low:        #059669;
    --low-lt:     #ECFDF5;
    --medium:     #D97706;
    --medium-lt:  #FFFBEB;
    --high:       #DC2626;
    --high-lt:    #FEF2F2;
    --critical:   #7C3AED;
    --critical-lt:#F5F3FF;
    --radius:     12px;
    --radius-sm:  8px;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    line-height: 1.6;
    min-height: 100vh;
  }

  /* ── Layout ── */
  .page { max-width: 680px; margin: 0 auto; padding: 3rem 1.5rem 6rem; }

  /* ── Header ── */
  .site-header { margin-bottom: 3rem; }
  .wordmark {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.5rem;
    display: block;
  }
  h1 {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin-bottom: 0.75rem;
  }
  .subtitle {
    color: var(--muted);
    font-size: 0.95rem;
    max-width: 480px;
  }

  /* ── Form card ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.75rem;
    margin-bottom: 1.5rem;
  }

  .form-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }

  .input-row {
    display: flex;
    gap: 0.75rem;
    align-items: stretch;
  }

  .handle-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    border: 1.5px solid var(--border);
    border-radius: var(--radius-sm);
    overflow: hidden;
    transition: border-color 0.15s;
    background: var(--bg);
  }

  .handle-wrap:focus-within {
    border-color: var(--accent);
    background: #fff;
  }

  .at-sign {
    padding: 0 0.75rem;
    color: var(--muted);
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    user-select: none;
  }

  input[type="text"] {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    color: var(--text);
    padding: 0.75rem 0.75rem 0.75rem 0;
  }

  input[type="text"]::placeholder { color: var(--border); }

  button[type="submit"] {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    padding: 0 1.5rem;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s, transform 0.1s;
  }

  button[type="submit"]:hover { background: #1d4ed8; }
  button[type="submit"]:active { transform: scale(0.98); }
  button[type="submit"]:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; }

  .privacy-note {
    margin-top: 0.85rem;
    font-size: 0.78rem;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .privacy-note::before {
    content: "🔒";
    font-size: 0.75rem;
  }

  /* ── Loading state ── */
  #loading {
    display: none;
    text-align: center;
    padding: 3rem 1rem;
    color: var(--muted);
  }

  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .loading-steps { font-size: 0.82rem; line-height: 2; }
  .loading-step { opacity: 0.4; transition: opacity 0.3s; }
  .loading-step.active { opacity: 1; color: var(--accent); }
  .loading-step.done { opacity: 0.6; }
  .loading-step.done::after { content: " ✓"; }

  /* ── Error state ── */
  #error {
    display: none;
    background: var(--high-lt);
    border: 1px solid #FECACA;
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    color: var(--high);
    font-size: 0.9rem;
  }

  /* ── Results ── */
  #results { display: none; }

  /* Score hero */
  .score-hero {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    margin-bottom: 1rem;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 1.5rem;
    align-items: center;
  }

  .score-handle {
    font-family: 'Space Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }

  .score-handle span { color: var(--muted); font-weight: 400; }

  .score-meta {
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 0.5rem;
  }

  .score-display { text-align: right; }

  .score-number {
    font-family: 'Space Mono', monospace;
    font-size: 3.5rem;
    font-weight: 700;
    line-height: 1;
  }

  .score-badge {
    display: inline-block;
    margin-top: 0.4rem;
    padding: 0.2rem 0.75rem;
    border-radius: 2rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .score-bar-wrap {
    grid-column: 1 / -1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  .score-bar {
    height: 100%;
    border-radius: 3px;
    width: 0;
    transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  /* Risk colour themes */
  .risk-LOW      { color: var(--low);      }
  .risk-MEDIUM   { color: var(--medium);   }
  .risk-HIGH     { color: var(--high);     }
  .risk-CRITICAL { color: var(--critical); }

  .badge-LOW      { background: var(--low-lt);      color: var(--low);      }
  .badge-MEDIUM   { background: var(--medium-lt);   color: var(--medium);   }
  .badge-HIGH     { background: var(--high-lt);     color: var(--high);     }
  .badge-CRITICAL { background: var(--critical-lt); color: var(--critical); }

  .bar-LOW      { background: var(--low);      }
  .bar-MEDIUM   { background: var(--medium);   }
  .bar-HIGH     { background: var(--high);     }
  .bar-CRITICAL { background: var(--critical); }

  /* Summary */
  .summary-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text);
  }

  /* Categories */
  .section-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.75rem;
    margin-top: 1.5rem;
  }

  .categories { display: flex; flex-direction: column; gap: 0.5rem; }

  .cat-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 1rem 1.25rem;
  }

  .cat-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.4rem;
  }

  .cat-name {
    font-size: 0.85rem;
    font-weight: 500;
  }

  .cat-score {
    font-family: 'Space Mono', monospace;
    font-size: 0.8rem;
    color: var(--muted);
  }

  .cat-bar-wrap {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .cat-bar {
    height: 100%;
    border-radius: 2px;
    background: var(--accent);
    width: 0;
    transition: width 1s ease 0.3s;
  }

  .cat-evidence {
    font-size: 0.75rem;
    color: var(--muted);
    font-family: 'Space Mono', monospace;
    line-height: 1.5;
  }

  /* Recommendations */
  .recs { display: flex; flex-direction: column; gap: 0.5rem; }

  .rec-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.85rem 1.25rem;
    font-size: 0.875rem;
    line-height: 1.5;
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .rec-icon {
    color: var(--accent);
    font-size: 0.75rem;
    margin-top: 0.15rem;
    flex-shrink: 0;
  }

  /* Footer */
  .site-footer {
    margin-top: 4rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--muted);
    text-align: center;
    line-height: 1.8;
  }

  /* Responsive */
  @media (max-width: 500px) {
    .input-row { flex-direction: column; }
    button[type="submit"] { padding: 0.75rem; }
    .score-hero { grid-template-columns: 1fr; }
    .score-display { text-align: left; }
  }
</style>
</head>
<body>
<div class="page">

  <header class="site-header">
    <span class="wordmark">TMI · Privacy Check</span>
    <h1>How exposed are you online?</h1>
    <p class="subtitle">Enter your Instagram username and we'll scan your public profile for personally identifiable information and privacy risks.</p>
  </header>

  <div class="card">
    <label class="form-label" for="username-input">Instagram username</label>
    <div class="input-row">
      <div class="handle-wrap">
        <span class="at-sign">@</span>
        <input
          type="text"
          id="username-input"
          placeholder="yourhandle"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
        >
      </div>
      <button type="submit" id="check-btn" onclick="startCheck()">Check</button>
    </div>
    <p class="privacy-note">Your username is only used to fetch public profile data. No information is stored or shared.</p>
  </div>

  <div id="loading">
    <div class="spinner"></div>
    <div class="loading-steps">
      <div class="loading-step" id="step-1">Fetching profile from Instagram</div>
      <div class="loading-step" id="step-2">Analysing comments and bio</div>
      <div class="loading-step" id="step-3">Calculating risk score</div>
    </div>
  </div>

  <div id="error"></div>

  <div id="results"></div>

  <footer class="site-footer">
    Analysis runs locally on private infrastructure.<br>
    No data is sent to third-party AI services. Scoring is powered by a local language model.
  </footer>

</div>

<script>
const CAT_LABELS = {
  pii_exposure:       'Personal Information in Profile',
  private_account:    'Account Privacy',
  bio_risk:           'Bio Content Risk',
  comment_disclosure: 'Information Shared in Comments',
  network_risk:       'Connections & Following List',
  engagement_pattern: 'Engagement with Strangers',
};

const RISK_COLORS = {
  LOW:      '#059669',
  MEDIUM:   '#D97706',
  HIGH:     '#DC2626',
  CRITICAL: '#7C3AED',
};

let pollTimer = null;

function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById('step-' + i);
    if (i < n) { el.className = 'loading-step done'; }
    else if (i === n) { el.className = 'loading-step active'; }
    else { el.className = 'loading-step'; }
  }
}

async function startCheck() {
  const input = document.getElementById('username-input');
  const username = input.value.trim().replace(/^@/, '');
  if (!username) { input.focus(); return; }

  // Reset UI
  document.getElementById('check-btn').disabled = true;
  document.getElementById('error').style.display = 'none';
  document.getElementById('results').style.display = 'none';
  document.getElementById('loading').style.display = 'block';
  setStep(1);

  try {
    // Start the job
    const startRes = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });

    if (!startRes.ok) {
      const err = await startRes.json();
      throw new Error(err.error || 'Failed to start assessment.');
    }

    const { job_id } = await startRes.json();

    // Poll for result
    let dots = 0;
    pollTimer = setInterval(async () => {
      dots++;
      if (dots < 15) setStep(1);
      else if (dots < 30) setStep(2);
      else setStep(3);

      try {
        const pollRes = await fetch('/api/result/' + job_id);
        if (!pollRes.ok) return;
        const data = await pollRes.json();

        if (data.status === 'done') {
          clearInterval(pollTimer);
          showResults(data.result);
        } else if (data.status === 'error') {
          clearInterval(pollTimer);
          showError(data.message || 'Assessment failed. Please try again.');
        }
      } catch (e) {
        // Keep polling
      }
    }, 2000);

  } catch (err) {
    showError(err.message);
  }
}

function showError(msg) {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('check-btn').disabled = false;
  const errEl = document.getElementById('error');
  errEl.style.display = 'block';
  errEl.textContent = msg;
}

function showResults(d) {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('check-btn').disabled = false;

  const risk  = d.risk_level || 'LOW';
  const score = d.total_risk_score ?? 0;
  const cats  = d.category_scores || {};
  const recs  = d.top_recommendations || [];
  const color = RISK_COLORS[risk] || RISK_COLORS.LOW;

  // Category rows
  let catsHTML = '';
  for (const [key, val] of Object.entries(cats)) {
    const s   = val.score ?? 0;
    const max = getMax(key);
    const pct = max > 0 ? Math.min(100, (s / max) * 100) : 0;
    const ev  = val.evidence || '';
    catsHTML += `
      <div class="cat-row">
        <div class="cat-top">
          <span class="cat-name">${CAT_LABELS[key] || key}</span>
          <span class="cat-score">${s} / ${max}</span>
        </div>
        <div class="cat-bar-wrap">
          <div class="cat-bar" data-pct="${pct}" style="background:${color}"></div>
        </div>
        ${ev && ev !== 'None detected' && ev !== 'None' && ev !== '[]'
          ? `<div class="cat-evidence">${ev.slice(0, 140)}${ev.length > 140 ? '…' : ''}</div>`
          : ''}
      </div>`;
  }

  // Recommendations
  let recsHTML = recs.map(r => `
    <div class="rec-item">
      <span class="rec-icon">→</span>
      <span>${r}</span>
    </div>`).join('');

  const platform = (d.platform || 'instagram').charAt(0).toUpperCase() + (d.platform || 'instagram').slice(1);

  document.getElementById('results').innerHTML = `
    <div class="score-hero">
      <div>
        <div class="score-handle"><span>@</span>${d.username || '—'}</div>
        <div class="score-meta">${platform} · public profile analysis</div>
      </div>
      <div class="score-display">
        <div class="score-number risk-${risk}">${score}</div>
        <div class="score-badge badge-${risk}">${risk}</div>
      </div>
      <div class="score-bar-wrap">
        <div class="score-bar bar-${risk}" id="main-bar"></div>
      </div>
    </div>

    ${d.analyst_summary ? `<div class="summary-card">${d.analyst_summary}</div>` : ''}

    <div class="section-label">Risk breakdown</div>
    <div class="categories">${catsHTML}</div>

    ${recs.length ? `
      <div class="section-label">What you can do</div>
      <div class="recs">${recsHTML}</div>
    ` : ''}
  `;

  document.getElementById('results').style.display = 'block';

  // Animate bars after render
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const mainBar = document.getElementById('main-bar');
      if (mainBar) mainBar.style.width = score + '%';
      document.querySelectorAll('.cat-bar[data-pct]').forEach(b => {
        b.style.width = b.dataset.pct + '%';
      });
    });
  });

  document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function getMax(category) {
  const maxes = {
    pii_exposure: 30, private_account: 10, bio_risk: 15,
    comment_disclosure: 20, network_risk: 15, engagement_pattern: 10,
  };
  return maxes[category] || 10;
}

// Allow Enter key to submit
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('username-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') startCheck();
  });
});
</script>
</body>
</html>"""


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/check", methods=["POST"])
def check():
    """
    Start a risk assessment job for the given Instagram username.
    Returns a job_id immediately — client polls /api/result/<job_id>.
    """
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip().lstrip("@")

    if not username:
        return jsonify({"error": "No username provided."}), 400

    import uuid
    job_id = str(uuid.uuid4())

    with _jobs_lock:
        _jobs[job_id] = {"status": "running"}

    # Run pipeline in background thread so request returns immediately
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, username),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/result/<job_id>")
def result(job_id):
    """Poll endpoint — returns job status and result when ready."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"status": "not_found"}), 404

    return jsonify(job)


# ── Pipeline runner ───────────────────────────────────────────────────────────

def _run_pipeline(job_id: str, username: str):
    """
    Runs the full Instagram risk pipeline in a background thread.
    Updates _jobs[job_id] when complete.
    """
    try:
        log.info("[WebApp] Starting assessment for @%s (job %s)", username, job_id)

        # 1. Fetch profile
        profile = fetch_instagram_profile(username)
        if not profile:
            _set_job_error(job_id, f"Could not find Instagram profile @{username}. Check the username is correct.")
            return

        # 2. Fetch comments (public accounts only)
        comments = []
        if not profile.get("is_private"):
            comments = fetch_instagram_comments(username, profile.get("post_urls", []))

        # 3. Score with Ollama
        result = score_profile(profile, comments, flagged_following=[])

        if result.get("risk_level") == "ERROR":
            _set_job_error(job_id, "Scoring failed. Please try again in a moment.")
            return

        # 4. Mark job complete
        with _jobs_lock:
            _jobs[job_id] = {"status": "done", "result": result}

        log.info(
            "[WebApp] @%s complete → %d/100 (%s)",
            username,
            result.get("total_risk_score", 0),
            result.get("risk_level", "?"),
        )

    except Exception as exc:
        log.error("[WebApp] Pipeline error for @%s: %s", username, exc)
        _set_job_error(job_id, "An unexpected error occurred. Please try again.")


def _set_job_error(job_id: str, message: str):
    with _jobs_lock:
        _jobs[job_id] = {"status": "error", "message": message}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("TMI Risk Web App starting on http://0.0.0.0:5001")
    log.info("Open on laptop: http://%s:5001", config.OLLAMA_HOST)
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
