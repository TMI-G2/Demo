"""
dashboard.py
-------------
Lightweight results dashboard server.
Serves a webpage showing the latest risk assessment result.
Auto-refreshes every 5 seconds.

Run this alongside server.py:
  python dashboard.py

Then open on any device on your Tailscale network:
  http://100.x.x.x:5000
"""

import json
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# In-memory result store — no files written to disk
_latest_result: dict = {}


def store_result(result: dict) -> None:
    """Called by instagram_transform after scoring. Stores result in memory."""
    global _latest_result
    _latest_result = result

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TMI Risk Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --border: #1e1e2e;
    --text: #e2e2f0;
    --muted: #6b6b8a;
    --low: #00d68f;
    --medium: #f5c518;
    --high: #ff6b35;
    --critical: #ff2052;
    --accent: #7c6aff;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    padding: 2rem;
  }

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(124,106,255,0.12), transparent);
    pointer-events: none;
    z-index: 0;
  }

  .container { max-width: 960px; margin: 0 auto; position: relative; z-index: 1; }

  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 2.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
  }

  .logo {
    font-size: 1.1rem;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .status-dot {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
  }

  .dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--low);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  #no-data {
    text-align: center;
    padding: 6rem 2rem;
    color: var(--muted);
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    line-height: 2;
  }

  #no-data .big { font-size: 3rem; margin-bottom: 1rem; opacity: 0.3; }

  .result { animation: fadeIn 0.4s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

  .profile-header {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: start;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .username {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1;
  }

  .username span { color: var(--muted); font-weight: 400; }

  .meta {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 0.5rem;
    line-height: 1.8;
  }

  .score-block {
    text-align: right;
  }

  .score-number {
    font-size: 4rem;
    font-weight: 800;
    line-height: 1;
    font-family: 'Space Mono', monospace;
  }

  .score-label {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-top: 0.3rem;
    padding: 0.25rem 0.75rem;
    border-radius: 2rem;
    display: inline-block;
  }

  .risk-LOW    { color: var(--low);      }
  .risk-MEDIUM { color: var(--medium);   }
  .risk-HIGH   { color: var(--high);     }
  .risk-CRITICAL { color: var(--critical); }
  .risk-ERROR  { color: var(--muted);    }

  .badge-LOW      { background: rgba(0,214,143,0.12);  color: var(--low);      }
  .badge-MEDIUM   { background: rgba(245,197,24,0.12); color: var(--medium);   }
  .badge-HIGH     { background: rgba(255,107,53,0.12); color: var(--high);     }
  .badge-CRITICAL { background: rgba(255,32,82,0.12);  color: var(--critical); }
  .badge-ERROR    { background: rgba(107,107,138,0.12); color: var(--muted);   }

  .score-bar-wrap {
    background: var(--border);
    border-radius: 4px;
    height: 6px;
    margin-bottom: 2rem;
    overflow: hidden;
  }

  .score-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 1s cubic-bezier(0.4,0,0.2,1);
  }

  .section-title {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 1rem;
  }

  .categories {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin-bottom: 2rem;
  }

  .cat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.2rem;
  }

  .cat-name {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }

  .cat-score-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }

  .cat-score { font-size: 1.4rem; font-weight: 800; font-family: 'Space Mono', monospace; }
  .cat-max   { font-size: 0.75rem; color: var(--muted); font-family: 'Space Mono', monospace; }

  .cat-bar-wrap { background: var(--border); border-radius: 4px; height: 3px; overflow: hidden; }
  .cat-bar      { height: 100%; border-radius: 4px; background: var(--accent); }

  .cat-evidence {
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 0.6rem;
    line-height: 1.5;
    font-family: 'Space Mono', monospace;
  }

  .summary-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 2rem;
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text);
  }

  .recs { margin-bottom: 2rem; }

  .rec {
    display: flex;
    gap: 1rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .rec:last-child { border-bottom: none; }
  .rec-num {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--accent);
    padding-top: 0.15rem;
    min-width: 1.5rem;
  }

  .hibp-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.85rem;
  }

  .hibp-label { color: var(--muted); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; }
  .hibp-val   { font-family: 'Space Mono', monospace; font-weight: 700; }

  footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">TMI · Risk Dashboard</div>
    <div class="status-dot"><div class="dot"></div> LIVE · auto-refresh 5s</div>
  </header>

  <div id="content">
    <div id="no-data">
      <div class="big">◎</div>
      Waiting for a risk assessment to run...<br>
      Run a transform in Maltego or trigger the pipeline to see results here.
    </div>
  </div>

  <footer>
    <span id="scored-at">—</span>
    <span>data processed locally · zero cloud scoring</span>
  </footer>
</div>

<script>
const RISK_COLORS = {
  LOW: 'var(--low)',
  MEDIUM: 'var(--medium)',
  HIGH: 'var(--high)',
  CRITICAL: 'var(--critical)',
  ERROR: 'var(--muted)'
};

const CAT_LABELS = {
  pii_exposure: 'PII Exposure',
  private_account: 'Account Privacy',
  bio_risk: 'Bio Risk',
  comment_disclosure: 'Comment Disclosure',
  network_risk: 'Network Risk',
  engagement_pattern: 'Engagement Pattern',
  breach_exposure: 'Breach Exposure'
};

let lastUsername = null;

async function fetchResult() {
  try {
    const res = await fetch('/api/latest');
    if (!res.ok) return;
    const data = await res.json();
    if (!data || data.error) return;
    if (data.username === lastUsername && data.scored_at === window._lastScored) return;
    lastUsername = data.username;
    window._lastScored = data.scored_at;
    render(data);
  } catch(e) {}
}

function bar(pct, color) {
  return `<div style="background:var(--border);border-radius:4px;height:3px;overflow:hidden;margin-top:0.4rem">
    <div style="height:100%;width:${pct}%;background:${color};border-radius:4px;transition:width 1s"></div>
  </div>`;
}

function render(d) {
  const risk = d.risk_level || 'ERROR';
  const score = d.total_risk_score ?? 0;
  const color = RISK_COLORS[risk] || RISK_COLORS.ERROR;
  const cats = d.category_scores || {};
  const recs = d.top_recommendations || [];
  const meta = d._meta || {};

  let catHTML = '';
  for (const [key, val] of Object.entries(cats)) {
    const s = val.score ?? 0;
    const max = val.max ?? 30;
    const pct = Math.min(100, (s / (max || 30)) * 100);
    const evidence = val.evidence || '';
    catHTML += `<div class="cat-card">
      <div class="cat-name">${CAT_LABELS[key] || key}</div>
      <div class="cat-score-row">
        <span class="cat-score" style="color:${color}">${s}</span>
        <span class="cat-max">/ ${max}</span>
      </div>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${pct}%;background:${color}"></div></div>
      ${evidence ? `<div class="cat-evidence">${evidence.slice(0,120)}${evidence.length>120?'…':''}</div>` : ''}
    </div>`;
  }

  let recHTML = recs.map((r, i) =>
    `<div class="rec"><span class="rec-num">0${i+1}</span><span>${r}</span></div>`
  ).join('');

  const hibpIncluded = d.hibp_included;
  let hibpHTML = '';
  if (hibpIncluded !== undefined) {
    hibpHTML = `<div class="hibp-row">
      <span class="hibp-label">HIBP Breach Check</span>
      <span class="hibp-val" style="color:${hibpIncluded ? color : 'var(--muted)'}">
        ${hibpIncluded ? `${meta.hibp_breaches ?? 0} breach(es) found` : 'Not checked — no email provided'}
      </span>
    </div>`;
  }

  const scoredAt = meta.scraped_at || d.scored_at || '';
  document.getElementById('scored-at').textContent = scoredAt ? `scored ${scoredAt}` : '—';

  document.getElementById('content').innerHTML = `
    <div class="result">
      <div class="profile-header">
        <div>
          <div class="username"><span>@</span>${d.username || '—'}</div>
          <div class="meta">
            platform: ${d.platform || 'instagram'}<br>
            comments analysed: ${meta.comments_analysed ?? '—'}<br>
            following list size: ${meta.following_list_size ?? '—'}<br>
            model: ${meta.model_used || '—'}
          </div>
        </div>
        <div class="score-block">
          <div class="score-number risk-${risk}">${score}</div>
          <div class="score-label badge-${risk}">${risk}</div>
        </div>
      </div>

      <div class="score-bar-wrap">
        <div class="score-bar" style="width:${score}%;background:${color}"></div>
      </div>

      ${d.analyst_summary ? `
        <div class="section-title">Analyst Summary</div>
        <div class="summary-box">${d.analyst_summary}</div>
      ` : ''}

      ${hibpHTML}

      <div class="section-title">Category Breakdown</div>
      <div class="categories">${catHTML}</div>

      ${recs.length ? `
        <div class="section-title">Recommendations</div>
        <div class="recs">${recHTML}</div>
      ` : ''}
    </div>`;
}

fetchResult();
setInterval(fetchResult, 5000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/latest")
def latest():
    """Return the most recent in-memory risk result."""
    if not _latest_result:
        return jsonify({"error": "no results yet"}), 404
    return jsonify(_latest_result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
