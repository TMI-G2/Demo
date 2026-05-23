import { useState, useCallback } from "react";

// ─── Risk Scoring Engine ───────────────────────────────────────────────────
const RISK_FACTORS = {
  password_reuse:       { weight: 20, label: "Password Reuse Detected",        category: "Authentication" },
  mfa_disabled:         { weight: 15, label: "MFA Not Enabled",                category: "Authentication" },
  public_email:         { weight: 10, label: "Email Exposed Publicly",         category: "Privacy" },
  data_breach:          { weight: 25, label: "Found in Data Breaches",         category: "Breach History" },
  weak_username:        { weight:  5, label: "Predictable Username Pattern",   category: "Identity" },
  over_sharing:         { weight: 10, label: "Over-sharing on Social Media",   category: "Privacy" },
  old_accounts:         { weight:  5, label: "Inactive Old Accounts",         category: "Hygiene" },
  http_domains:         { weight: 15, label: "Uses HTTP (non-HTTPS) Sites",   category: "Network" },
  geolocation_exposed:  { weight: 10, label: "Geolocation Metadata Exposed",  category: "Privacy" },
  phishing_susceptible: { weight: 15, label: "Linked to Phishing Indicators", category: "Threat Intel" },
};

function computeRiskScore(flags) {
  let score = 0;
  for (const [key, active] of Object.entries(flags)) {
    if (active && RISK_FACTORS[key]) score += RISK_FACTORS[key].weight;
  }
  return Math.min(score, 100);
}

function getRiskLevel(score) {
  if (score >= 70) return { label: "CRITICAL", color: "#ff2d55", bg: "#2a0010" };
  if (score >= 45) return { label: "HIGH",     color: "#ff9f0a", bg: "#2a1800" };
  if (score >= 20) return { label: "MEDIUM",   color: "#ffd60a", bg: "#2a2200" };
  return               { label: "LOW",      color: "#30d158", bg: "#00200a" };
}

// ─── CSV Generator ────────────────────────────────────────────────────────
function generateCSV(records) {
  const headers = [
    "Username","Platform","URL","Email_Exposed","Data_Breach","MFA_Disabled",
    "Password_Reuse","Over_Sharing","HTTP_Domains","Geolocation_Exposed",
    "Old_Accounts","Weak_Username","Phishing_Susceptible","Risk_Score","Risk_Level"
  ];
  const rows = records.map(r => {
    const score = computeRiskScore(r.flags);
    const level = getRiskLevel(score).label;
    return [
      r.username, r.platform, r.url,
      r.flags.public_email       ? 1 : 0,
      r.flags.data_breach        ? 1 : 0,
      r.flags.mfa_disabled       ? 1 : 0,
      r.flags.password_reuse     ? 1 : 0,
      r.flags.over_sharing       ? 1 : 0,
      r.flags.http_domains       ? 1 : 0,
      r.flags.geolocation_exposed? 1 : 0,
      r.flags.old_accounts       ? 1 : 0,
      r.flags.weak_username      ? 1 : 0,
      r.flags.phishing_susceptible?1 : 0,
      score, level
    ].join(",");
  });
  return [headers.join(","), ...rows].join("\n");
}

// ─── AI Analysis via Claude ───────────────────────────────────────────────
async function analyzeWithClaude(record) {
  const flagList = Object.entries(record.flags)
    .filter(([, v]) => v)
    .map(([k]) => RISK_FACTORS[k]?.label || k)
    .join(", ");

  const prompt = `You are a cybersecurity analyst. Analyze this social media account's cyber hygiene data and provide a concise risk assessment.

Subject: ${record.username} on ${record.platform}
URL: ${record.url}
Risk Indicators Found: ${flagList || "None"}
Risk Score: ${computeRiskScore(record.flags)}/100

Respond in JSON only (no markdown) with this structure:
{
  "summary": "2-3 sentence executive summary of the risk profile",
  "top_risks": ["top 3 most critical risks as short strings"],
  "recommendations": ["3 actionable recommendations"],
  "threat_actors": "likely threat actor interest level: Low/Medium/High",
  "exposure_type": "primary exposure type in 4 words max"
}`;

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      messages: [{ role: "user", content: prompt }]
    })
  });
  const data = await res.json();
  const text = data.content?.find(b => b.type === "text")?.text || "{}";
  try { return JSON.parse(text.replace(/```json|```/g, "").trim()); }
  catch { return null; }
}

// ─── Sample / Parse Maltego Input ────────────────────────────────────────
function parseMaltegoInput(raw) {
  // Accepts newline-separated lines: username | platform | url | comma-flags
  // e.g.: johndoe123 | Twitter | https://twitter.com/johndoe123 | data_breach,mfa_disabled
  const lines = raw.trim().split("\n").filter(l => l.trim());
  return lines.map((line, i) => {
    const parts = line.split("|").map(s => s.trim());
    const [username = `user_${i}`, platform = "Unknown", url = "", flagStr = ""] = parts;
    const flagKeys = flagStr.split(",").map(f => f.trim()).filter(Boolean);
    const flags = {};
    Object.keys(RISK_FACTORS).forEach(k => { flags[k] = flagKeys.includes(k); });
    return { id: i, username, platform, url, flags };
  });
}

const SAMPLE_INPUT = `johndoe1990 | Twitter | https://twitter.com/johndoe1990 | data_breach,mfa_disabled,public_email,over_sharing
jane.doe | LinkedIn | https://linkedin.com/in/jane-doe | weak_username,old_accounts,geolocation_exposed
hackme2020 | GitHub | https://github.com/hackme2020 | password_reuse,http_domains,data_breach,phishing_susceptible
sarah_smith | Instagram | https://instagram.com/sarah_smith | over_sharing,geolocation_exposed,public_email
corp_admin | Reddit | https://reddit.com/u/corp_admin | mfa_disabled,weak_username,password_reuse,old_accounts`;

// ─── UI Components ────────────────────────────────────────────────────────
const ScoreRing = ({ score }) => {
  const level = getRiskLevel(score);
  const r = 36, c = 2 * Math.PI * r;
  const dash = (score / 100) * c;
  return (
    <svg width="100" height="100" viewBox="0 0 100 100" style={{ transform: "rotate(-90deg)" }}>
      <circle cx="50" cy="50" r={r} fill="none" stroke="#1a1a2e" strokeWidth="10"/>
      <circle cx="50" cy="50" r={r} fill="none" stroke={level.color}
        strokeWidth="10" strokeDasharray={`${dash} ${c - dash}`}
        strokeLinecap="round" style={{ transition: "stroke-dasharray 1s ease" }}/>
      <text x="50" y="58" textAnchor="middle" fill={level.color}
        style={{ font: "bold 18px monospace", transform: "rotate(90deg)", transformOrigin: "50px 50px" }}>
        {score}
      </text>
    </svg>
  );
};

export default function MaltegoRiskAgent() {
  const [input, setInput]         = useState(SAMPLE_INPUT);
  const [records, setRecords]     = useState([]);
  const [selected, setSelected]   = useState(null);
  const [analysis, setAnalysis]   = useState({});
  const [loadingAI, setLoadingAI] = useState(null);
  const [processed, setProcessed] = useState(false);
  const [tab, setTab]             = useState("dashboard");

  const handleProcess = useCallback(() => {
    const parsed = parseMaltegoInput(input);
    setRecords(parsed);
    setSelected(parsed[0] || null);
    setAnalysis({});
    setProcessed(true);
    setTab("dashboard");
  }, [input]);

  const handleAnalyze = useCallback(async (record) => {
    setLoadingAI(record.id);
    const result = await analyzeWithClaude(record);
    setAnalysis(prev => ({ ...prev, [record.id]: result }));
    setLoadingAI(null);
  }, []);

  const handleCSVDownload = useCallback(() => {
    if (!records.length) return;
    const csv = generateCSV(records);
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "maltego_risk_report.csv"; a.click();
    URL.revokeObjectURL(url);
  }, [records]);

  const avgScore = records.length
    ? Math.round(records.reduce((s, r) => s + computeRiskScore(r.flags), 0) / records.length) : 0;

  const criticalCount = records.filter(r => computeRiskScore(r.flags) >= 70).length;

  // Styles
  const S = {
    app: {
      minHeight: "100vh", background: "#080b14",
      color: "#e0e6f0", fontFamily: "'Space Mono', 'Courier New', monospace",
      display: "flex", flexDirection: "column"
    },
    header: {
      background: "linear-gradient(135deg, #0d1117 0%, #0a0f1e 100%)",
      borderBottom: "1px solid #1e293b",
      padding: "18px 28px", display: "flex", alignItems: "center", gap: 16,
      boxShadow: "0 2px 20px rgba(0,200,255,0.05)"
    },
    logo: { display: "flex", alignItems: "center", gap: 10 },
    hexBadge: {
      width: 38, height: 38,
      background: "linear-gradient(135deg, #00d4ff, #0066ff)",
      clipPath: "polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 18
    },
    title: { fontSize: 18, fontWeight: 700, letterSpacing: 2,
      background: "linear-gradient(90deg, #00d4ff, #6a8fff)", WebkitBackgroundClip: "text",
      WebkitTextFillColor: "transparent" },
    subtitle: { fontSize: 10, color: "#4a6080", letterSpacing: 3, marginTop: 2 },
    main: { display: "flex", flex: 1, overflow: "hidden" },
    sidebar: {
      width: 260, background: "#0a0d16", borderRight: "1px solid #131926",
      display: "flex", flexDirection: "column", overflow: "hidden"
    },
    sidebarHeader: { padding: "14px 16px", borderBottom: "1px solid #131926",
      fontSize: 10, letterSpacing: 2, color: "#3a5070" },
    sidebarItem: (active) => ({
      padding: "12px 16px", cursor: "pointer", borderLeft: `3px solid ${active ? "#00d4ff" : "transparent"}`,
      background: active ? "rgba(0,212,255,0.05)" : "transparent",
      transition: "all 0.2s", display: "flex", alignItems: "center", gap: 10,
      borderBottom: "1px solid #0d1020"
    }),
    content: { flex: 1, overflow: "auto", padding: 24 },
    card: {
      background: "#0d1117", border: "1px solid #1e293b",
      borderRadius: 8, padding: 20, marginBottom: 16
    },
    statGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 },
    stat: {
      background: "#0a0d16", border: "1px solid #1a2535",
      borderRadius: 8, padding: 16, textAlign: "center"
    },
    statVal: { fontSize: 32, fontWeight: 700, lineHeight: 1 },
    statLabel: { fontSize: 10, color: "#4a6080", letterSpacing: 2, marginTop: 6 },
    table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
    th: { padding: "10px 12px", textAlign: "left", borderBottom: "1px solid #1a2535",
      color: "#3a6080", fontSize: 10, letterSpacing: 2 },
    td: { padding: "10px 12px", borderBottom: "1px solid #0d1020" },
    badge: (color, bg) => ({
      display: "inline-block", padding: "2px 8px", borderRadius: 3,
      fontSize: 10, fontWeight: 700, letterSpacing: 1,
      color, background: bg, border: `1px solid ${color}33`
    }),
    btn: (primary) => ({
      padding: "9px 18px", borderRadius: 5, border: "none", cursor: "pointer",
      fontFamily: "inherit", fontSize: 11, fontWeight: 700, letterSpacing: 1.5,
      background: primary ? "linear-gradient(135deg, #00d4ff, #0066ff)" : "#1a2535",
      color: primary ? "#000" : "#8ab", transition: "all 0.2s"
    }),
    textarea: {
      width: "100%", background: "#060810", border: "1px solid #1a2535",
      borderRadius: 6, color: "#8ab8d0", fontFamily: "inherit",
      fontSize: 11, padding: 14, resize: "vertical", minHeight: 180,
      lineHeight: 1.7, outline: "none", boxSizing: "border-box"
    },
    flagRow: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 },
    flag: (active) => ({
      padding: "3px 10px", borderRadius: 3, fontSize: 10,
      background: active ? "rgba(255,45,85,0.15)" : "#0d1117",
      color: active ? "#ff6b8a" : "#2a3a4a",
      border: `1px solid ${active ? "#ff2d5533" : "#1a2535"}`,
      cursor: "pointer", transition: "all 0.2s"
    }),
    analysisBox: {
      background: "#080c14", border: "1px solid #0d3a4a",
      borderRadius: 8, padding: 18, marginTop: 16
    },
    recItem: { padding: "8px 0", borderBottom: "1px solid #0d1020",
      color: "#7ab", fontSize: 12, display: "flex", gap: 8, alignItems: "flex-start" },
    tabs: { display: "flex", gap: 2, marginBottom: 20, borderBottom: "1px solid #131926" },
    tabBtn: (active) => ({
      padding: "10px 20px", background: "none", border: "none",
      borderBottom: `2px solid ${active ? "#00d4ff" : "transparent"}`,
      color: active ? "#00d4ff" : "#3a5070", cursor: "pointer",
      fontFamily: "inherit", fontSize: 11, letterSpacing: 1.5, fontWeight: 700,
      transition: "all 0.2s", marginBottom: -1
    }),
    inputFormat: {
      background: "#060810", border: "1px solid #0d3a4a",
      borderRadius: 6, padding: 14, fontSize: 11, color: "#3a6070",
      lineHeight: 1.8, marginBottom: 14
    }
  };

  return (
    <div style={S.app}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.logo}>
          <div style={S.hexBadge}>⬡</div>
          <div>
            <div style={S.title}>MALTEGO RISK AGENT</div>
            <div style={S.subtitle}>CYBER HYGIENE INTELLIGENCE PLATFORM</div>
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
          {processed && (
            <button style={S.btn(false)} onClick={handleCSVDownload}>
              ↓ EXPORT CSV
            </button>
          )}
        </div>
      </div>

      <div style={S.main}>
        {/* Sidebar */}
        <div style={S.sidebar}>
          <div style={S.sidebarHeader}>NAVIGATION</div>
          {[
            { id: "ingest",    icon: "⬡", label: "DATA INGEST" },
            { id: "dashboard", icon: "◈", label: "DASHBOARD" },
            { id: "subjects",  icon: "◉", label: "SUBJECTS" },
            { id: "analysis",  icon: "⬟", label: "AI ANALYSIS" },
          ].map(({ id, icon, label }) => (
            <div key={id} style={S.sidebarItem(tab === id)} onClick={() => setTab(id)}>
              <span style={{ color: tab === id ? "#00d4ff" : "#2a4060", fontSize: 16 }}>{icon}</span>
              <span style={{ fontSize: 11, letterSpacing: 1.5, color: tab === id ? "#9dd" : "#3a5070" }}>{label}</span>
            </div>
          ))}

          {/* Subject list in sidebar */}
          {processed && records.length > 0 && (
            <>
              <div style={{ ...S.sidebarHeader, marginTop: 8 }}>SUBJECTS ({records.length})</div>
              <div style={{ overflowY: "auto", flex: 1 }}>
                {records.map(r => {
                  const score = computeRiskScore(r.flags);
                  const lv    = getRiskLevel(score);
                  return (
                    <div key={r.id}
                      style={{ ...S.sidebarItem(selected?.id === r.id), flexDirection: "column", alignItems: "flex-start", gap: 2 }}
                      onClick={() => { setSelected(r); setTab("subjects"); }}>
                      <div style={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
                        <span style={{ fontSize: 11, color: "#8ab" }}>{r.username}</span>
                        <span style={{ fontSize: 10, color: lv.color, fontWeight: 700 }}>{score}</span>
                      </div>
                      <span style={{ fontSize: 9, color: "#2a4060", letterSpacing: 1 }}>{r.platform.toUpperCase()}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Content */}
        <div style={S.content}>

          {/* ── DATA INGEST ── */}
          {tab === "ingest" && (
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: 2, marginBottom: 6, color: "#00d4ff" }}>
                DATA INGEST
              </div>
              <div style={{ fontSize: 11, color: "#3a5070", marginBottom: 20, letterSpacing: 1 }}>
                Paste Maltego-exported data below. Each line = one entity.
              </div>
              <div style={S.inputFormat}>
                FORMAT: <span style={{ color: "#00d4ff" }}>username | platform | url | flag1,flag2,...</span><br/>
                AVAILABLE FLAGS: {Object.keys(RISK_FACTORS).join(", ")}
              </div>
              <textarea
                style={S.textarea}
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Paste Maltego data here..."
                rows={10}
              />
              <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
                <button style={S.btn(true)} onClick={handleProcess}>
                  ⬡ PROCESS &amp; ANALYZE
                </button>
                <button style={S.btn(false)} onClick={() => setInput(SAMPLE_INPUT)}>
                  LOAD SAMPLE DATA
                </button>
              </div>
            </div>
          )}

          {/* ── DASHBOARD ── */}
          {tab === "dashboard" && (
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: 2, marginBottom: 20, color: "#00d4ff" }}>
                RISK DASHBOARD
              </div>
              {!processed ? (
                <div style={{ ...S.card, textAlign: "center", padding: 48, color: "#2a4060" }}>
                  <div style={{ fontSize: 40, marginBottom: 12 }}>⬡</div>
                  <div style={{ letterSpacing: 2 }}>NO DATA — GO TO DATA INGEST TO BEGIN</div>
                </div>
              ) : (
                <>
                  <div style={S.statGrid}>
                    <div style={S.stat}>
                      <div style={{ ...S.statVal, color: "#00d4ff" }}>{records.length}</div>
                      <div style={S.statLabel}>SUBJECTS ANALYZED</div>
                    </div>
                    <div style={S.stat}>
                      <div style={{ ...S.statVal, color: getRiskLevel(avgScore).color }}>{avgScore}</div>
                      <div style={S.statLabel}>AVG RISK SCORE</div>
                    </div>
                    <div style={S.stat}>
                      <div style={{ ...S.statVal, color: "#ff2d55" }}>{criticalCount}</div>
                      <div style={S.statLabel}>CRITICAL SUBJECTS</div>
                    </div>
                  </div>

                  {/* Risk distribution */}
                  <div style={S.card}>
                    <div style={{ fontSize: 11, color: "#3a6080", letterSpacing: 2, marginBottom: 14 }}>
                      RISK SCORE DISTRIBUTION
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {records.map(r => {
                        const score = computeRiskScore(r.flags);
                        const lv = getRiskLevel(score);
                        return (
                          <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 12 }}
                            onClick={() => { setSelected(r); setTab("subjects"); }}
                            onMouseEnter={e => e.currentTarget.style.cursor = "pointer"}>
                            <div style={{ width: 110, fontSize: 11, color: "#6a9" }}>{r.username}</div>
                            <div style={{ flex: 1, background: "#0a0d16", borderRadius: 3, height: 16, overflow: "hidden" }}>
                              <div style={{
                                width: `${score}%`, height: "100%", borderRadius: 3,
                                background: `linear-gradient(90deg, ${lv.color}88, ${lv.color})`,
                                transition: "width 1s ease"
                              }}/>
                            </div>
                            <div style={{ width: 50, textAlign: "right", fontSize: 12, color: lv.color, fontWeight: 700 }}>{score}</div>
                            <div style={{ width: 70 }}>
                              <span style={S.badge(lv.color, lv.bg)}>{lv.label}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Most common flags */}
                  <div style={S.card}>
                    <div style={{ fontSize: 11, color: "#3a6080", letterSpacing: 2, marginBottom: 14 }}>
                      TOP RISK INDICATORS
                    </div>
                    {Object.entries(RISK_FACTORS)
                      .map(([key, meta]) => ({
                        key, meta,
                        count: records.filter(r => r.flags[key]).length
                      }))
                      .filter(x => x.count > 0)
                      .sort((a, b) => b.count - a.count)
                      .map(({ key, meta, count }) => (
                        <div key={key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                          <div style={{ width: 180, fontSize: 11, color: "#7a9" }}>{meta.label}</div>
                          <div style={{ flex: 1, background: "#0a0d16", borderRadius: 3, height: 10, overflow: "hidden" }}>
                            <div style={{
                              width: `${(count / records.length) * 100}%`, height: "100%",
                              background: "linear-gradient(90deg, #ff2d5566, #ff2d55)",
                              borderRadius: 3, transition: "width 1s"
                            }}/>
                          </div>
                          <div style={{ width: 30, textAlign: "right", fontSize: 11, color: "#ff6b8a" }}>{count}</div>
                          <div style={{ width: 60, fontSize: 9, color: "#2a4060", letterSpacing: 1 }}>{meta.category}</div>
                        </div>
                      ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── SUBJECTS ── */}
          {tab === "subjects" && (
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: 2, marginBottom: 20, color: "#00d4ff" }}>
                SUBJECT DETAIL
              </div>
              {!processed || !selected ? (
                <div style={{ ...S.card, textAlign: "center", padding: 48, color: "#2a4060" }}>
                  <div style={{ letterSpacing: 2 }}>SELECT A SUBJECT FROM THE SIDEBAR</div>
                </div>
              ) : (() => {
                const score = computeRiskScore(selected.flags);
                const lv    = getRiskLevel(score);
                return (
                  <>
                    <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                      {/* Score ring */}
                      <div style={{ ...S.card, display: "flex", alignItems: "center", gap: 20, flex: 1 }}>
                        <ScoreRing score={score}/>
                        <div>
                          <div style={{ fontSize: 18, fontWeight: 700, color: "#9dd" }}>{selected.username}</div>
                          <div style={{ fontSize: 11, color: "#3a6080", marginTop: 4, letterSpacing: 1 }}>
                            {selected.platform} · <a href={selected.url} style={{ color: "#2a5070" }} target="_blank" rel="noreferrer">{selected.url || "—"}</a>
                          </div>
                          <div style={{ marginTop: 10 }}>
                            <span style={S.badge(lv.color, lv.bg)}>{lv.label} RISK</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Flags editor */}
                    <div style={S.card}>
                      <div style={{ fontSize: 11, color: "#3a6080", letterSpacing: 2, marginBottom: 10 }}>
                        RISK INDICATORS (click to toggle)
                      </div>
                      <div style={S.flagRow}>
                        {Object.entries(RISK_FACTORS).map(([key, meta]) => (
                          <div key={key}
                            style={S.flag(selected.flags[key])}
                            onClick={() => {
                              const updated = {
                                ...selected,
                                flags: { ...selected.flags, [key]: !selected.flags[key] }
                              };
                              setSelected(updated);
                              setRecords(rs => rs.map(r => r.id === updated.id ? updated : r));
                              // clear stale AI analysis
                              setAnalysis(a => { const n = {...a}; delete n[selected.id]; return n; });
                            }}>
                            {selected.flags[key] ? "✕ " : ""}{meta.label}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* All subjects table */}
                    <div style={S.card}>
                      <div style={{ fontSize: 11, color: "#3a6080", letterSpacing: 2, marginBottom: 10 }}>ALL SUBJECTS</div>
                      <table style={S.table}>
                        <thead>
                          <tr>
                            {["USERNAME","PLATFORM","SCORE","LEVEL","FLAGS"].map(h =>
                              <th key={h} style={S.th}>{h}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {records.map(r => {
                            const s = computeRiskScore(r.flags);
                            const l = getRiskLevel(s);
                            const fc = Object.values(r.flags).filter(Boolean).length;
                            return (
                              <tr key={r.id} style={{ cursor: "pointer", background: selected.id === r.id ? "rgba(0,212,255,0.03)" : "" }}
                                onClick={() => setSelected(r)}>
                                <td style={{ ...S.td, color: "#9dd" }}>{r.username}</td>
                                <td style={{ ...S.td, color: "#4a7090" }}>{r.platform}</td>
                                <td style={{ ...S.td, color: l.color, fontWeight: 700 }}>{s}</td>
                                <td style={S.td}><span style={S.badge(l.color, l.bg)}>{l.label}</span></td>
                                <td style={{ ...S.td, color: "#4a7090" }}>{fc} active</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                );
              })()}
            </div>
          )}

          {/* ── AI ANALYSIS ── */}
          {tab === "analysis" && (
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: 2, marginBottom: 6, color: "#00d4ff" }}>
                AI RISK ANALYSIS
              </div>
              <div style={{ fontSize: 11, color: "#3a5070", marginBottom: 20, letterSpacing: 1 }}>
                Claude generates a detailed threat assessment for each subject.
              </div>
              {!processed ? (
                <div style={{ ...S.card, textAlign: "center", padding: 48, color: "#2a4060" }}>
                  <div style={{ letterSpacing: 2 }}>PROCESS DATA FIRST</div>
                </div>
              ) : (
                records.map(r => {
                  const score = computeRiskScore(r.flags);
                  const lv    = getRiskLevel(score);
                  const ai    = analysis[r.id];
                  return (
                    <div key={r.id} style={S.card}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <div>
                          <span style={{ color: "#9dd", fontWeight: 700 }}>{r.username}</span>
                          <span style={{ color: "#2a4060", marginLeft: 10, fontSize: 11 }}>{r.platform}</span>
                          <span style={{ marginLeft: 12 }}>
                            <span style={S.badge(lv.color, lv.bg)}>{lv.label} · {score}</span>
                          </span>
                        </div>
                        {!ai && (
                          <button style={S.btn(true)}
                            onClick={() => handleAnalyze(r)}
                            disabled={loadingAI === r.id}>
                            {loadingAI === r.id ? "ANALYZING..." : "⬡ RUN AI ANALYSIS"}
                          </button>
                        )}
                      </div>

                      {ai && (
                        <div style={S.analysisBox}>
                          <div style={{ fontSize: 11, color: "#5a9", marginBottom: 10, lineHeight: 1.7 }}>
                            {ai.summary}
                          </div>
                          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                            <div style={{ flex: 1, minWidth: 200 }}>
                              <div style={{ fontSize: 9, color: "#3a6080", letterSpacing: 2, marginBottom: 6 }}>TOP RISKS</div>
                              {(ai.top_risks || []).map((t, i) =>
                                <div key={i} style={S.recItem}>
                                  <span style={{ color: "#ff2d55" }}>▸</span> {t}
                                </div>)}
                            </div>
                            <div style={{ flex: 1, minWidth: 200 }}>
                              <div style={{ fontSize: 9, color: "#3a6080", letterSpacing: 2, marginBottom: 6 }}>RECOMMENDATIONS</div>
                              {(ai.recommendations || []).map((rec, i) =>
                                <div key={i} style={S.recItem}>
                                  <span style={{ color: "#30d158" }}>▸</span> {rec}
                                </div>)}
                            </div>
                            <div style={{ minWidth: 150 }}>
                              <div style={{ fontSize: 9, color: "#3a6080", letterSpacing: 2, marginBottom: 6 }}>INTEL</div>
                              <div style={{ fontSize: 11, color: "#7a9" }}>
                                Actor Interest: <span style={{ color: "#ffd60a" }}>{ai.threat_actors}</span>
                              </div>
                              <div style={{ fontSize: 11, color: "#7a9", marginTop: 6 }}>
                                Exposure: <span style={{ color: "#00d4ff" }}>{ai.exposure_type}</span>
                              </div>
                            </div>
                          </div>
                          <div style={{ marginTop: 12 }}>
                            <button style={{ ...S.btn(false), fontSize: 10 }}
                              onClick={() => handleAnalyze(r)}>
                              ↺ RE-ANALYZE
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
