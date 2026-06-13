"""GET /health — Portfolio health diagnosis page (inline HTML)

Shares the same CSS variable system, Chart.js CDN, and theme toggle as ui.py.
Fetches from the /api/health/* family of routes.

Sections:
  - Health score hero: animated SVG circular gauge + 4 dimension score cards
  - Type distribution: Chart.js doughnut chart
  - Holding duration: horizontal bar chart (per-fund months)
  - Concentration: vertical bar chart (top holdings by weight)
  - Peer comparison: table showing each fund's return vs portfolio average
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
<title>组合健康诊断</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ===== CSS Variables ===== */
:root {
  --bg: #f5f7fa; --surface: #ffffff; --border: #e2e8f0;
  --text: #1e293b; --text-secondary: #64748b; --text-muted: #94a3b8;
  --primary: #2563eb; --primary-hover: #1d4ed8; --primary-light: #eff6ff;
  --primary-border: #bfdbfe;
  --green: #22c55e; --green-bg: #f0fdf4; --green-text: #16a34a;
  --red: #ef4444; --red-bg: #fef2f2; --red-text: #dc2626;
  --orange: #f59e0b; --orange-bg: #fffbeb; --orange-text: #d97706;
  --gray: #94a3b8; --gray-bg: #f8fafc; --surface-hover: #f1f5f9;
  --btn-text: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.12);
  --radius: 12px; --radius-sm: 8px; --transition: 0.2s ease;
}
:root[data-theme="dark"] {
  --bg: #0f172a; --surface: #1e293b; --border: #334155;
  --text: #f1f5f9; --text-secondary: #94a3b8; --text-muted: #64748b;
  --primary: #3b82f6; --primary-hover: #60a5fa; --primary-light: #1e3a5f;
  --primary-border: #1e40af;
  --green: #22c55e; --green-bg: #052e16; --green-text: #4ade80;
  --red: #ef4444; --red-bg: #450a0a; --red-text: #f87171;
  --orange: #f59e0b; --orange-bg: #451a03; --orange-text: #fb923c;
  --gray: #64748b; --gray-bg: #1e293b; --surface-hover: #334155;
  --btn-text: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.4);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.5;
}
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

/* ===== Loading ===== */
#loading-overlay {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 20px; color: var(--text-muted); gap: 12px;
}
.loading-spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

/* ===== Health Score Hero ===== */
.health-hero {
  display: flex; align-items: center; gap: 32px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px 32px;
  margin-bottom: 20px; box-shadow: var(--shadow);
}
.health-gauge {
  flex-shrink: 0; width: 160px; height: 160px;
  position: relative;
}
.health-gauge svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.health-gauge .bg-circle { fill: none; stroke: var(--border); stroke-width: 10; }
.health-gauge .fg-circle {
  fill: none; stroke-width: 10; stroke-linecap: round;
  transition: stroke-dashoffset 1.2s ease, stroke 0.3s ease;
}
.health-score-text {
  position: absolute; inset: 0; display: flex;
  flex-direction: column; align-items: center; justify-content: center;
  transform: rotate(0deg);
}
.health-score-text .score-num {
  font-size: 44px; font-weight: 800; font-variant-numeric: tabular-nums;
  line-height: 1; letter-spacing: -1px;
}
.health-score-text .score-label {
  font-size: 11px; color: var(--text-muted); margin-top: 4px;
}
.health-info { flex: 1; min-width: 0; }
.health-info .health-title {
  font-size: 18px; font-weight: 700; margin-bottom: 4px;
}
.health-info .health-desc {
  font-size: 13px; color: var(--text-secondary); line-height: 1.6;
}

/* ===== Dimension Score Cards ===== */
.dim-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
}
.dim-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow);
}
.dim-card .dim-label {
  font-size: 11px; color: var(--text-secondary); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;
}
.dim-card .dim-weight {
  font-size: 10px; color: var(--text-muted); margin-left: 4px;
  font-weight: 400; text-transform: none; letter-spacing: 0;
}
.dim-card .dim-value {
  font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums;
  line-height: 1.2; margin-bottom: 8px;
}
.dim-card .dim-bar-bg {
  height: 4px; background: var(--border); border-radius: 2px; overflow: hidden;
}
.dim-card .dim-bar {
  height: 100%; border-radius: 2px; transition: width 0.8s ease;
}

/* ===== Chart Sections ===== */
.chart-section {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px; margin-bottom: 20px;
  box-shadow: var(--shadow);
}
.chart-section .section-title {
  font-size: 15px; font-weight: 600; margin-bottom: 14px; color: var(--text);
  display: flex; align-items: center; justify-content: space-between;
}
.chart-wrap { position: relative; }
.chart-wrap canvas { max-height: 300px; max-width: 100%; }
.chart-loading, .chart-error {
  display: none; text-align: center; padding: 40px 20px;
  color: var(--text-muted); font-size: 13px;
}
.chart-loading.show, .chart-error.show { display: block; }
.chart-error { color: var(--text-secondary); }
.chart-loading .spinner {
  display: inline-block; width: 20px; height: 20px;
  border: 2px solid var(--border); border-top-color: var(--primary);
  border-radius: 50%; animation: spin 0.6s linear infinite;
  vertical-align: middle; margin-right: 8px;
}

/* ===== Composition Grid ===== */
.composition-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;
}
.composition-grid .chart-section { margin-bottom: 0; }

/* ===== Peer Comparison Table ===== */
.table-wrap { overflow-x: auto; }
.peer-table {
  width: 100%; border-collapse: collapse; font-size: 13px; min-width: 500px;
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
.text-pos { color: var(--green-text); font-weight: 600; }
.text-neg { color: var(--red-text); font-weight: 600; }

/* ===== Empty State ===== */
.empty-state {
  text-align: center; padding: 60px 20px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
}
.empty-state .empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.6; }
.empty-state h3 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
.empty-state p { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }

/* ===== Animations ===== */
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.fade-in { animation: fadeIn 0.25s ease; }

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .app-container { padding: 16px; }
  .health-hero { flex-direction: column; text-align: center; gap: 16px; }
  .health-gauge { width: 130px; height: 130px; }
  .dim-grid { grid-template-columns: repeat(2, 1fr); }
  .composition-grid { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .dim-grid { grid-template-columns: 1fr 1fr; }
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
    <a href="/health" class="nav-link active">组合诊断</a>
  </div>

  <!-- Health Score Hero -->
  <div class="health-hero fade-in" id="health-hero" style="display:none;">
    <div class="health-gauge">
      <svg viewBox="0 0 160 160">
        <circle class="bg-circle" cx="80" cy="80" r="68"></circle>
        <circle class="fg-circle" id="health-fg" cx="80" cy="80" r="68"
          stroke="#22c55e" stroke-dasharray="427.26" stroke-dashoffset="427.26"></circle>
      </svg>
      <div class="health-score-text">
        <div class="score-num" id="health-score-num" style="color:var(--text-muted);">—</div>
        <div class="score-label">健康评分</div>
      </div>
    </div>
    <div class="health-info">
      <div class="health-title">组合健康诊断</div>
      <div class="health-desc" id="health-desc">综合评估组合的分散程度、资产配置、收益表现和持有稳定性。</div>
    </div>
  </div>

  <!-- Dimension Score Cards -->
  <div class="dim-grid" id="dim-grid" style="display:none;">
    <div class="dim-card fade-in">
      <div class="dim-label">集中度 <span class="dim-weight">权重 30%</span></div>
      <div class="dim-value" id="dim-concentration">—</div>
      <div class="dim-bar-bg"><div class="dim-bar" id="bar-concentration" style="width:0%;background:var(--border);"></div></div>
    </div>
    <div class="dim-card fade-in">
      <div class="dim-label">类型分散 <span class="dim-weight">权重 30%</span></div>
      <div class="dim-value" id="dim-type-diversity">—</div>
      <div class="dim-bar-bg"><div class="dim-bar" id="bar-type-diversity" style="width:0%;background:var(--border);"></div></div>
    </div>
    <div class="dim-card fade-in">
      <div class="dim-label">收益表现 <span class="dim-weight">权重 20%</span></div>
      <div class="dim-value" id="dim-outperform">—</div>
      <div class="dim-bar-bg"><div class="dim-bar" id="bar-outperform" style="width:0%;background:var(--border);"></div></div>
    </div>
    <div class="dim-card fade-in">
      <div class="dim-label">持有时长 <span class="dim-weight">权重 20%</span></div>
      <div class="dim-value" id="dim-holding-duration">—</div>
      <div class="dim-bar-bg"><div class="dim-bar" id="bar-holding-duration" style="width:0%;background:var(--border);"></div></div>
    </div>
  </div>

  <!-- Composition Grid: Type Doughnut + Duration Bar -->
  <div class="composition-grid" id="chart-grid" style="display:none;">
    <div class="chart-section">
      <div class="section-title">类型分布</div>
      <div class="chart-loading" id="type-loading"><span class="spinner"></span>加载中...</div>
      <div class="chart-wrap" id="type-wrap" style="display:none;"><canvas id="typeChart"></canvas></div>
      <div class="chart-error" id="type-error">暂无类型数据</div>
    </div>
    <div class="chart-section">
      <div class="section-title">
        <span>持有时长</span>
        <span style="font-size:12px;font-weight:400;color:var(--text-muted);" id="avg-duration"></span>
      </div>
      <div class="chart-loading" id="duration-loading"><span class="spinner"></span>加载中...</div>
      <div class="chart-wrap" id="duration-wrap" style="display:none;"><canvas id="durationChart"></canvas></div>
      <div class="chart-error" id="duration-error">暂无持有时长数据</div>
    </div>
  </div>

  <!-- Concentration Bar Chart -->
  <div class="chart-section" id="concentration-section" style="display:none;">
    <div class="section-title">持仓集中度</div>
    <div class="chart-loading" id="concentration-loading"><span class="spinner"></span>加载中...</div>
    <div class="chart-wrap" id="concentration-wrap" style="display:none;"><canvas id="concentrationChart"></canvas></div>
    <div class="chart-error" id="concentration-error">暂无集中度数据</div>
  </div>

  <!-- Peer Comparison Table -->
  <div class="chart-section" id="peer-section" style="display:none;">
    <div class="section-title">同类对比 — 各基金 vs 组合平均</div>
    <div class="chart-loading" id="peer-loading"><span class="spinner"></span>加载中...</div>
    <div class="table-wrap" id="peer-wrap" style="display:none;">
      <table class="peer-table" id="peer-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th class="col-num">回报</th>
            <th class="col-num">vs 平均</th>
          </tr>
        </thead>
        <tbody id="peer-body"></tbody>
      </table>
    </div>
    <div class="chart-error" id="peer-error">暂无同类对比数据</div>
  </div>
</div>

<!-- Loading overlay -->
<div id="loading-overlay">
  <div class="loading-spinner"></div>
  <span>加载组合健康数据...</span>
</div>

<script>
/* ===== State ===== */
var chartInstances = {};

/* ===== Utilities ===== */
function escapeHtml(str) {
  if (str == null) return '';
  var d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
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

function destroyChart(key) {
  if (chartInstances[key]) {
    chartInstances[key].destroy();
    delete chartInstances[key];
  }
}

function scoreColor(score) {
  if (score == null) return '#94a3b8';
  return score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444';
}

function scoreColorCSS(score) {
  if (score == null) return 'var(--text-muted)';
  return score >= 70 ? 'var(--green-text)' : score >= 40 ? 'var(--orange-text)' : 'var(--red-text)';
}

function barColor(score) {
  if (score == null) return 'var(--border)';
  return score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--orange)' : 'var(--red)';
}

/* ===== Theme ===== */
function toggleTheme() {
  var html = document.documentElement;
  var current = html.getAttribute('data-theme') || 'dark';
  var next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  document.getElementById('theme-icon').innerHTML = next === 'dark' ? '&#x2600;&#xFE0F;' : '&#x1F319;';
  rebuildCharts();
}

/* ===== API Helper ===== */
async function fetchAPI(path) {
  var r = await fetch(path);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return await r.json();
}

/* ===== Render Health Score ===== */
function renderHealthScore(data) {
  var score = data.health_score;
  var numEl = document.getElementById('health-score-num');
  numEl.textContent = score != null ? Math.round(score) : '—';
  numEl.style.color = scoreColorCSS(score);

  // Animate SVG gauge
  var circumference = 2 * Math.PI * 68;
  var offset = circumference;
  if (score != null) {
    offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;
  }
  var fg = document.getElementById('health-fg');
  fg.style.stroke = scoreColor(score);
  // Trigger CSS transition on next frame
  requestAnimationFrame(function() {
    requestAnimationFrame(function() {
      fg.style.strokeDashoffset = Math.max(0, offset);
    });
  });

  // Context-aware description
  var desc = document.getElementById('health-desc');
  if (score >= 80) {
    desc.textContent = '组合非常健康！分散配置合理，风险控制得当，持有稳定。继续保持！';
  } else if (score >= 60) {
    desc.textContent = '组合整体良好，仍有优化空间。建议关注集中度和持有时长。';
  } else if (score >= 40) {
    desc.textContent = '组合需要注意。建议降低单只基金权重，增加类型分散度，或延长持有期限。';
  } else {
    desc.textContent = '组合需要大幅调整。集中度过高、类型单一，建议重新评估配置策略。';
  }

  document.getElementById('health-hero').style.display = 'flex';
}

/* ===== Render Dimension Cards ===== */
function renderDimensions(data) {
  var dims = [
    { id: 'concentration', label: '集中度' },
    { id: 'type_diversity', label: '类型分散' },
    { id: 'outperform', label: '收益表现' },
    { id: 'holding_duration', label: '持有时长' },
  ];
  for (var i = 0; i < dims.length; i++) {
    var d = dims[i];
    var val = data[d.id];
    var valEl = document.getElementById('dim-' + d.id);
    var barEl = document.getElementById('bar-' + d.id);
    if (val != null) {
      valEl.textContent = Math.round(val);
      valEl.style.color = scoreColorCSS(val);
      barEl.style.width = val + '%';
      barEl.style.background = barColor(val);
    } else {
      valEl.textContent = '—';
      valEl.style.color = 'var(--text-muted)';
      barEl.style.width = '0%';
    }
  }
  document.getElementById('dim-grid').style.display = 'grid';
}

/* ===== Load Type Distribution (doughnut) ===== */
async function loadTypeDistribution() {
  var wrap = document.getElementById('type-wrap');
  var loading = document.getElementById('type-loading');
  var error = document.getElementById('type-error');
  loading.classList.add('show');
  wrap.style.display = 'none';
  error.classList.remove('show');
  try {
    var data = await fetchAPI('/api/health/type_distribution');
    var dist = data.distribution || [];
    if (dist.length === 0) { loading.classList.remove('show'); error.textContent = '暂无类型数据'; error.classList.add('show'); return; }
    destroyChart('type');
    var textColor = getChartTextColor();
    var colors = ['#2563eb', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];
    loading.classList.remove('show');
    wrap.style.display = 'block';
    chartInstances['type'] = new Chart(document.getElementById('typeChart'), {
      type: 'doughnut',
      data: {
        labels: dist.map(function(d) { return d.type; }),
        datasets: [{
          data: dist.map(function(d) { return d.value_pct; }),
          backgroundColor: dist.map(function(_, i) { return colors[i % colors.length]; }),
          borderColor: isDarkTheme() ? '#1e293b' : '#ffffff',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: textColor, boxWidth: 12, padding: 12, font: { size: 11 } } },
          tooltip: {
            backgroundColor: isDarkTheme() ? '#1e293b' : '#ffffff',
            titleColor: isDarkTheme() ? '#f1f5f9' : '#1e293b',
            bodyColor: isDarkTheme() ? '#94a3b8' : '#64748b',
            borderColor: isDarkTheme() ? '#334155' : '#e2e8f0',
            borderWidth: 1,
            callbacks: { label: function(ctx) { return ctx.label + ': ' + ctx.parsed.toFixed(1) + '%'; } },
          },
        },
        cutout: '55%',
      },
    });
  } catch (e) { loading.classList.remove('show'); error.textContent = '类型数据加载失败'; error.classList.add('show'); }
}

/* ===== Load Holding Duration (horizontal bar) ===== */
async function loadHoldingDuration() {
  var wrap = document.getElementById('duration-wrap');
  var loading = document.getElementById('duration-loading');
  var error = document.getElementById('duration-error');
  var avgEl = document.getElementById('avg-duration');
  loading.classList.add('show');
  wrap.style.display = 'none';
  error.classList.remove('show');
  try {
    var data = await fetchAPI('/api/health/holding_duration');
    var holdings = data.holdings || [];
    avgEl.textContent = data.avg_duration_months != null ? '平均 ' + data.avg_duration_months + ' 个月' : '';
    if (holdings.length === 0) { loading.classList.remove('show'); error.textContent = '暂无持有时长数据'; error.classList.add('show'); return; }
    destroyChart('duration');
    var textColor = getChartTextColor();
    var gridColor = getChartGridColor();
    var sorted = holdings.slice().sort(function(a, b) { return a.duration_months - b.duration_months; });
    loading.classList.remove('show');
    wrap.style.display = 'block';
    chartInstances['duration'] = new Chart(document.getElementById('durationChart'), {
      type: 'bar',
      data: {
        labels: sorted.map(function(h) { return h.name || h.code; }),
        datasets: [{
          label: '持有月数',
          data: sorted.map(function(h) { return h.duration_months; }),
          backgroundColor: sorted.map(function(h) {
            var d = h.duration_months;
            return d >= 12 ? '#22c55e' : d >= 6 ? '#f59e0b' : '#ef4444';
          }),
          borderRadius: 4, borderSkipped: false,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDarkTheme() ? '#1e293b' : '#ffffff',
            titleColor: isDarkTheme() ? '#f1f5f9' : '#1e293b',
            bodyColor: isDarkTheme() ? '#94a3b8' : '#64748b',
            borderColor: isDarkTheme() ? '#334155' : '#e2e8f0',
            borderWidth: 1,
            callbacks: { label: function(ctx) { return ctx.parsed.x + ' 个月'; } },
          },
        },
        scales: {
          x: { ticks: { color: textColor, font: { size: 11 } }, grid: { color: gridColor }, title: { display: true, text: '月数', color: textColor, font: { size: 11 } } },
          y: { ticks: { color: textColor, font: { size: 10 } }, grid: { display: false } },
        },
      },
    });
  } catch (e) { loading.classList.remove('show'); error.textContent = '持有时长加载失败'; error.classList.add('show'); }
}

/* ===== Load Concentration (vertical bar) ===== */
async function loadConcentration() {
  var section = document.getElementById('concentration-section');
  var wrap = document.getElementById('concentration-wrap');
  var loading = document.getElementById('concentration-loading');
  var error = document.getElementById('concentration-error');
  loading.classList.add('show');
  wrap.style.display = 'none';
  error.classList.remove('show');
  try {
    var data = await fetchAPI('/api/health/concentration');
    var topHoldings = data.top_holdings || [];
    if (topHoldings.length === 0) { loading.classList.remove('show'); error.textContent = '暂无集中度数据'; error.classList.add('show'); return; }
    destroyChart('concentration');
    var textColor = getChartTextColor();
    var gridColor = getChartGridColor();
    var labels = topHoldings.map(function(h) { return h.name || h.code; });
    var weights = topHoldings.map(function(h) { return h.weight_pct; });
    loading.classList.remove('show');
    wrap.style.display = 'block';
    section.style.display = 'block';
    chartInstances['concentration'] = new Chart(document.getElementById('concentrationChart'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '权重 %',
          data: weights,
          backgroundColor: weights.map(function(w) { return w > 20 ? '#ef4444' : w > 10 ? '#f59e0b' : '#22c55e'; }),
          borderRadius: 4, borderSkipped: false,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDarkTheme() ? '#1e293b' : '#ffffff',
            titleColor: isDarkTheme() ? '#f1f5f9' : '#1e293b',
            bodyColor: isDarkTheme() ? '#94a3b8' : '#64748b',
            borderColor: isDarkTheme() ? '#334155' : '#e2e8f0',
            borderWidth: 1,
            callbacks: { label: function(ctx) { return ctx.parsed.y.toFixed(1) + '%'; } },
          },
        },
        scales: {
          x: { ticks: { color: textColor, font: { size: 10 }, maxRotation: 45 }, grid: { display: false } },
          y: { ticks: { color: textColor, font: { size: 11 } }, grid: { color: gridColor }, title: { display: true, text: '权重 (%)', color: textColor, font: { size: 11 } }, beginAtZero: true },
        },
      },
    });
  } catch (e) { loading.classList.remove('show'); error.textContent = '集中度加载失败'; error.classList.add('show'); }
}

/* ===== Load Peer Comparison (table) ===== */
async function loadPeerCompare() {
  var section = document.getElementById('peer-section');
  var wrap = document.getElementById('peer-wrap');
  var loading = document.getElementById('peer-loading');
  var error = document.getElementById('peer-error');
  var tbody = document.getElementById('peer-body');
  loading.classList.add('show');
  wrap.style.display = 'none';
  error.classList.remove('show');
  try {
    var data = await fetchAPI('/api/health/peer_compare');
    var peers = data.outperform || [];
    if (peers.length === 0) { loading.classList.remove('show'); error.textContent = '暂无同类对比数据'; error.classList.add('show'); return; }
    loading.classList.remove('show');
    wrap.style.display = 'block';
    section.style.display = 'block';
    var html = '';
    for (var i = 0; i < peers.length; i++) {
      var p = peers[i];
      var retClass = 'col-num ' + (p.return_pct != null ? (p.return_pct >= 0 ? 'text-pos' : 'text-neg') : 'text-muted');
      var vsClass = 'col-num ' + (p.vs_avg != null ? (p.vs_avg >= 0 ? 'text-pos' : 'text-neg') : 'text-muted');
      var retDisplay = p.return_pct != null ? (p.return_pct >= 0 ? '+' : '') + (p.return_pct * 100).toFixed(2) + '%' : '—';
      var vsDisplay = p.vs_avg != null ? (p.vs_avg >= 0 ? '+' : '') + (p.vs_avg * 100).toFixed(2) + '%' : '—';
      html += '<tr>';
      html += '<td class="peer-code">' + escapeHtml(p.code || '') + '</td>';
      html += '<td class="peer-name" title="' + escapeHtml(p.name || '') + '">' + escapeHtml(p.name || '') + '</td>';
      html += '<td class="' + retClass + '">' + retDisplay + '</td>';
      html += '<td class="' + vsClass + '">' + vsDisplay + '</td>';
      html += '</tr>';
    }
    tbody.innerHTML = html;
  } catch (e) { loading.classList.remove('show'); error.textContent = '同类对比加载失败'; error.classList.add('show'); }
}

/* ===== Rebuild Charts on Theme Toggle ===== */
function rebuildCharts() {
  loadTypeDistribution();
  loadHoldingDuration();
  loadConcentration();
}

/* ===== Main Load ===== */
async function loadAll() {
  try {
    var summary = await fetchAPI('/api/health/summary');
    renderHealthScore(summary);
    renderDimensions(summary);

    // Load remaining sections in parallel
    await Promise.all([
      loadTypeDistribution(),
      loadHoldingDuration(),
      loadConcentration(),
      loadPeerCompare(),
    ]);

    document.getElementById('chart-grid').style.display = 'grid';
  } catch (e) {
    console.error('Health page load error:', e);
    throw e;
  }
}

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', function() {
  var html = document.documentElement;
  var theme = html.getAttribute('data-theme') || 'dark';
  var icon = document.getElementById('theme-icon');
  if (icon) icon.innerHTML = theme === 'dark' ? '&#x2600;&#xFE0F;' : '&#x1F319;';

  loadAll().then(function() {
    var overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';
    document.getElementById('app').style.display = 'block';
  }).catch(function(e) {
    var overlay = document.getElementById('loading-overlay');
    if (overlay) {
      overlay.innerHTML = '<p style="color:var(--red-text);">加载失败: ' + escapeHtml(e.message) + '</p>';
    }
  });
});
</script>
</body>
</html>"""


@router.get("/health", response_class=HTMLResponse)
async def health_ui() -> str:
    return HTML
