"""GET / — Web UI with inline HTML"""

import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 添加 CSS
_chart_style = """
.bt-table { width:100%; border-collapse:collapse; font-size:12px; }
.bt-table th { text-align:left; padding:8px 10px; color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.3px; border-bottom:1px solid var(--border); }
.bt-table td { padding:8px 10px; border-bottom:1px solid rgba(30,41,64,.4); }
.bt-table tr:hover td { background:rgba(59,130,246,.03); }
.bt-code { font-family:'SF Mono','Cascadia Code',monospace; font-weight:600; }
.bt-num { font-family:'SF Mono','Cascadia Code',monospace; text-align:right; font-variant-numeric:tabular-nums; }

/* 多策略回测展示 */
.bt-fund-section { padding:16px 0; border-bottom:1px dashed rgba(30,41,64,.6); }
.bt-fund-section:last-child { border-bottom:none; }
.bt-fund-header { display:flex; align-items:center; gap:10px; margin-bottom:10px; padding:4px 0; }
.bt-fund-code { font-family:'SF Mono',monospace; font-weight:700; color:var(--accent); font-size:14px; }
.bt-fund-name { color:var(--text); font-size:13px; opacity:.9; }
.bt-best-tag { margin-left:auto; font-size:11px; padding:3px 10px; border-radius:12px; background:rgba(168,85,247,.15); color:#c4b5fd; border:1px solid rgba(168,85,247,.3); }
.bt-strategy { display:flex; align-items:center; gap:8px; font-weight:500; }
.bt-strategy-dot { display:inline-block; width:8px; height:8px; border-radius:50%; }
.bt-best-pill { font-size:14px; margin-left:4px; }
.bt-table tbody tr td.bt-strategy { color:var(--text); }
"""

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 基金分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root { --bg: #0b0f1a; --surface: #131827; --surface2: #0b0f1a; --border: #1e2940;
           --text: #e2e8f0; --muted: #6b7a99; --accent: #3b82f6; --accent-hover: #60a5fa;
           --green: #22c55e; --red: #ef4444; --amber: #f59e0b; --purple: #8b5cf6; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, 'Inter', 'SF Pro', 'Microsoft YaHei', sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }
  .container { max-width: 1200px; margin:0 auto; padding:24px; }

  .header { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
  .header-left { display:flex; align-items:center; gap:12px; }
  .logo { width:40px; height:40px; background:linear-gradient(135deg,#3b82f6,#8b5cf6);
          border-radius:10px; display:flex; align-items:center; justify-content:center;
          font-size:18px; font-weight:700; color:#fff; }
  .header h1 { font-size:22px; font-weight:700; letter-spacing:-0.3px; }
  .header p { font-size:12px; color:var(--muted); margin-top:2px; }
  .header-right { display:flex; gap:8px; }
  .tab-btn { padding:8px 14px; background:var(--surface); border:1px solid var(--border);
             border-radius:8px; color:var(--muted); font-size:13px; cursor:pointer;
             transition:all .2s; }
  .tab-btn:hover { color:var(--text); border-color:var(--accent); }
  .tab-btn.active { color:var(--text); border-color:var(--accent); background:rgba(59,130,246,.1); }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
          padding:20px; margin-bottom:16px; }
  .card-title { font-size:14px; font-weight:600; margin-bottom:14px;
                display:flex; align-items:center; gap:8px; }
  .form-row { display:flex; gap:12px; align-items:end; flex-wrap:wrap; }
  .form-group { flex:1; min-width:140px; }
  .form-group label { display:block; font-size:12px; font-weight:500;
                      color:var(--muted); margin-bottom:6px; }
  textarea, select, input { width:100%; padding:8px 12px; border-radius:8px;
         border:1px solid var(--border); background:#0b0f1a; color:var(--text);
         font-size:13px; font-family:inherit; transition:border-color .2s; }
  textarea:focus, select:focus, input:focus { outline:none; border-color:var(--accent); }
  textarea { resize:vertical; min-height:40px; font-family:'SF Mono','Cascadia Code',monospace; }
  select { cursor:pointer; appearance:none; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236b7a99' d='M6 8.5L1 3.5h10z'/%3E%3C/svg%3E");
           background-repeat:no-repeat; background-position:right 10px center; padding-right:30px; }
  .checkbox-group { display:flex; align-items:center; gap:6px; height:40px; }
  .checkbox-group input { width:auto; }
  .checkbox-group label { margin:0; cursor:pointer; font-size:12px; color:var(--text); font-weight:400; }

  .btn { display:inline-flex; align-items:center; gap:6px; padding:9px 20px;
         border-radius:8px; font-size:13px; font-weight:600; border:none;
         cursor:pointer; transition:all .2s; background:var(--accent); color:#fff; }
  .btn:hover { background:var(--accent-hover); transform:translateY(-1px); }
  .btn:disabled { opacity:.5; cursor:not-allowed; transform:none; }
  .btn-secondary { background:transparent; border:1px solid var(--border); color:var(--text); }
  .btn-secondary:hover { background:var(--surface); border-color:var(--accent); }
  .btn-icon { padding:6px 10px; font-size:11px; }
  .spinner { display:inline-block; width:14px; height:14px;
             border:2px solid rgba(255,255,255,.2); border-top-color:#fff;
             border-radius:50%; animation:spin .6s linear infinite; }
  @keyframes spin { to{transform:rotate(360deg)} }

  .signal-badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px;
                  border-radius:16px; font-size:11px; font-weight:600; }
  .signal-badge.bullish { background:rgba(34,197,94,.15); color:var(--green); }
  .signal-badge.neutral { background:rgba(245,158,11,.15); color:var(--amber); }
  .signal-badge.bearish { background:rgba(239,68,68,.15); color:var(--red); }

  .fund-card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
               margin-bottom:14px; overflow:hidden; }
  .fund-card-header { padding:16px 20px 12px;
                      display:flex; align-items:center; justify-content:space-between;
                      flex-wrap:wrap; gap:10px; cursor:pointer; user-select:none; }
  .fund-card-header:hover { background:rgba(59,130,246,.03); }
  .fund-card-header .chevron { color:var(--muted); font-size:11px; transition:transform .2s; }
  .fund-card.expanded .chevron { transform:rotate(180deg); }
  .fund-info { display:flex; align-items:center; gap:10px; }
  .fund-code { font-family:'SF Mono','Cascadia Code',monospace; font-size:13px;
               color:var(--muted); }
  .fund-name { font-size:15px; font-weight:600; }
  .fund-score { font-size:22px; font-weight:700; letter-spacing:-0.5px; min-width:48px;
                text-align:right; }

  .agent-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
                gap:10px; padding:0 20px 16px; }
  .agent-card { background:#0b0f1a; border:1px solid var(--border); border-radius:8px;
                padding:12px; }
  .agent-name { font-size:12px; font-weight:500; color:var(--muted); margin-bottom:6px; }
  .agent-row { display:flex; align-items:center; justify-content:space-between; }
  .agent-signal { font-size:11px; font-weight:700; text-transform:uppercase;
                  letter-spacing:.4px; }
  .agent-score { font-size:16px; font-weight:700; }
  .agent-score.high { color:var(--green); }
  .agent-score.mid { color:var(--amber); }
  .agent-score.low { color:var(--red); }
  .agent-confidence { font-size:10px; color:var(--muted); margin-top:4px; }

  .reasoning-box { background:#060a12; border:1px solid var(--border); border-radius:8px;
                   padding:12px 16px; margin:0 20px 14px; font-size:12px;
                   line-height:1.6; font-family:'SF Mono','Cascadia Code',monospace;
                   white-space:pre-wrap; color:#94a3b8; }
  .reasoning-box strong { color:var(--text); }
  .llm-reasoning { background:linear-gradient(135deg,rgba(59,130,246,.08),rgba(139,92,246,.08));
                   border:1px solid rgba(59,130,246,.25); border-radius:8px;
                   padding:14px 18px; margin:0 20px 14px; font-size:12px; line-height:1.7;
                   white-space:pre-wrap; color:#c8d6e5; }
  .llm-reasoning strong { color:#60a5fa; font-size:13px; }

  .score-bar-bg { height:3px; background:var(--border); border-radius:2px;
                  margin:6px 20px 12px; overflow:hidden; }
  .score-bar { height:100%; border-radius:2px; transition:width .6s ease; }

  @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  .fund-card { animation:fadeIn .3s ease; }
  .empty-state { text-align:center; padding:50px 20px; color:var(--muted); }
  .empty-state .icon { font-size:42px; margin-bottom:12px; opacity:.5; }
  .empty-state h3 { font-size:16px; margin-bottom:6px; color:var(--text); }
  .empty-state p { font-size:13px; line-height:1.6; }

  /* Charts */
  .chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
  .chart-card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
                padding:18px; }
  .chart-card.full { grid-column:1 / -1; }
  .chart-card h3 { font-size:13px; font-weight:600; margin-bottom:10px;
                   color:var(--text); display:flex; align-items:center; gap:6px; }
  .chart-wrap { position:relative; height:280px; }
  .chart-wrap.tall { height:340px; }

  /* History */
  .history-item { display:flex; align-items:center; justify-content:space-between;
                  padding:10px 14px; background:#0b0f1a; border-radius:8px;
                  margin-bottom:6px; cursor:pointer; transition:all .2s;
                  border:1px solid transparent; }
  .history-item:hover { border-color:var(--accent); }
  .history-codes { font-family:'SF Mono',monospace; font-size:13px; font-weight:600; }
  .history-meta { display:flex; gap:10px; font-size:11px; color:var(--muted); align-items:center; }
  .tag { padding:2px 7px; border-radius:10px; font-size:10px; font-weight:500; }
  .tag-llm { background:rgba(139,92,246,.15); color:var(--purple); }
  .tag-bt { background:rgba(59,130,246,.15); color:var(--accent); }
  .tag-rc { background:rgba(34,197,94,.15); color:var(--green); }

  /* Favorites */
  .fav-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:10px; }
  .fav-card { background:#0b0f1a; border:1px solid var(--border); border-radius:8px;
              padding:12px; position:relative; cursor:pointer; transition:all .2s; }
  .fav-card:hover { border-color:var(--accent); }
  .fav-code { font-family:'SF Mono',monospace; font-size:12px; color:var(--muted); }
  .fav-name { font-size:13px; font-weight:600; margin-top:2px; }
  .fav-remove { position:absolute; top:6px; right:6px; background:transparent;
                border:none; color:var(--muted); cursor:pointer; font-size:12px; }
  .fav-remove:hover { color:var(--red); }

  /* Modal */
  .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.6);
           z-index:100; align-items:center; justify-content:center; }
  .modal.show { display:flex; }
  .modal-content { background:var(--surface); border:1px solid var(--border);
                   border-radius:12px; padding:20px; max-width:400px; width:90%; }
  .modal h3 { font-size:15px; margin-bottom:12px; }
  .modal input { margin-bottom:10px; }
  .modal-buttons { display:flex; gap:8px; justify-content:flex-end; margin-top:8px; }

  @media (max-width: 768px) {
    .chart-grid { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-left">
      <div class="logo">AI</div>
      <div>
        <h1>AI 基金分析</h1>
        <p>多 Agent 智能评估 · 持仓深度分析 · 历史可追溯</p>
      </div>
    </div>
    <div class="header-right">
      <button class="tab-btn active" onclick="switchTab('analyze')">分析</button>
      <button class="tab-btn" onclick="switchTab('history')">历史</button>
      <button class="tab-btn" onclick="switchTab('favorites')">关注</button>
    </div>
  </div>

  <!-- Analyze Tab -->
  <div id="tab-analyze">
    <div class="card">
      <div class="card-title">🔍 分析配置</div>
      <div class="form-row">
        <div class="form-group" style="flex:2">
          <label>基金代码（逗号分隔）</label>
          <textarea id="codes" placeholder="例如：019305, 110011, 000001" rows="1">019305, 110011</textarea>
        </div>
        <div class="form-group">
          <label>回溯月数</label>
          <select id="months">
            <option value="12">12</option>
            <option value="24" selected>24</option>
            <option value="36">36</option>
            <option value="60">60</option>
          </select>
        </div>
        <div class="form-group">
          <div class="checkbox-group"><input type="checkbox" id="reasoning"><label for="reasoning">推理细节</label></div>
        </div>
        <div class="form-group">
          <div class="checkbox-group"><input type="checkbox" id="use_llm" checked><label for="use_llm">LLM 分析</label></div>
        </div>
        <div class="form-group">
          <div class="checkbox-group"><input type="checkbox" id="backtest"><label for="backtest">回测</label></div>
        </div>
        <div class="form-group" style="flex:0">
          <button class="btn" id="btn" onclick="analyze()">开始分析</button>
        </div>
      </div>
    </div>

    <div id="results"></div>
  </div>

  <!-- History Tab -->
  <div id="tab-history" style="display:none;">
    <div class="card">
      <div class="card-title">📚 分析历史 <span style="font-weight:400;color:var(--muted);font-size:12px;margin-left:auto;">点击加载历史结果</span></div>
      <div id="history-list"><div class="empty-state"><div class="icon">📜</div><p>加载中...</p></div></div>
    </div>
  </div>

  <!-- Favorites Tab -->
  <div id="tab-favorites" style="display:none;">
    <div class="card">
      <div class="card-title">⭐ 关注的基金
        <button class="btn btn-icon" style="margin-left:auto;" onclick="showAddFav()">+ 添加</button>
      </div>
      <div id="favorites-list" class="fav-grid"></div>
    </div>
  </div>
</div>

<!-- Add Favorite Modal -->
<div id="fav-modal" class="modal">
  <div class="modal-content">
    <h3>添加关注基金</h3>
    <input id="fav-code" placeholder="基金代码（如 019305）">
    <input id="fav-name" placeholder="备注名称（可选）">
    <div class="modal-buttons">
      <button class="btn btn-secondary" onclick="closeFav()">取消</button>
      <button class="btn" onclick="addFav()">添加</button>
    </div>
  </div>
</div>

<script>
const SIGNAL_LABELS = {bullish:'看多', neutral:'中性', bearish:'看空'};
const SIGNAL_COLORS = {bullish:'#22c55e', neutral:'#f59e0b', bearish:'#ef4444'};
const CHART_COLORS = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#10b981'];
let navChart = null, radarChart = null;

function scoreColor(s) { if (s >= 65) return 'high'; if (s >= 40) return 'mid'; return 'low'; }
function scoreBarColor(s) { if (s >= 65) return '#22c55e'; if (s >= 40) return '#f59e0b'; return '#ef4444'; }

function switchTab(tab) {
  document.getElementById('tab-analyze').style.display = tab === 'analyze' ? 'block' : 'none';
  document.getElementById('tab-history').style.display = tab === 'history' ? 'block' : 'none';
  document.getElementById('tab-favorites').style.display = tab === 'favorites' ? 'block' : 'none';
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    const tabs = ['analyze', 'history', 'favorites'];
    b.classList.toggle('active', tabs[i] === tab);
  });
  if (tab === 'history') loadHistory();
  if (tab === 'favorites') loadFavorites();
}

async function analyze() {
  const btn = document.getElementById('btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>分析中...';
  document.getElementById('results').innerHTML = '';
  if (navChart) { navChart.destroy(); navChart = null; }
  if (radarChart) { radarChart.destroy(); radarChart = null; }

  try {
    const codes = document.getElementById('codes').value;
    const months = document.getElementById('months').value;
    const reasoning = document.getElementById('reasoning').checked ? '1' : '0';
    const use_llm = document.getElementById('use_llm').checked ? '1' : '0';
    const backtest = document.getElementById('backtest').checked ? '1' : '0';

    const resp = await fetch('/analyze', {
      method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body: new URLSearchParams({codes, months, reasoning, use_llm, backtest}),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      // 兼容 FastAPI 422 detail 数组 / 对象 / 字符串
      const detail = data.detail || data.error || '请求失败';
      let msg;
      if (typeof detail === 'string') msg = detail;
      else if (Array.isArray(detail)) {
        msg = detail.map(d => `${d.loc?.join('.')||''}: ${d.msg||JSON.stringify(d)}`).join('; ');
      } else msg = JSON.stringify(detail);
      throw new Error(msg);
    }

    if (data._record_id) {
      btn.innerHTML = '<span class="spinner"></span>分析完成，保存 #' + data._record_id;
    }
    renderResults(data);
  } catch(e) {
    document.getElementById('results').innerHTML =
      `<div class="card" style="border-color:rgba(239,68,68,.3);">
        <div style="color:var(--red);font-weight:600;">❌ 错误: ${e.message}</div>
       </div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '重新分析';
  }
}

function renderResults(data) {
  const bt = data._backtesting || [];
  const navHistory = data._nav_history || {};
  delete data._backtesting;
  delete data._nav_history;

  const codes = Object.keys(data);
  if (codes.length === 0) {
    document.getElementById('results').innerHTML = '<div class="empty-state"><div class="icon">📭</div><h3>无数据</h3><p>未获取到基金数据</p></div>';
    return;
  }

  let html = '';
  for (const code of codes) {
    const f = data[code];
    const s = f.summary || {};
    const agents = f.agents || {};
    const agentKeys = Object.keys(agents);
    const signal = s.final_signal || 'neutral';
    const score = s.score || 50;
    const confidence = s.confidence || 0;

    html += `
      <div class="fund-card">
        <div class="fund-card-header" onclick="toggleAgents('${code}')">
          <div class="fund-info">
            <div>
              <span class="fund-code">${code}</span>
              <div class="fund-name">${f.name}</div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:14px;">
            <span class="signal-badge ${signal}">${SIGNAL_LABELS[signal]}</span>
            <div style="text-align:right;">
              <div class="fund-score" style="color:${scoreBarColor(score)}">${score}</div>
              <div style="font-size:10px;color:var(--muted);">置信 ${confidence}%</div>
            </div>
            <span class="chevron">▼</span>
          </div>
        </div>
        <div class="score-bar-bg"><div class="score-bar" style="width:${score}%;background:${scoreBarColor(score)}"></div></div>
        <div id="agents-${code}" style="padding-top:8px;">
          <div style="padding:0 20px 10px;font-size:12px;color:var(--muted);">
            看多 ${s.bullish_agents||0} · 看空 ${s.bearish_agents||0} · 共 ${s.total_agents||0} Agent
          </div>
          <div class="agent-grid">`;

    for (const key of agentKeys) {
      const a = agents[key];
      const aScore = a.score || 0;
      html += `
        <div class="agent-card">
          <div class="agent-name">${agentLabel(key)}</div>
          <div class="agent-row">
            <span class="agent-signal" style="color:${SIGNAL_COLORS[a.signal]||'#6b7a99'}">${SIGNAL_LABELS[a.signal]||a.signal}</span>
            <span class="agent-score ${scoreColor(aScore)}">${aScore}</span>
          </div>
          <div class="score-bar-bg" style="margin:6px 0 0;"><div class="score-bar" style="width:${aScore}%;background:${scoreBarColor(aScore)}"></div></div>
          <div class="agent-confidence">置信 ${a.confidence || 0}%</div>
        </div>`;
    }
    html += `</div>`;

    if (document.getElementById('reasoning').checked) {
      for (const key of agentKeys) {
        const a = agents[key];
        if (a.reasoning && typeof a.reasoning === 'string' && a.reasoning.trim()) {
          if (key === 'llm') {
            html += `<div class="llm-reasoning"><strong>🧠 LLM 深度分析</strong>\n\n${a.reasoning}</div>`;
          } else {
            html += `<div class="reasoning-box"><strong>${agentLabel(key)} 推理</strong>\n\n${a.reasoning}</div>`;
          }
        }
      }
    }
    html += `</div></div>`;
  }

  // Charts section
  if (codes.length > 0) {
    html += `<div class="chart-grid" id="charts-section">`;
    if (codes.length >= 2 && navHistory && Object.keys(navHistory).length >= 2) {
      html += `<div class="chart-card full">
        <h3>📈 净值走势叠加</h3>
        <div class="chart-wrap tall"><canvas id="navChart"></canvas></div>
      </div>`;
    }
    if (codes.length >= 2) {
      html += `<div class="chart-card full">
        <h3>🎯 Agent 评分雷达对比</h3>
        <div class="chart-wrap tall"><canvas id="radarChart"></canvas></div>
      </div>`;
    }
    html += `</div>`;
  }

  document.getElementById('results').innerHTML = html;

  if (bt && bt.length > 0) renderBacktesting(bt);
  if (navHistory && Object.keys(navHistory).length >= 2) renderNavChart(navHistory, data);
  if (codes.length >= 2) renderRadarChart(data);
}

function renderNavChart(navHistory, data) {
  const ctx = document.getElementById('navChart');
  if (!ctx) return;
  // 归一化为 100 起点
  const datasets = [];
  let i = 0;
  for (const code of Object.keys(navHistory)) {
    const navs = navHistory[code];
    if (!navs || navs.length === 0) continue;
    const start = navs[0].nav;
    const normalized = navs.map(n => ({x: n.date, y: (n.nav / start * 100).toFixed(2)}));
    datasets.push({
      label: code + ' ' + (data[code] ? data[code].name : ''),
      data: normalized,
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.1,
    });
    i++;
  }
  navChart = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
        tooltip: { backgroundColor: '#0b0f1a', borderColor: '#1e2940', borderWidth: 1 }
      },
      scales: {
        x: { type: 'category', ticks: { color: '#6b7a99', maxTicksLimit: 8 }, grid: { color: 'rgba(30,41,64,.3)' } },
        y: { ticks: { color: '#6b7a99', callback: v => v }, grid: { color: 'rgba(30,41,64,.3)' },
             title: { display: true, text: '归一化净值（起点=100）', color: '#6b7a99', font: { size: 10 } } }
      }
    }
  });
}

function renderRadarChart(data) {
  const ctx = document.getElementById('radarChart');
  if (!ctx) return;
  const codes = Object.keys(data);
  if (codes.length < 2) return;
  // 统一 Agent 集合
  const agentSet = new Set();
  for (const code of codes) {
    const agents = data[code].agents || {};
    for (const k of Object.keys(agents)) agentSet.add(k);
  }
  const agentKeys = Array.from(agentSet).filter(k => k !== 'llm' || document.getElementById('use_llm').checked);
  const labels = agentKeys.map(k => agentLabel(k));

  const datasets = codes.map((code, i) => {
    const agents = data[code].agents || {};
    const values = agentKeys.map(k => (agents[k] ? agents[k].score : 0));
    return {
      label: code,
      data: values,
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '22',
      borderWidth: 2,
      pointRadius: 3,
    };
  });

  radarChart = new Chart(ctx, {
    type: 'radar',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
      scales: {
        r: {
          beginAtZero: true, max: 100,
          ticks: { color: '#6b7a99', backdropColor: 'transparent', stepSize: 25 },
          grid: { color: 'rgba(30,41,64,.5)' },
          angleLines: { color: 'rgba(30,41,64,.5)' },
          pointLabels: { color: '#cbd5e1', font: { size: 11 } }
        }
      }
    }
  });
}

// ===== 回测渲染 =====
const STRATEGY_COLORS = {
  'sma': '#3b82f6',      // 蓝
  'trend': '#a855f7',    // 紫
  'hold': '#6b7280',     // 灰
};

function strategyLabel(s) {
  const map = {'sma':'SMA 交叉', 'trend':'趋势跟踪', 'hold':'买入持有'};
  return map[s] || s;
}

function strategyColor(s) {
  return STRATEGY_COLORS[s] || '#94a3b8';
}

function renderBacktesting(bt) {
  if (!bt || bt.length === 0) return;

  // 按基金代码分组
  const grouped = {};
  for (const r of bt) {
    if (!grouped[r.code]) grouped[r.code] = [];
    grouped[r.code].push(r);
  }

  let html = '<div class="card"><div class="card-title">📊 回测结果 (backtrader)</div>';

  for (const code of Object.keys(grouped)) {
    const rows = grouped[code];
    const fundName = rows[0].name || code;

    // 找最佳策略 (按 sharpe)
    const best = rows.reduce((a, b) => (b.sharpe_ratio > a.sharpe_ratio ? b : a), rows[0]);
    const isMultiStrategy = rows.length > 1;

    html += `<div class="bt-fund-section">`;
    html += `<div class="bt-fund-header">
      <span class="bt-fund-code">${code}</span>
      <span class="bt-fund-name">${fundName}</span>
      <span class="bt-best-tag">最优: ${strategyLabel(best.strategy)} (Sharpe ${best.sharpe_ratio.toFixed(2)})</span>
    </div>`;

    html += `<div style="overflow-x:auto;"><table class="bt-table">
      <thead><tr>
        <th>策略</th>
        <th>收益</th>
        <th>年化</th>
        <th>买入持有</th>
        <th>超额α</th>
        <th>最大回撤</th>
        <th>夏普</th>
        <th>SQN</th>
        <th>胜率</th>
        <th>交易</th>
      </tr></thead><tbody>`;

    for (const r of rows) {
      if (r.error) {
        html += `<tr><td colspan="10" style="color:#ef4444">${strategyLabel(r.strategy)}: ${r.error}</td></tr>`;
        continue;
      }
      const color = strategyColor(r.strategy);
      const retColor = r.total_return_pct >= 0 ? '#22c55e' : '#ef4444';
      const isBest = isMultiStrategy && r === best;
      const rowStyle = isBest ? `background:${color}11; border-left:3px solid ${color}` : '';
      html += `<tr style="${rowStyle}">
        <td class="bt-strategy">
          <span class="bt-strategy-dot" style="background:${color}"></span>
          ${strategyLabel(r.strategy)}
          ${isBest ? '<span class="bt-best-pill">👑</span>' : ''}
        </td>
        <td class="bt-num" style="color:${retColor}">${r.total_return_pct > 0 ? '+' : ''}${r.total_return_pct.toFixed(1)}%</td>
        <td class="bt-num">${r.annualized_return_pct > 0 ? '+' : ''}${r.annualized_return_pct.toFixed(1)}%</td>
        <td class="bt-num" style="color:#94a3b8">${r.buy_and_hold_return_pct > 0 ? '+' : ''}${r.buy_and_hold_return_pct.toFixed(1)}%</td>
        <td class="bt-num" style="color:${r.alpha >= 0 ? '#22c55e' : '#ef4444'}">${r.alpha > 0 ? '+' : ''}${r.alpha.toFixed(1)}%</td>
        <td class="bt-num" style="color:#ef4444">-${Math.abs(r.max_drawdown_pct).toFixed(1)}%</td>
        <td class="bt-num">${r.sharpe_ratio.toFixed(2)}</td>
        <td class="bt-num" style="color:#94a3b8">${r.sqn.toFixed(2)}</td>
        <td class="bt-num">${r.win_rate.toFixed(0)}%</td>
        <td class="bt-num">${r.total_trades}</td>
      </tr>`;
    }
    html += `</tbody></table></div>`;

    // 净值曲线叠加图 (3 策略 + 基准)
    html += `<div class="chart-wrap" style="margin-top:12px"><canvas id="btChart-${code}"></canvas></div>`;
    html += `</div>`;
  }
  html += '</div>';

  document.getElementById('results').innerHTML += html;

  // 画每个基金的回测曲线
  for (const code of Object.keys(grouped)) {
    const rows = grouped[code].filter(r => !r.error && r.equity_curve && r.equity_curve.length > 0);
    if (rows.length > 0) renderBacktestChart(code, rows);
  }
}

function renderBacktestChart(code, rows) {
  const ctx = document.getElementById(`btChart-${code}`);
  if (!ctx) return;
  const datasets = rows.map(r => ({
    label: strategyLabel(r.strategy),
    data: r.equity_curve.map(p => ({x: p.date, y: parseFloat(p.value)})),
    borderColor: strategyColor(r.strategy),
    backgroundColor: 'transparent',
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.1,
  }));
  // 基准线 (取第一条的 buy_and_hold 即可, 它们都相同)
  if (rows[0].equity_curve && rows[0].equity_curve[0].benchmark_value) {
    datasets.push({
      label: '买入持有基准',
      data: rows[0].equity_curve.map(p => ({x: p.date, y: parseFloat(p.benchmark_value)})),
      borderColor: '#fbbf24',
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      borderDash: [5, 5],
      pointRadius: 0,
      tension: 0.1,
    });
  }
  new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 }, usePointStyle: true, padding: 12 } },
        tooltip: { backgroundColor: '#0b0f1a', borderColor: '#1e2940', borderWidth: 1,
          callbacks: { label: (ctx) => ctx.dataset.label + ': ¥' + Math.round(ctx.parsed.y).toLocaleString() } }
      },
      scales: {
        x: { type: 'category', ticks: { color: '#6b7a99', maxTicksLimit: 8 }, grid: { color: 'rgba(30,41,64,.3)' } },
        y: { ticks: { color: '#6b7a99', callback: v => '¥' + (v/1000).toFixed(0) + 'k' }, grid: { color: 'rgba(30,41,64,.3)' } }
      }
    }
  });
}

function toggleAgents(code) {
  const el = document.getElementById('agents-' + code);
  if (el) {
    const card = el.closest('.fund-card');
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? 'block' : 'none';
    if (card) card.classList.toggle('expanded', hidden);
  }
}

function agentLabel(key) {
  const map = {trend:'趋势', risk:'风险', manager:'经理', valuation:'估值', peer:'同类', llm:'LLM', holdings:'持仓'};
  return map[key] || key;
}

// ===== History =====
async function loadHistory() {
  const el = document.getElementById('history-list');
  el.innerHTML = '<div class="empty-state"><div class="icon">📜</div><p>加载中...</p></div>';
  try {
    const r = await fetch('/api/history?limit=50');
    const data = await r.json();
    if (!data.history || data.history.length === 0) {
      el.innerHTML = '<div class="empty-state"><div class="icon">📭</div><h3>暂无历史</h3><p>完成一次分析后会自动保存</p></div>';
      return;
    }
    let html = '';
    for (const h of data.history) {
      const tags = [];
      if (h.use_llm) tags.push('<span class="tag tag-llm">LLM</span>');
      if (h.backtest) tags.push('<span class="tag tag-bt">回测</span>');
      html += `<div class="history-item" onclick="loadHistoryItem(${h.id})">
        <div>
          <div class="history-codes">${h.codes}</div>
          <div class="history-meta">${h.datetime} · ${h.months}月 · ${tags.join(' ') || '<span style="opacity:.5">基础分析</span>'}</div>
        </div>
        <span style="color:var(--muted);font-size:18px;">→</span>
      </div>`;
    }
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>' + e.message + '</p></div>';
  }
}

async function loadHistoryItem(id) {
  switchTab('analyze');
  document.getElementById('codes').value = '';
  document.getElementById('results').innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载历史 #' + id + '...</p></div>';
  try {
    const r = await fetch('/api/history/' + id);
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    document.getElementById('results').innerHTML = '';
    renderResults(data);
  } catch(e) {
    document.getElementById('results').innerHTML = '<div class="card" style="border-color:rgba(239,68,68,.3);"><div style="color:var(--red)">❌ ' + e.message + '</div></div>';
  }
}

// ===== Favorites =====
async function loadFavorites() {
  const el = document.getElementById('favorites-list');
  try {
    const r = await fetch('/api/favorites');
    const data = await r.json();
    if (!data.favorites || data.favorites.length === 0) {
      el.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><div class="icon">⭐</div><p>还没有关注的基金</p></div>';
      return;
    }
    let html = '';
    for (const f of data.favorites) {
      html += `<div class="fav-card" onclick="quickAnalyze('${f.code}')">
        <button class="fav-remove" onclick="event.stopPropagation();removeFav('${f.code}')">✕</button>
        <div class="fav-code">${f.code}</div>
        <div class="fav-name">${f.name || f.note || '点击分析'}</div>
      </div>`;
    }
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="empty-state">' + e.message + '</div>';
  }
}

function quickAnalyze(code) {
  document.getElementById('codes').value = code;
  switchTab('analyze');
  analyze();
}

function showAddFav() {
  document.getElementById('fav-modal').classList.add('show');
  document.getElementById('fav-code').focus();
}
function closeFav() {
  document.getElementById('fav-modal').classList.remove('show');
  document.getElementById('fav-code').value = '';
  document.getElementById('fav-name').value = '';
}
async function addFav() {
  const code = document.getElementById('fav-code').value.trim();
  const name = document.getElementById('fav-name').value.trim();
  if (!code) return;
  const fd = new FormData();
  fd.append('code', code);
  fd.append('name', name);
  await fetch('/api/favorites', { method: 'POST', body: fd });
  closeFav();
  loadFavorites();
}
async function removeFav(code) {
  await fetch('/api/favorites/' + encodeURIComponent(code), { method: 'DELETE' });
  loadFavorites();
}
</script>
</body>
</html>"""

HTML = HTML.replace("</style>\n</head>", "</style>\n<style>" + _chart_style + "</style>\n</head>")


@router.get("/", response_class=HTMLResponse)
async def index():
    return HTML
