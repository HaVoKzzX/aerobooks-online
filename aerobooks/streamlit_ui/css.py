"""AeroBooks Streamlit chrome — navy/gold paper theme, mobile-first."""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Baskerville:wght@700&display=swap');

:root {
  --ab-navy: #1B365D;
  --ab-navy-2: #152A4A;
  --ab-navy-3: #10233F;
  --ab-gold: #C4A35A;
  --ab-gold-2: #E8C56A;
  --ab-paper: #F4F1EA;
  --ab-card: #FFFCF7;
  --ab-ink: #1C1917;
  --ab-muted: #6B6459;
  --ab-line: #E6E0D4;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  background: var(--ab-paper) !important;
  color: var(--ab-ink) !important;
  font-family: 'DM Sans', 'Segoe UI', sans-serif !important;
}

[data-testid="stHeader"] {
  background: var(--ab-navy) !important;
  color: #fff !important;
}
[data-testid="stHeader"] * { color: #fff !important; fill: #fff !important; }
[data-testid="stToolbar"] { right: 0.4rem; }
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stBottom"], footer, #MainMenu, .stDeployButton,
[data-testid="stAppDeployButton"] { display: none !important; }

.block-container {
  padding-top: 1.1rem !important;
  padding-bottom: 2.5rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
  max-width: 1180px !important;
}

[data-testid="stSidebar"] {
  background: var(--ab-navy-3) !important;
  color: #FFFCF7 !important;
}
[data-testid="stSidebar"] * { color: #FFFCF7 !important; }
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
  color: #FFFCF7 !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] span {
  font-weight: 600;
  letter-spacing: 0.01em;
}
[data-testid="stSidebarNav"] a {
  border-radius: 10px !important;
  padding: 0.45rem 0.7rem !important;
}
[data-testid="stSidebarNav"] a:hover {
  background: rgba(232, 197, 106, 0.16) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNav"] li:has(a[aria-current="page"]) a {
  background: rgba(232, 197, 106, 0.22) !important;
}
[data-testid="stSidebar"] button {
  min-height: 44px;
}

.ab-brand {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 22px;
  color: #FFFcf7 !important;
  letter-spacing: 0.02em;
  line-height: 1.1;
  margin: 0;
}
.ab-brand-sub {
  color: #E8C56A !important;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 4px 0 10px 0;
}
.ab-h1 {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 28px;
  color: var(--ab-navy);
  margin: 0 0 2px 0;
  line-height: 1.2;
}
.ab-sub { color: var(--ab-muted); font-size: 14px; margin: 0 0 12px 0; }
.ab-kicker {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ab-muted);
}

.ab-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin: 0 0 14px 0;
}
.ab-stat {
  background: var(--ab-card);
  border: 1px solid var(--ab-line);
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(27,54,93,0.04);
}
.ab-stat .ab-stat-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ab-muted);
}
.ab-stat .ab-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--ab-navy);
  line-height: 1.2;
  margin-top: 2px;
}
.ab-stat.warn .ab-stat-value { color: #9B2C2C; }
.ab-stat.good .ab-stat-value { color: #1B7A4E; }
.ab-stat.gold .ab-stat-value { color: #8A6A2A; }
.ab-stat .ab-stat-hint { font-size: 12px; color: var(--ab-muted); margin-top: 4px; }

.ab-card {
  background: var(--ab-card);
  border: 1px solid var(--ab-line);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 2px rgba(27,54,93,0.04);
}
.ab-card-title { font-weight: 700; color: var(--ab-navy); margin: 0 0 8px 0; }
.ab-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--ab-line);
  flex-wrap: wrap;
}
.ab-row:last-child { border-bottom: 0; }

.ab-chip {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 3px 9px;
  line-height: 1.4;
}
.ab-status-paid, .ab-status-active { background: #E4F5EA; color: #1B7A4E; }
.ab-status-unpaid { background: #FFF3D6; color: #8A6A2A; }
.ab-status-partial { background: #E8F1FA; color: #1B365D; }
.ab-status-overdue { background: #FDECEC; color: #9B2C2C; }
.ab-status-draft, .ab-status-void, .ab-status-inactive { background: #EEECE7; color: #5C564C; }
.ab-status-void { text-decoration: line-through; }
.ab-status-soloed { background: #E8F1FA; color: #1B365D; }
.ab-status-checkride_ready { background: #FFF3D6; color: #8A6A2A; }
.ab-status-graduated { background: #EDE7F6; color: #5E35B1; }
.ab-status-disabled { background: #FDECEC; color: #9B2C2C; }
.ab-status-pending { background: #FFF3D6; color: #8A6A2A; }
.ab-status-approved { background: #E4F5EA; color: #1B7A4E; }
.ab-status-rejected { background: #EEECE7; color: #5C564C; }

.ab-alert {
  background: #FDECEC;
  border-left: 4px solid #9B2C2C;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.ab-alert-gold {
  background: #FFF6E0;
  border-left: 4px solid #C4A35A;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.ab-lock-note {
  background: #FFF6E0;
  border-left: 4px solid #C4A35A;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: #5C564C;
  margin-bottom: 10px;
}

.ab-auth-hero {
  min-height: 28vh;
  margin: -1.1rem -1.5rem 1.2rem -1.5rem;
  padding: 36px 20px 28px;
  background:
    radial-gradient(900px 400px at 10% -10%, rgba(196,163,90,0.22), transparent 50%),
    linear-gradient(180deg, #10233F 0%, #1B365D 100%);
  color: #fff;
  text-align: center;
}
.ab-auth-hero .ab-brand { font-size: 28px; }
.ab-auth-hero .ab-brand-sub { margin-bottom: 0; }

div[data-testid="stMetric"] {
  background: var(--ab-card);
  border: 1px solid var(--ab-line);
  border-radius: 14px;
  padding: 10px 12px;
}

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  min-height: 42px;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: var(--ab-navy) !important;
  color: #fff !important;
  border: 0 !important;
}

[data-testid="stDataFrame"], [data-testid="stTable"] {
  overflow-x: auto;
}

@media (max-width: 768px) {
  html, body, .stApp {
    padding-left: env(safe-area-inset-left);
    padding-right: env(safe-area-inset-right);
  }
  .block-container {
    padding-top: 0.7rem !important;
    padding-bottom: calc(1.4rem + env(safe-area-inset-bottom)) !important;
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    max-width: 100% !important;
  }
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.45rem !important;
  }
  [data-testid="stHorizontalBlock"] > div {
    min-width: min(100%, 100%) !important;
    flex: 1 1 100% !important;
  }
  [data-testid="stSidebar"] {
    min-width: min(320px, 92vw) !important;
  }
  [data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
    min-height: 44px;
    display: flex !important;
    align-items: center;
  }
  input, textarea, select, [data-baseweb="select"] input, .stNumberInput input,
  .stTextInput input, .stTextArea textarea, .stDateInput input {
    font-size: 16px !important;
  }
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    min-height: 44px !important;
    width: 100%;
  }
  .ab-h1 { font-size: 22px; }
  .ab-stat .ab-stat-value { font-size: 22px; }
  .ab-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .ab-auth-hero {
    margin-left: -0.85rem;
    margin-right: -0.85rem;
    padding-top: calc(22px + env(safe-area-inset-top));
  }
  [data-testid="stDialog"] div[role="dialog"] {
    width: 100vw !important;
    max-width: 100vw !important;
    max-height: 100dvh !important;
    border-radius: 12px 12px 0 0 !important;
  }
  [data-testid="stExpander"] { border-radius: 12px !important; }
}

@media (max-width: 420px) {
  .ab-stats { grid-template-columns: 1fr; }
}

@media (hover: none) {
  .stButton > button:hover { filter: none; }
}

* { -webkit-tap-highlight-color: transparent; }
"""
