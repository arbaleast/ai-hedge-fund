"""GET /fund/{code} — Single fund detail page (inline HTML)

Shares the same CSS variable system and Chart.js dependency as ui.py.
Fetches all data from the /api/detail/{code}/* family of routes.

Sections:
  - Fund header: name + code + type tag + risk rating stars
  - My holdings card: buy price / amount / date / current value / gain-loss
  - Returns: 6 window tabs with percentage display
  - Risk: MDD / Volatility / Sharpe / Peer rank cards
  - NAV chart: unit + accumulated NAV overlay
  - Drawdown chart: area fill
  - Peer comparison table
"""

import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
router = APIRouter()

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title id="page-title">基金详情</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ===== CSS Variables ===== */
:root {
  --bg: #f5f7fa;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  --primary-border: #bfdbfe;
  --green: #22c55e;
  --green-bg: #f0fdf4;
  --green-text: #16a34a;
  --red: #ef4444;
  --red-bg: #fef2f2;
  --red-text: #dc2626;
  --orange: #f59e0b;
  --orange-bg: #fffbeb;
  --orange-text: #d97706;
  --gray: #94a3b8;
  --gray-bg: #f8fafc;
  --surface-hover: #f1f5f9;
  --btn-text: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.12);
  --overlay: rgba(0,0,0,0.4);
  --primary-glow: rgba(37,99,235,0.1);
  --red-glow: rgba(239,68,68,0.1);
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.2s ease;
}
:root[data-theme="dark"] {
  --bg: #0f172a;
  --surface: #1e293b;
  --border: #334155;
  --text: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --primary: #3b82f6;
  --primary-hover: #60a5fa;
  --primary-light: #1e3a5f;
  --primary-border: #1e40af;
  --green: #22c55e;
  --green-bg: #052e16;
  --green-text: #4ade80;
  --red: #ef4444;
  --red-bg: #450a0a;
  --red-text: #f87171;
  --orange: #f59e0b;
  --orange-bg: #451a03;
  --orange-text: #fb923c;
  --gray: #64748b;
  --gray-bg: #1e293b;
  --surface-hover: #334155;
  --btn-text: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.4);
  --overlay: rgba(0,0,0,0.6);
  --primary-glow: rgba(59,130,246,0.15);
  --red-glow: rgba(239,68,68,0.15);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
}

/* ===== Layout ===== */
.app-container { max-width: 1100px; margin: 0 auto; padding: 24px; }

/* ===== Toolbar ===== */
.toolbar {
  display: flex; align-items: center; gap: 12px;
  padding-bottom: 20px; border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}
.toolbar-left { display: flex; align-items: center; gap: 12px; flex: 1; }
.back-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--surface);
  color: var(--text-secondary); font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all var(--transition); text-decoration: none;
}
.back-btn:hover { border-color: var(--primary); color: var(--primary); }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.theme-btn {
  width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); cursor: pointer; font-size: 16px;
  transition: all var(--transition);
}
.theme-btn:hover { border-color: var(--primary); }

/* ===== Nav Bar ===== */
.nav-bar {
  display: flex; align-items: center; gap: 4px;
  margin-bottom: 20px; padding: 6px 0;
}
.nav-link {
  padding: 6px 14px; border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 500; text-decoration: none;
  color: var(--text-secondary); transition: all var(--transition);
}
.nav-link:hover { color: var(--text); background: var(--surface-hover); }
.nav-link.active { color: var(--primary); background: var(--primary-light); font-weight: 600; cursor: default; }

/* ===== Loading Overlay ===== */
#loading-overlay {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 20px; color: var(--text-muted); gap: 12px;
}
.loading-spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

/* ===== Fund Header Card ===== */
.fund-header {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px; margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.fund-header-top { display: flex; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.fund-name { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
.fund-code-badge {
  display: inline-block; padding: 2px 10px; border-radius: 6px;
  background: var(--gray-bg); color: var(--text-secondary);
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
}
.fund-tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.fund-tag {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-size: 12px; font-weight: 500;
}
.fund-tag.type { background: var(--primary-light); color: var(--primary); }
.fund-tag.stars { background: var(--orange-bg); color: var(--orange-text); }
.fund-meta {
  display: flex; flex-wrap: wrap; gap: 24px; margin-top: 14px;
  padding-top: 14px; border-top: 1px solid var(--border);
  font-size: 13px; color: var(--text-secondary);
}
.fund-meta-item { display: flex; align-items: center; gap: 6px; }
.fund-meta-item strong { color: var(--text); font-weight: 600; }

/* ===== Cards ===== */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px; margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.card-title {
  font-size: 14px; font-weight: 600; margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between;
  color: var(--text);
}

/* ===== Holdings Table ===== */
.holdings-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}
.holding-item { text-align: center; }
.holding-label {
  font-size: 11px; color: var(--text-secondary); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
}
.holding-value {
  font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

/* ===== Returns Section ===== */
.returns-display {
  text-align: center; padding: 16px 0;
}
.returns-pct {
  font-size: 42px; font-weight: 700; font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.returns-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.ret-pos { color: var(--green-text); }
.ret-neg { color: var(--red-text); }
.ret-nil { color: var(--text-muted); }

/* ===== Time Window ===== */
.window-group {
  display: flex; gap: 4px; margin-bottom: 16px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 6px;
  box-shadow: var(--shadow); flex-wrap: wrap;
}
.window-btn {
  padding: 7px 16px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 13px; font-weight: 500;
  border-radius: 6px; cursor: pointer; transition: all var(--transition);
  font-family: inherit;
}
.window-btn:hover { color: var(--text); background: var(--surface-hover); }
.window-btn.active { background: var(--primary); color: var(--btn-text); }
.window-btn.active:hover { background: var(--primary-hover); }

/* ===== Risk Metrics Grid ===== */
.metrics-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;
}
.metric-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow);
  text-align: center;
}
.metric-card .metric-label {
  font-size: 11px; color: var(--text-secondary); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
}
.metric-card .metric-value {
  font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.2;
}
.metric-card .metric-sub {
  font-size: 11px; color: var(--text-muted); margin-top: 4px;
}

/* ===== Charts ===== */
.chart-section { margin-bottom: 16px; }
.chart-wrap {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow);
}
.chart-wrap canvas { max-height: 320px; max-width: 100%; }
.chart-title {
  font-size: 14px; font-weight: 600; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.chart-loading, .chart-error {
  display: none; text-align: center; padding: 40px 20px;
  color: var(--text-muted); font-size: 13px;
}
.chart-loading.show, .chart-error.show { display: block; }
.chart-error { color: var(--text-secondary); }
.no-data {
  text-align: center; padding: 40px 20px; color: var(--text-muted); font-size: 14px;
}

/* ===== Peer Comparison Table ===== */
.table-wrap { overflow-x: auto; }
.peer-table {
  width: 100%; border-collapse: collapse; font-size: 13px; min-width: 600px;
}
.peer-table thead th {
  text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
  background: var(--gray-bg); border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.peer-table tbody td {
  padding: 10px 14px; border-bottom: 1px solid var(--border); vertical-align: middle;
}
.peer-table tbody tr:last-child td { border-bottom: none; }
.peer-table tbody tr:hover { background: var(--surface-hover); }
.peer-table tbody tr { transition: background var(--transition); }
.peer-code {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-weight: 600; font-size: 12px;
}
.peer-name { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-num {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap;
}

/* ===== Color helpers ===== */
.text-pos { color: var(--green-text); }
.text-neg { color: var(--red-text); }
.text-muted { color: var(--text-muted); }
.ml-auto { margin-left: auto; }

/* ===== Section divider ===== */
.section-title {
  font-size: 16px; font-weight: 700; margin-bottom: 14px; margin-top: 8px;
  display: flex; align-items: center; gap: 8px;
}
.section-title::before {
  content: ''; display: inline-block; width: 3px; height: 18px;
  background: var(--primary); border-radius: 2px; flex-shrink: 0;
}

/* ===== Animations ===== */
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.fade-in { animation: fadeIn 0.25s ease; }

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .app-container { padding: 16px; }
  .fund-header-top { flex-direction: column; gap: 8px; }
  .fund-name { font-size: 18px; }
  .fund-meta { gap: 12px; flex-direction: column; }
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .holdings-grid { grid-template-columns: repeat(2, 1fr); }
  .returns-pct { font-size: 32px; }
}
@media (max-width: 480px) {
  .metrics-grid { grid-template-columns: 1fr 1fr; }
  .holdings-grid { grid-template-columns: 1fr 1fr; }
}
</style>
<script>
/* Theme FOUC prevention */
(function(){var t=localStorage.getItem('theme')||'dark';document.documentElement.setAttribute('data-theme',t);})();
</script>
</head>
<body>
<div class="app-container" id="app" style="display:none;">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-left">
      <a href="/" class="back-btn">&#x2190; 返回</a>
    </div>
    <div class="toolbar-right">
      <button class="theme-btn" onclick="toggleTheme()" aria-label="切换主题" title="切换主题">
        <span id="theme-icon">&#x2600;&#xFE0F;</span>
      </button>
    </div>
  </div>

  <!-- Nav Bar -->
  <div class="nav-bar">
    <a href="/" class="nav-link">首页</a>
    <a href="/health" class="nav-link">组合诊断</a>
  </div>

  <!-- Fund Header -->
  <div class="fund-header fade-in" id="fund-header" style="display:none;">
    <div class="fund-header-top">
      <h1 class="fund-name" id="fund-name">—</h1>
      <span class="fund-code-badge" id="fund-code">—</span>
    </div>
    <div class="fund-tags" id="fund-tags"></div>
    <div class="fund-meta" id="fund-meta">
      <div class="fund-meta-item">经理: <strong id="fund-manager">—</strong></div>
      <div class="fund-meta-item">规模: <strong id="fund-scale">—</strong></div>
      <div class="fund-meta-item">成立日: <strong id="fund-inception">—</strong></div>
    </div>
  </div>

  <!-- My Holdings -->
  <div class="card fade-in" id="holdings-card" style="display:none;">
    <div class="card-title">&#x1F4B0; 我的持仓</div>
    <div class="holdings-grid">
      <div class="holding-item">
        <div class="holding-label">买入价</div>
        <div class="holding-value" id="h-buy-price">—</div>
      </div>
      <div class="holding-item">
        <div class="holding-label">持有金额</div>
        <div class="holding-value" id="h-buy-amount">—</div>
      </div>
      <div class="holding-item">
        <div class="holding-label">买入日期</div>
        <div class="holding-value" id="h-buy-date" style="font-size:16px;">—</div>
      </div>
      <div class="holding-item">
        <div class="holding-label">当前市值</div>
        <div class="holding-value" id="h-current-value">—</div>
      </div>
      <div class="holding-item">
        <div class="holding-label">收益</div>
        <div class="holding-value" id="h-gain-loss">—</div>
      </div>
    </div>
  </div>

  <!-- No Holdings message -->
  <div class="card fade-in" id="no-holdings-card" style="display:none;">
    <div class="card-title">&#x1F4B0; 我的持仓</div>
    <div class="no-data">尚未添加此基金到自选，<a href="/api/favorites" style="color:var(--primary);">点此添加</a></div>
  </div>

  <!-- Time Window -->
  <div class="window-group" id="window-group">
    <button class="window-btn" data-window="1" data-key="1m">1M</button>
    <button class="window-btn" data-window="3" data-key="3m">3M</button>
    <button class="window-btn" data-window="6" data-key="6m">6M</button>
    <button class="window-btn active" data-window="12" data-key="1y">1Y</button>
    <button class="window-btn" data-window="36" data-key="3y">3Y</button>
    <button class="window-btn" data-window="12" data-key="ytd">YTD</button>
  </div>

  <!-- Returns -->
  <div class="card fade-in" id="returns-card">
    <div class="card-title">区间回报</div>
    <div class="returns-display">
      <div class="returns-pct ret-nil" id="returns-pct">—</div>
      <div class="returns-label" id="returns-label">1Y 回报</div>
    </div>
  </div>

  <!-- Risk Metrics -->
  <div class="section-title">风险指标</div>
  <div class="metrics-grid" id="risk-section">
    <div class="metric-card">
      <div class="metric-label">最大回撤</div>
      <div class="metric-value" id="risk-mdd">—</div>
      <div class="metric-sub" id="risk-mdd-sub"></div>
    </div>
    <div class="metric-card">
      <div class="metric-label">波动率</div>
      <div class="metric-value" id="risk-vol">—</div>
      <div class="metric-sub" id="risk-vol-sub"></div>
    </div>
    <div class="metric-card">
      <div class="metric-label">夏普比率</div>
      <div class="metric-value" id="risk-sharpe">—</div>
      <div class="metric-sub" id="risk-sharpe-sub"></div>
    </div>
    <div class="metric-card">
      <div class="metric-label">同类排名</div>
      <div class="metric-value" id="risk-rank">—</div>
      <div class="metric-sub" id="risk-rank-sub"></div>
    </div>
  </div>

  <!-- NAV Chart -->
  <div class="section-title">净值走势</div>
  <div class="chart-section">
    <div class="chart-wrap">
      <canvas id="navChart"></canvas>
    </div>
    <div class="chart-loading" id="nav-chart-loading">
      <span class="loading-spinner" style="width:20px;height:20px;border-width:2px;display:inline-block;margin-right:8px;vertical-align:middle;"></span>加载中...
    </div>
    <div class="chart-error" id="nav-chart-error">暂无净值数据</div>
  </div>

  <!-- Drawdown Chart -->
  <div class="section-title">回撤走势</div>
  <div class="chart-section">
    <div class="chart-wrap">
      <canvas id="drawdownChart"></canvas>
    </div>
    <div class="chart-loading" id="dd-chart-loading">
      <span class="loading-spinner" style="width:20px;height:20px;border-width:2px;display:inline-block;margin-right:8px;vertical-align:middle;"></span>加载中...
    </div>
    <div class="chart-error" id="dd-chart-error">暂无回撤数据</div>
  </div>

  <!-- Peer Comparison -->
  <div class="section-title">同类对比</div>
  <div class="card" id="peer-section">
    <div class="table-wrap">
      <table class="peer-table" id="peer-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th class="col-num">回报</th>
            <th class="col-num">最大回撤</th>
            <th class="col-num">波动率</th>
            <th class="col-num">风险评级</th>
          </tr>
        </thead>
        <tbody id="peer-body"></tbody>
      </table>
    </div>
    <div class="no-data" id="peer-empty" style="display:none;">无同类基金数据</div>
  </div>
</div>

<!-- Loading overlay (shown before initial data) -->
<div id="loading-overlay">
  <div class="loading-spinner"></div>
  <span>加载基金数据...</span>
</div>

<script>
/* ===== State ===== */
let currentCode = null;
let navChartInstance = null;
let ddChartInstance = null;
let cachedReturns = null;
let activeWindow = 12;
let activeKey = '1y';

/* ===== Utilities ===== */
function escapeHtml(str) {
  if (str == null) return '';
  var d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

function fmtNum(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtMoney(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return Number(n).toFixed(2);
}

function fmtPct(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  var v = n >= 0 ? '+' : '';
  return v + Number(n).toFixed(2) + '%';
}

function fmtCleanPct(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return Number(n).toFixed(2) + '%';
}

function isDarkTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

function getChartTextColor() {
  return isDarkTheme() ? '#94a3b8' : '#64748b';
}

function getChartGridColor() {
  return isDarkTheme() ? '#334155' : '#e2e8f0';
}

function isRetPos(v) {
  return v != null && v > 0;
}

function isRetNeg(v) {
  return v != null && v < 0;
}

/* ===== Theme ===== */
function toggleTheme() {
  var html = document.documentElement;
  var current = html.getAttribute('data-theme') || 'dark';
  var next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  document.getElementById('theme-icon').innerHTML = next === 'dark' ? '&#x2600;&#xFE0F;' : '&#x1F319;';
  // Rebuild charts with new colors
  rebuildCharts();
}

/* ===== API Fetching ===== */
async function fetchAPI(path) {
  var r = await fetch(path);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return await r.json();
}

/* ===== Load All Data ===== */
async function loadAll() {
  var code = currentCode;
  try {
    var [infoData, quoteData, returnsData, riskData, navData, ddData, peerData] = await Promise.all([
      fetchAPI('/api/detail/' + code + '/info'),
      fetchAPI('/api/detail/' + code + '/quote'),
      fetchAPI('/api/detail/' + code + '/returns?window=12'),
      fetchAPI('/api/detail/' + code + '/risk?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/nav_curve?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/drawdown?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/peer_compare?window=' + activeWindow),
    ]);

    // Cache returns for window switching
    cachedReturns = returnsData;

    renderHeader(infoData);
    renderQuote(quoteData, infoData);
    renderReturns(returnsData);
    renderRisk(riskData);
    renderNavChart(navData);
    renderDrawdownChart(ddData);
    renderPeerCompare(peerData, code);
  } catch (e) {
    console.error('Failed to load details:', e);
  }
}

/* ===== Load holdings from favorites API ===== */
async function loadHoldings() {
  try {
    var r = await fetch('/api/favorites');
    if (!r.ok) return;
    var all = await r.json();
    var match = null;
    for (var i = 0; i < all.length; i++) {
      if (all[i].code === currentCode) {
        match = all[i];
        break;
      }
    }
    if (match) {
      renderHoldings(match);
    } else {
      document.getElementById('no-holdings-card').style.display = 'block';
      document.getElementById('holdings-card').style.display = 'none';
    }
  } catch (e) {
    document.getElementById('no-holdings-card').style.display = 'block';
  }
}

/* ===== Render Sections ===== */
function renderHeader(data) {
  document.getElementById('fund-name').textContent = data.name || '—';
  document.getElementById('fund-code').textContent = currentCode;
  document.getElementById('fund-manager').textContent = data.manager || '—';

  var scaleEl = document.getElementById('fund-scale');
  if (data.scale != null) {
    scaleEl.textContent = fmtMoney(data.scale) + ' 亿元';
  } else {
    scaleEl.textContent = '—';
  }

  document.getElementById('fund-inception').textContent = data.inception_date || '—';

  // Tags
  var tags = document.getElementById('fund-tags');
  var html = '';
  if (data.type) {
    html += '<span class="fund-tag type">' + escapeHtml(data.type) + '</span>';
  }
  // Star rating from risk data displayed separately
  tags.innerHTML = html;

  // Page title
  document.getElementById('page-title').textContent = (data.name || currentCode) + ' — 基金详情';

  document.getElementById('fund-header').style.display = 'block';
}

function renderQuote(quoteData, infoData) {
  // Daily return in header
  var dr = quoteData.daily_return;
  if (dr != null) {
    var drHtml = '<span class="fund-meta-item">最新净值: <strong>' + fmtNum(quoteData.nav) + '</strong> (' +
      (dr >= 0
        ? '<span class="text-pos">+' + dr.toFixed(2) + '%</span>'
        : '<span class="text-neg">' + dr.toFixed(2) + '%</span>') +
      ') <span style="font-size:11px;color:var(--text-muted);">' + (quoteData.nav_date || '') + '</span></span>';
    var meta = document.getElementById('fund-meta');
    meta.insertAdjacentHTML('beforeend', drHtml);
  }
}

function renderHoldings(data) {
  document.getElementById('h-buy-price').textContent = fmtNum(data.buy_price);
  document.getElementById('h-buy-amount').textContent = '¥' + fmtMoney(data.buy_amount);
  document.getElementById('h-buy-date').textContent = data.buy_date || '—';
  document.getElementById('h-current-value').textContent = '¥' + fmtMoney(data.current_value);

  var gainEl = document.getElementById('h-gain-loss');
  var ret = data.return_pct;
  if (ret != null) {
    var retDisplay = (ret >= 0 ? '+' : '') + (ret * 100).toFixed(2) + '%';
    gainEl.textContent = retDisplay;
    gainEl.className = 'holding-value ' + (ret >= 0 ? 'text-pos' : 'text-neg');
  } else {
    gainEl.textContent = '—';
    gainEl.className = 'holding-value text-muted';
  }

  document.getElementById('holdings-card').style.display = 'block';
}

function renderReturns(data) {
  var windows = data.windows || {};
  // Update display for active key
  updateReturnDisplay(windows);
}

function updateReturnDisplay(windows) {
  var val = windows[activeKey];
  var pctEl = document.getElementById('returns-pct');
  var labelEl = document.getElementById('returns-label');
  labelEl.textContent = activeKey.toUpperCase() + ' 回报';

  if (val != null) {
    pctEl.textContent = fmtPct(val);
    pctEl.className = 'returns-pct ' + (val >= 0 ? 'ret-pos' : 'ret-neg');
  } else {
    pctEl.textContent = '—';
    pctEl.className = 'returns-pct ret-nil';
  }
}

function renderRisk(data) {
  // MDD
  var mddEl = document.getElementById('risk-mdd');
  var mddSub = document.getElementById('risk-mdd-sub');
  if (data.mdd != null) {
    mddEl.textContent = data.mdd.toFixed(2) + '%';
    mddEl.className = 'metric-value ' + (Math.abs(data.mdd) <= 10 ? 'text-pos' : Math.abs(data.mdd) <= 20 ? '' : 'text-neg');
    mddSub.textContent = data.mdd_days != null ? '持续 ' + data.mdd_days + ' 天' : '';
  } else {
    mddEl.textContent = '—';
    mddEl.className = 'metric-value text-muted';
  }

  // Volatility
  var volEl = document.getElementById('risk-vol');
  var volSub = document.getElementById('risk-vol-sub');
  if (data.volatility != null) {
    volEl.textContent = data.volatility.toFixed(2) + '%';
    volEl.className = 'metric-value ' + (data.volatility < 15 ? 'text-pos' : data.volatility < 25 ? '' : 'text-neg');
    volSub.textContent = '年化波动率';
  } else {
    volEl.textContent = '—';
    volEl.className = 'metric-value text-muted';
    volSub.textContent = '';
  }

  // Sharpe
  var sharpeEl = document.getElementById('risk-sharpe');
  var sharpeSub = document.getElementById('risk-sharpe-sub');
  if (data.sharpe != null) {
    sharpeEl.textContent = data.sharpe.toFixed(2);
    sharpeEl.className = 'metric-value ' + (data.sharpe >= 1 ? 'text-pos' : data.sharpe >= 0 ? '' : 'text-neg');
    sharpeSub.textContent = data.sharpe >= 1 ? '优秀' : data.sharpe >= 0 ? '一般' : '较差';
  } else {
    sharpeEl.textContent = '—';
    sharpeEl.className = 'metric-value text-muted';
    sharpeSub.textContent = '';
  }

  // Rating — show stars in header + peer rank
  var rankEl = document.getElementById('risk-rank');
  var rankSub = document.getElementById('risk-rank-sub');
  if (data.rating && data.rating !== '—') {
    rankEl.textContent = data.rating;
    rankEl.className = 'metric-value';
    var starCount = data.rating.length;
    rankSub.textContent = starCount >= 4 ? '风险较低' : starCount >= 3 ? '风险适中' : starCount >= 2 ? '风险较高' : '风险高';
    // Also show stars in fund header
    var tags = document.getElementById('fund-tags');
    var starTag = document.createElement('span');
    starTag.className = 'fund-tag stars';
    starTag.textContent = data.rating;
    tags.appendChild(starTag);
  } else {
    rankEl.textContent = '—';
    rankEl.className = 'metric-value text-muted';
    rankSub.textContent = '';
  }
}

/* ===== NAV Chart ===== */
function renderNavChart(data) {
  var dates = data.dates || [];
  var navs = data.navs || [];
  var accNavs = data.accumulated_navs || [];

  var loading = document.getElementById('nav-chart-loading');
  var error = document.getElementById('nav-chart-error');
  var canvas = document.getElementById('navChart');

  if (dates.length < 2) {
    loading.classList.remove('show');
    error.classList.add('show');
    return;
  }

  loading.classList.remove('show');
  error.classList.remove('show');

  // Show every Nth label
  var maxLabels = 20;
  var step = Math.max(1, Math.floor(dates.length / maxLabels));

  var textColor = getChartTextColor();
  var gridColor = getChartGridColor();

  if (navChartInstance) {
    navChartInstance.destroy();
    navChartInstance = null;
  }

  navChartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [
        {
          label: '单位净值',
          data: navs,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
          tension: 0.1,
          yAxisID: 'y',
        },
        {
          label: '累计净值',
          data: accNavs,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
          tension: 0.1,
          yAxisID: 'y',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: textColor, boxWidth: 12, padding: 12, font: { size: 11 } },
        },
        tooltip: {
          backgroundColor: isDarkTheme() ? '#1e293b' : '#ffffff',
          titleColor: isDarkTheme() ? '#f1f5f9' : '#1e293b',
          bodyColor: isDarkTheme() ? '#94a3b8' : '#64748b',
          borderColor: isDarkTheme() ? '#334155' : '#e2e8f0',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(4);
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor, font: { size: 10 }, maxRotation: 45,
            callback: function(val, idx) { return idx % step === 0 ? this.getLabelForValue(val) : ''; },
          },
          grid: { color: gridColor },
        },
        y: {
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor },
        },
      },
    },
  });
}

/* ===== Drawdown Chart ===== */
function renderDrawdownChart(data) {
  var series = data.drawdown_series || [];
  var loading = document.getElementById('dd-chart-loading');
  var error = document.getElementById('dd-chart-error');
  var canvas = document.getElementById('drawdownChart');

  if (!series || series.length < 2) {
    loading.classList.remove('show');
    error.classList.add('show');
    return;
  }

  loading.classList.remove('show');
  error.classList.remove('show');

  var dates = series.map(function(s) { return s.date; });
  var values = series.map(function(s) { return s.drawdown_pct; });

  var maxLabels = 20;
  var step = Math.max(1, Math.floor(dates.length / maxLabels));
  var textColor = getChartTextColor();
  var gridColor = getChartGridColor();

  if (ddChartInstance) {
    ddChartInstance.destroy();
    ddChartInstance = null;
  }

  ddChartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [{
        label: '回撤',
        data: values,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.15)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: isDarkTheme() ? '#1e293b' : '#ffffff',
          titleColor: isDarkTheme() ? '#f1f5f9' : '#1e293b',
          bodyColor: isDarkTheme() ? '#94a3b8' : '#64748b',
          borderColor: isDarkTheme() ? '#334155' : '#e2e8f0',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(ctx) {
              return '回撤: ' + ctx.parsed.y.toFixed(2) + '%';
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor, font: { size: 10 }, maxRotation: 45,
            callback: function(val, idx) { return idx % step === 0 ? this.getLabelForValue(val) : ''; },
          },
          grid: { color: gridColor },
        },
        y: {
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor },
          reverse: true,
          title: {
            display: true,
            text: '回撤 (%)',
            color: textColor,
            font: { size: 11 },
          },
        },
      },
    },
  });
}

/* ===== Peer Comparison ===== */
function renderPeerCompare(data, excludeCode) {
  var peers = data.peer_metrics || [];
  var tbody = document.getElementById('peer-body');
  var empty = document.getElementById('peer-empty');

  if (!peers || peers.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }

  empty.style.display = 'none';

  var html = '';
  for (var i = 0; i < peers.length; i++) {
    var p = peers[i];
    if (p.code === excludeCode) continue;

    var retClass = 'col-num ' + (isRetPos(p.return_pct) ? 'text-pos' : isRetNeg(p.return_pct) ? 'text-neg' : 'text-muted');
    var retDisplay = p.return_pct != null ? fmtPct(p.return_pct) : '—';
    var mddDisplay = p.mdd != null ? p.mdd.toFixed(2) + '%' : '—';
    var volDisplay = p.volatility != null ? p.volatility.toFixed(2) + '%' : '—';

    html += '<tr>';
    html += '<td class="peer-code">' + escapeHtml(p.code || '') + '</td>';
    html += '<td class="peer-name" title="' + escapeHtml(p.name || '') + '">' + escapeHtml(p.name || '') + '</td>';
    html += '<td class="' + retClass + '">' + retDisplay + '</td>';
    html += '<td class="col-num">' + mddDisplay + '</td>';
    html += '<td class="col-num">' + volDisplay + '</td>';
    html += '<td class="col-num">' + escapeHtml(p.rating || '—') + '</td>';
    html += '</tr>';
  }

  tbody.innerHTML = html || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">无同类对比数据</td></tr>';
}

/* ===== Window Switching ===== */
function switchWindow(windowMonths, key) {
  activeWindow = windowMonths;
  activeKey = key;

  // Update buttons
  var btns = document.querySelectorAll('#window-group .window-btn');
  for (var i = 0; i < btns.length; i++) {
    btns[i].classList.remove('active');
    if (btns[i].dataset.key === key) {
      btns[i].classList.add('active');
    }
  }

  // Update returns display (from cache)
  if (cachedReturns && cachedReturns.windows) {
    updateReturnDisplay(cachedReturns.windows);
  }

  // Refetch time-dependent data
  reloadTimeWindowData();
}

async function reloadTimeWindowData() {
  var code = currentCode;
  try {
    var [riskData, navData, ddData, peerData] = await Promise.all([
      fetchAPI('/api/detail/' + code + '/risk?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/nav_curve?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/drawdown?window=' + activeWindow),
      fetchAPI('/api/detail/' + code + '/peer_compare?window=' + activeWindow),
    ]);

    renderRisk(riskData);
    renderNavChart(navData);
    renderDrawdownChart(ddData);
    renderPeerCompare(peerData, code);
  } catch (e) {
    console.error('Failed to reload window data:', e);
  }
}

/* ===== Rebuild charts after theme toggle ===== */
function rebuildCharts() {
  var code = currentCode;
  if (!code) return;

  // Refetch nav and drawdown data with current window
  fetchAPI('/api/detail/' + code + '/nav_curve?window=' + activeWindow)
    .then(function(d) { renderNavChart(d); })
    .catch(function() {});
  fetchAPI('/api/detail/' + code + '/drawdown?window=' + activeWindow)
    .then(function(d) { renderDrawdownChart(d); })
    .catch(function() {});
}

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', function() {
  // Sync theme icon
  var html = document.documentElement;
  var theme = html.getAttribute('data-theme') || 'dark';
  var icon = document.getElementById('theme-icon');
  if (icon) icon.innerHTML = theme === 'dark' ? '&#x2600;&#xFE0F;' : '&#x1F319;';

  // Extract code from URL path: /fund/{code}
  var pathParts = window.location.pathname.split('/');
  if (pathParts.length >= 3 && pathParts[1] === 'fund') {
    currentCode = pathParts[2];
  }

  if (!currentCode) {
    document.getElementById('loading-overlay').innerHTML = '<p style="color:var(--red-text);">无效的基金代码</p>';
    return;
  }

  // Load all data
  Promise.all([
    loadAll(),
    loadHoldings(),
  ]).then(function() {
    document.getElementById('loading-overlay').style.display = 'none';
    document.getElementById('app').style.display = 'block';
  }).catch(function(e) {
    document.getElementById('loading-overlay').innerHTML = '<p style="color:var(--red-text);">加载失败: ' + escapeHtml(e.message) + '</p>';
  });
});

/* ===== Window Group Click Handler ===== */
document.getElementById('window-group').addEventListener('click', function(e) {
  var btn = e.target.closest('.window-btn');
  if (!btn) return;
  if (btn.classList.contains('active')) return;
  var w = parseInt(btn.dataset.window, 10);
  var k = btn.dataset.key;
  switchWindow(w, k);
});
</script>
</body>
</html>"""


@router.get("/fund/{code}", response_class=HTMLResponse)
async def fund_detail(code: str) -> str:
    return HTML
