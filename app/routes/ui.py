"""GET / — Portfolio watchlist UI: 收藏表 + 滑出面板 + SSE 批量刷新

All CSS and JS are inline in a single file. Light theme.
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
<title>我的基金组合</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
/* ===== Reset & Variables ===== */
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
  --green: #22c55e;
  --green-bg: #f0fdf4;
  --red: #ef4444;
  --red-bg: #fef2f2;
  --orange: #f59e0b;
  --orange-bg: #fffbeb;
  --gray: #94a3b8;
  --gray-bg: #f8fafc;
  --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.12);
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.2s ease;
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
.app-container { max-width: 1280px; margin: 0 auto; padding: 24px; }

/* ===== Toolbar ===== */
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
}
.toolbar-left h1 {
  font-size: 22px; font-weight: 700; letter-spacing: -0.3px;
  color: var(--text);
}
.toolbar-left .subtitle {
  font-size: 13px; color: var(--text-secondary); margin-top: 2px;
}
.toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* ===== Buttons ===== */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600; border: none; cursor: pointer;
  transition: all var(--transition); white-space: nowrap;
}
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border);
}
.btn-secondary:hover { border-color: var(--primary); color: var(--primary); }
.btn-danger { background: var(--red); color: #fff; }
.btn-danger:hover { background: #dc2626; }
.btn-sm { padding: 4px 10px; font-size: 12px; border-radius: 6px; }
.btn-icon { padding: 6px 10px; font-size: 11px; }

/* ===== Progress Section ===== */
#progress-section {
  display: none; margin-bottom: 16px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 18px;
  box-shadow: var(--shadow);
}
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.progress-label { font-size: 13px; font-weight: 600; color: var(--text); }
.progress-text { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.progress-bar-bg {
  height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;
}
.progress-bar {
  height: 100%; background: var(--primary); border-radius: 3px;
  transition: width 0.3s ease; width: 0%;
}

/* ===== Empty State ===== */
#empty-state {
  display: none; text-align: center; padding: 60px 20px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
}
#empty-state .empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.6; }
#empty-state h3 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
#empty-state p { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }
#empty-state .btn { margin-top: 16px; }

/* ===== Table ===== */
.table-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden;
}
.table-wrap { overflow-x: auto; }
#favorites-table {
  width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px;
}
#favorites-table thead th {
  text-align: left; padding: 12px 14px; font-size: 11px; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
  background: #f8fafc; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
#favorites-table tbody td {
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
#favorites-table tbody tr:last-child td { border-bottom: none; }
#favorites-table tbody tr:hover { background: #f8fafc; }
#favorites-table tbody tr { transition: background var(--transition); }

/* Column alignment */
.col-code { font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace; font-weight: 600; font-size: 13px; }
.col-name { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-num {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap;
}
.col-date { white-space: nowrap; color: var(--text-secondary); font-size: 12px; }
.col-actions { white-space: nowrap; text-align: right; }

/* Status badge */
.status-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500;
}
.status-badge.ok { background: var(--green-bg); color: #16a34a; }
.status-badge.no_quote { background: var(--gray-bg); color: var(--gray); }
.status-badge.no_history { background: var(--orange-bg); color: #d97706; }
.status-badge.error { background: var(--red-bg); color: #dc2626; }

/* Return % color */
.return-pos { color: #16a34a; font-weight: 600; }
.return-neg { color: #dc2626; font-weight: 600; }
.return-nil { color: var(--text-muted); }

/* Max drawdown color intensity */
.dd-low { color: #16a34a; }       /* 0-10% */
.dd-mid { color: #d97706; }       /* 10-20% */
.dd-high { color: #dc2626; }      /* 20%+ */
.dd-nil { color: var(--text-muted); }

/* ===== Detail Panel (slide-out) ===== */
#detail-panel {
  position: fixed; top: 0; right: -480px; width: 480px; height: 100%;
  background: var(--surface); box-shadow: -4px 0 20px rgba(0,0,0,0.12);
  transition: right 0.3s ease; overflow-y: auto; padding: 0; z-index: 1000;
  display: flex; flex-direction: column;
}
#detail-panel.open { right: 0; }

#detail-panel .panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--surface); z-index: 1;
}
#detail-panel .panel-title { font-size: 16px; font-weight: 700; }
#detail-panel .panel-close {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border: none; background: #f1f5f9; border-radius: 50%; cursor: pointer;
  font-size: 16px; color: var(--text-secondary); transition: all var(--transition);
}
#detail-panel .panel-close:hover { background: #e2e8f0; color: var(--text); }

#detail-panel .panel-loading {
  display: flex; align-items: center; justify-content: center;
  flex: 1; padding: 40px; color: var(--text-muted); font-size: 14px;
}
.panel-spinner {
  width: 24px; height: 24px; border: 3px solid #e2e8f0;
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin 0.6s linear infinite; margin-right: 10px;
}

#detail-panel .panel-body { padding: 20px 22px; flex: 1; overflow-y: auto; }

/* Analysis result cards in panel */
.panel-signal {
  display: flex; align-items: center; gap: 12px; padding: 14px 18px;
  border-radius: var(--radius-sm); margin-bottom: 16px;
}
.panel-signal.bullish { background: var(--green-bg); }
.panel-signal.neutral { background: var(--orange-bg); }
.panel-signal.bearish { background: var(--red-bg); }
.panel-signal .signal-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.panel-signal.bullish .signal-dot { background: var(--green); }
.panel-signal.neutral .signal-dot { background: var(--orange); }
.panel-signal.bearish .signal-dot { background: var(--red); }
.panel-signal .signal-label { font-size: 15px; font-weight: 700; }
.panel-signal .signal-score { font-size: 22px; font-weight: 700; margin-left: auto; }
.panel-signal .signal-conf { font-size: 11px; color: var(--text-secondary); }

.panel-agent-card {
  background: #f8fafc; border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 10px;
}
.panel-agent-card .agent-head {
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}
.panel-agent-card .agent-name { font-size: 13px; font-weight: 600; }
.panel-agent-card .agent-signal { font-size: 11px; font-weight: 600; text-transform: uppercase; }
.panel-agent-card .agent-signal.bullish { color: #16a34a; }
.panel-agent-card .agent-signal.neutral { color: #d97706; }
.panel-agent-card .agent-signal.bearish { color: #dc2626; }
.panel-agent-card .agent-score { font-size: 16px; font-weight: 700; }
.panel-agent-card .agent-reasoning {
  font-size: 12px; line-height: 1.6; color: var(--text-secondary);
  margin-top: 8px; display: none;
}
.panel-agent-card.expanded .agent-reasoning { display: block; }

/* LLM reasoning rendered as markdown */
.llm-reasoning-box {
  background: var(--primary-light); border: 1px solid #bfdbfe;
  border-radius: var(--radius-sm); padding: 16px 18px; margin-bottom: 16px;
  font-size: 13px; line-height: 1.7; color: var(--text);
}
.llm-reasoning-box h1, .llm-reasoning-box h2, .llm-reasoning-box h3 {
  margin: 12px 0 6px; font-weight: 600;
}
.llm-reasoning-box h1 { font-size: 16px; }
.llm-reasoning-box h2 { font-size: 14px; }
.llm-reasoning-box h3 { font-size: 13px; }
.llm-reasoning-box p { margin: 6px 0; }
.llm-reasoning-box strong { color: var(--primary); }
.llm-reasoning-box ul, .llm-reasoning-box ol { padding-left: 18px; margin: 6px 0; }
.llm-reasoning-box code { background: #e2e8f0; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.llm-reasoning-box pre { background: #e2e8f0; padding: 10px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }

/* ===== Modal ===== */
.modal-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.4); z-index: 2000;
  align-items: center; justify-content: center;
  animation: fadeIn 0.15s ease;
}
.modal-overlay.show { display: flex; }

.modal-box {
  background: var(--surface); border-radius: var(--radius);
  box-shadow: var(--shadow-lg); width: 420px; max-width: 92vw;
  padding: 0; max-height: 90vh; overflow-y: auto;
}
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--border);
}
.modal-head h3 { font-size: 16px; font-weight: 700; }
.modal-close-btn {
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  border: none; background: #f1f5f9; border-radius: 50%; cursor: pointer;
  font-size: 14px; color: var(--text-secondary);
}
.modal-close-btn:hover { background: #e2e8f0; }

.modal-body { padding: 20px 22px; }

.form-group { margin-bottom: 14px; }
.form-group label {
  display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary);
  margin-bottom: 4px;
}
.form-group input {
  width: 100%; padding: 9px 12px; border: 1px solid var(--border);
  border-radius: 6px; font-size: 13px; font-family: inherit; color: var(--text);
  background: var(--surface); transition: border-color var(--transition);
}
.form-group input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.form-group input.error { border-color: var(--red); box-shadow: 0 0 0 3px rgba(239,68,68,0.1); }
.form-error { font-size: 12px; color: var(--red); margin-top: 4px; display: none; }
.form-error.show { display: block; }

.modal-foot {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 14px 22px; border-top: 1px solid var(--border);
}

/* ===== Overlay for detail panel ===== */
#panel-overlay {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.3);
  z-index: 999;
}
#panel-overlay.open { display: block; }

/* ===== Animations ===== */
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn 0.25s ease; }

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .app-container { padding: 16px; }
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-right { justify-content: flex-start; }
  #favorites-table { min-width: 640px; }
  .col-hide-sm { display: none; }
  #detail-panel { width: 100%; right: -100%; }
  #detail-panel.open { right: 0; }
  .modal-box { width: 100%; max-width: 100%; border-radius: 0; min-height: 100vh; }
}
@media (max-width: 480px) {
  .col-hide-xs { display: none; }
  #favorites-table { min-width: 480px; }
}
</style>
</head>
<body>
<div class="app-container">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-left">
      <h1>我的基金组合</h1>
      <div class="subtitle">持仓监控 · 实时净值 · AI 分析</div>
    </div>
    <div class="toolbar-right" id="toolbar-actions">
      <button class="btn btn-primary" id="add-btn" onclick="openAddDialog()" aria-label="添加基金">
        <span>+</span> 添加
      </button>
      <button class="btn btn-secondary" id="refresh-btn" onclick="batchRefresh()" aria-label="批量刷新行情">
        <span>&#x21bb;</span> 批量刷新
      </button>
    </div>
  </div>

  <!-- Progress Section -->
  <div id="progress-section">
    <div class="progress-header">
      <span class="progress-label" id="progress-label">批量刷新中...</span>
      <span class="progress-text" id="progress-text">0/0</span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar" id="progress-bar"></div>
    </div>
  </div>

  <!-- Empty State -->
  <div id="empty-state" class="fade-in">
    <div class="empty-icon">&#x1F4CA;</div>
    <h3>还没有自选基金</h3>
    <p>点击「+ 添加」按钮添加你的第一只基金，<br>开始跟踪持仓表现和 AI 分析建议。</p>
    <button class="btn btn-primary" onclick="openAddDialog()">+ 添加基金</button>
  </div>

  <!-- Table Card -->
  <div id="table-card" class="table-card" style="display:none;">
    <div class="table-wrap">
      <table id="favorites-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th class="col-hide-sm">买入价</th>
            <th class="col-hide-sm">持有份额</th>
            <th class="col-hide-xs col-hide-sm">买入日期</th>
            <th>当前净值</th>
            <th class="col-hide-sm">持仓市值</th>
            <th>收益率</th>
            <th class="col-hide-xs col-hide-sm">最大回撤</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="table-body">
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- Panel Overlay -->
<div id="panel-overlay" onclick="closeDetail()"></div>

<!-- Detail Panel -->
<div id="detail-panel" role="dialog" aria-label="基金分析详情">
  <div class="panel-header">
    <span class="panel-title" id="panel-title">基金详情</span>
    <button class="panel-close" onclick="closeDetail()" aria-label="关闭详情面板">&times;</button>
  </div>
  <div class="panel-loading" id="panel-loading">
    <span class="panel-spinner"></span>
    <span>加载 AI 分析中...</span>
  </div>
  <div class="panel-body" id="panel-body" style="display:none;"></div>
</div>

<!-- Add Modal -->
<div class="modal-overlay" id="add-modal" role="dialog" aria-modal="true" aria-label="添加基金">
  <div class="modal-box">
    <div class="modal-head">
      <h3>添加基金</h3>
      <button class="modal-close-btn" onclick="closeAddDialog()" aria-label="关闭">&times;</button>
    </div>
    <form id="add-form" onsubmit="submitAdd(event)">
      <div class="modal-body">
        <div class="form-group">
          <label for="f-code">基金代码</label>
          <input type="text" id="f-code" name="code" required maxlength="6" pattern="[0-9]{6}" placeholder="例如 019305" autocomplete="off">
          <div class="form-error" id="e-code"></div>
        </div>
        <div class="form-group">
          <label for="f-name">基金名称</label>
          <input type="text" id="f-name" name="name" required placeholder="例如 易方达蓝筹精选" autocomplete="off">
          <div class="form-error" id="e-name"></div>
        </div>
        <div class="form-group">
          <label for="f-buy-price">买入价（元/份）</label>
          <input type="number" id="f-buy-price" name="buy_price" required min="0.001" step="0.001" placeholder="例如 1.500" autocomplete="off">
          <div class="form-error" id="e-buy_price"></div>
        </div>
        <div class="form-group">
          <label for="f-buy-amount">持有金额（元）</label>
          <input type="number" id="f-buy-amount" name="buy_amount" required min="1" step="0.01" placeholder="例如 10000" autocomplete="off">
          <div class="form-error" id="e-buy_amount"></div>
        </div>
        <div class="form-group">
          <label for="f-buy-date">买入日期</label>
          <input type="date" id="f-buy-date" name="buy_date" required autocomplete="off">
          <div class="form-error" id="e-buy_date"></div>
        </div>
        <div class="form-error" id="e-general" style="display:none;"></div>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn btn-secondary" onclick="closeAddDialog()">取消</button>
        <button type="submit" class="btn btn-primary" id="submit-add-btn">确认添加</button>
      </div>
    </form>
  </div>
</div>

<script>
/* ===== State ===== */
let favoritesData = [];
let currentDetailCode = null;
let eventSource = null;

/* ===== Utilities ===== */
function escapeHtml(str) {
  if (str == null) return '';
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

function fmtNum(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtMoney(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return Number(n).toFixed(0);
}

function fmtPct(n) {
  if (n == null || n === '' || isNaN(n)) return '—';
  return (n * 100).toFixed(2) + '%';
}

function fmtDate(d) {
  if (!d) return '—';
  return d;
}

function statusBadge(status) {
  const labels = { ok: '正常', no_quote: '无行情', no_history: '无历史', error: '失败' };
  return '<span class="status-badge ' + status + '">' + (labels[status] || status) + '</span>';
}

/* ===== Load Favorites ===== */
async function loadFavorites() {
  const tbody = document.getElementById('table-body');
  const emptyState = document.getElementById('empty-state');
  const tableCard = document.getElementById('table-card');

  try {
    const r = await fetch('/api/favorites');
    if (!r.ok) throw new Error('请求失败: ' + r.status);
    const data = await r.json();
    favoritesData = data;

    if (!favoritesData || favoritesData.length === 0) {
      emptyState.style.display = 'block';
      tableCard.style.display = 'none';
      return;
    }

    emptyState.style.display = 'none';
    tableCard.style.display = 'block';

    let html = '';
    for (const f of favoritesData) {
      const code = escapeHtml(f.code || '');
      const name = escapeHtml(f.name || '');
      const buyPrice = f.buy_price;
      const buyAmount = f.buy_amount;
      const shares = (buyPrice && buyAmount) ? fmtNum(buyAmount / buyPrice) : '—';
      const buyDate = fmtDate(f.buy_date);
      const nav = f.current_nav;
      const value = f.current_value;
      const ret = f.return_pct;
      const dd = f.max_drawdown;
      const status = f.status || 'error';

      // Return % styling
      let retDisplay = '—';
      let retClass = 'return-nil';
      if (ret != null) {
        retDisplay = (ret >= 0 ? '+' : '') + fmtPct(ret);
        retClass = ret >= 0 ? 'return-pos' : 'return-neg';
      }

      // Max drawdown styling
      let ddDisplay = '—';
      let ddClass = 'dd-nil';
      if (dd != null) {
        ddDisplay = '-' + fmtPct(Math.abs(dd));
        const absDd = Math.abs(dd);
        ddClass = absDd <= 0.10 ? 'dd-low' : (absDd <= 0.20 ? 'dd-mid' : 'dd-high');
      }

      html += '<tr data-code="' + code + '">';
      html += '<td class="col-code">' + code + '</td>';
      html += '<td class="col-name" title="' + name + '">' + name + '</td>';
      html += '<td class="col-num col-hide-sm">' + fmtNum(buyPrice) + '</td>';
      html += '<td class="col-num col-hide-sm">' + shares + '</td>';
      html += '<td class="col-date col-hide-xs col-hide-sm">' + buyDate + '</td>';
      html += '<td class="col-num">' + fmtNum(nav) + '</td>';
      html += '<td class="col-num col-hide-sm">' + fmtMoney(value) + '</td>';
      html += '<td class="col-num ' + retClass + '">' + retDisplay + '</td>';
      html += '<td class="col-num ' + ddClass + ' col-hide-xs col-hide-sm">' + ddDisplay + '</td>';
      html += '<td>' + statusBadge(status) + '</td>';
      html += '<td class="col-actions">';
      html += '<button class="btn btn-sm btn-secondary" onclick="openDetail(\'' + code + '\')" aria-label="查看详情" style="margin-right:4px;">详情</button>';
      html += '<button class="btn btn-sm btn-danger" onclick="deleteFavorite(\'' + code + '\', this)" aria-label="删除基金">删除</button>';
      html += '</td>';
      html += '</tr>';
    }
    tbody.innerHTML = html;

    // Update progress if need to re-show
    updateProgressAfterRefresh();
  } catch (e) {
    emptyState.style.display = 'block';
    emptyState.innerHTML = '<div class="empty-icon">&#x26A0;&#xFE0F;</div>'
      + '<h3>加载失败</h3><p>' + escapeHtml(e.message) + '</p>'
      + '<button class="btn btn-primary" onclick="loadFavorites()">重试</button>';
    tableCard.style.display = 'none';
  }
}

/* ===== Batch Refresh (SSE) ===== */
function batchRefresh() {
  const btn = document.getElementById('refresh-btn');
  const section = document.getElementById('progress-section');
  const bar = document.getElementById('progress-bar');
  const label = document.getElementById('progress-label');
  const text = document.getElementById('progress-text');

  if (btn.disabled) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="panel-spinner" style="width:14px;height:14px;border-width:2px;margin:0;"></span> 刷新中';

  // Show progress section immediately with a connecting state
  section.style.display = 'block';
  bar.style.width = '5%';
  label.textContent = '连接中...';
  text.textContent = '';

  // Close any existing EventSource
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  // Use EventSource to connect to SSE endpoint
  const es = new EventSource('/api/favorites/refresh');
  eventSource = es;

  let total = 0;
  let progressCount = 0;
  let okCount = 0;
  let failCount = 0;

  es.onmessage = function(e) {
    let event;
    try {
      event = JSON.parse(e.data);
    } catch (err) {
      console.warn('SSE parse error', err);
      return;
    }

    if (event.event === 'start') {
      total = event.total || 0;
      progressCount = 0;
      okCount = 0;
      failCount = 0;
      if (total === 0) {
        label.textContent = '没有基金需要刷新';
        text.textContent = '0/0';
        bar.style.width = '100%';
        finishRefresh(btn, es);
        return;
      }
      label.textContent = '正在刷新基金行情';
      text.textContent = '0/' + total;
      bar.style.width = '0%';
    }
    else if (event.event === 'progress') {
      progressCount++;
      if (event.ok) okCount++;
      if (event.fail) failCount++;
      const pct = total > 0 ? Math.round((progressCount / total) * 100) : 0;
      bar.style.width = Math.min(pct, 100) + '%';
      text.textContent = progressCount + '/' + total + ' (ok: ' + okCount + ', fail: ' + failCount + ')';
    }
    else if (event.event === 'keep-alive') {
      // Heartbeat, do nothing
    }
    else if (event.event === 'done') {
      okCount = event.ok || 0;
      failCount = event.fail || 0;
      bar.style.width = '100%';
      text.textContent = '完成 — ok: ' + okCount + ', fail: ' + failCount;
      label.textContent = '批量刷新完成';
      if (failCount > 0) {
        label.textContent = '刷新完成（部分失败）';
      }
      finishRefresh(btn, es);
      // Reload table to show latest data
      loadFavorites();
    }
    else if (event.event === 'error' && event.code === 'batch_in_progress') {
      label.textContent = '已有刷新任务进行中';
      text.textContent = '请稍后重试';
      bar.style.width = '100%';
      finishRefresh(btn, es);
    }
  };

  es.onerror = function() {
    label.textContent = '刷新中断，请重试';
    text.textContent = '连接异常';
    bar.style.width = '100%';
    section.style.display = 'block';
    finishRefresh(btn, es);
  };
}

function finishRefresh(btn, es) {
  if (es) { es.close(); }
  if (eventSource === es) { eventSource = null; }
  btn.disabled = false;
  btn.innerHTML = '&#x21bb; 批量刷新';

  // Auto-hide progress bar after 5 seconds
  setTimeout(function() {
    const section = document.getElementById('progress-section');
    if (section) {
      section.style.display = 'none';
    }
  }, 5000);
}

function updateProgressAfterRefresh() {
  // Clean up any stale progress state
  const section = document.getElementById('progress-section');
  if (section && !section.querySelector('.progress-header')) {
    // already clean
  }
}

/* ===== Add Dialog ===== */
function openAddDialog() {
  const modal = document.getElementById('add-modal');
  const form = document.getElementById('add-form');
  form.reset();
  // Set default date to today
  document.getElementById('f-buy-date').value = new Date().toISOString().split('T')[0];
  // Clear all errors
  document.querySelectorAll('.form-error').forEach(function(el) {
    el.classList.remove('show');
    el.textContent = '';
  });
  document.querySelectorAll('.form-group input').forEach(function(el) {
    el.classList.remove('error');
  });
  document.getElementById('e-general').style.display = 'none';
  modal.classList.add('show');
  document.getElementById('f-code').focus();
}

function closeAddDialog() {
  document.getElementById('add-modal').classList.remove('show');
}

async function submitAdd(event) {
  event.preventDefault();
  const form = event.target;
  const btn = document.getElementById('submit-add-btn');
  const fd = new FormData(form);

  // Clear previous errors
  document.querySelectorAll('.form-error').forEach(function(el) {
    el.classList.remove('show');
    el.textContent = '';
  });
  document.querySelectorAll('.form-group input').forEach(function(el) {
    el.classList.remove('error');
  });
  document.getElementById('e-general').style.display = 'none';

  btn.disabled = true;
  btn.textContent = '提交中...';

  try {
    const r = await fetch('/api/favorites', { method: 'POST', body: fd });
    if (r.status === 201) {
      closeAddDialog();
      await loadFavorites();
    } else if (r.status === 422) {
      const err = await r.json();
      const detail = err.detail || {};
      if (detail.field && detail.msg) {
        // Field-level error
        const fieldEl = document.getElementById('e-' + detail.field);
        const inputEl = document.getElementById('f-' + detail.field);
        if (fieldEl) {
          fieldEl.textContent = detail.msg;
          fieldEl.classList.add('show');
        }
        if (inputEl) {
          inputEl.classList.add('error');
          inputEl.focus();
        }
      } else {
        // General error
        const msg = typeof detail === 'string' ? detail : (detail.msg || JSON.stringify(detail));
        const genEl = document.getElementById('e-general');
        genEl.textContent = msg;
        genEl.style.display = 'block';
      }
    } else if (r.status === 409) {
      // Duplicate code (or refresh conflict)
      const err = await r.json();
      const genEl = document.getElementById('e-general');
      genEl.textContent = err.detail || '该基金已在自选列表中';
      genEl.style.display = 'block';
    } else {
      const err = await r.json().catch(function() { return {}; });
      const genEl = document.getElementById('e-general');
      genEl.textContent = err.detail || '提交失败，请重试 (状态码: ' + r.status + ')';
      genEl.style.display = 'block';
    }
  } catch (e) {
    const genEl = document.getElementById('e-general');
    genEl.textContent = '网络错误: ' + e.message;
    genEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '确认添加';
  }
}

/* ===== Detail Panel ===== */
async function openDetail(code) {
  currentDetailCode = code;
  const panel = document.getElementById('detail-panel');
  const overlay = document.getElementById('panel-overlay');
  const loading = document.getElementById('panel-loading');
  const body = document.getElementById('panel-body');
  const title = document.getElementById('panel-title');

  // Find name from data
  let name = '';
  for (const f of favoritesData) {
    if (f.code === code) {
      name = f.name || '';
      break;
    }
  }

  title.textContent = code + ' ' + name;
  loading.style.display = 'flex';
  body.style.display = 'none';
  body.innerHTML = '';
  panel.classList.add('open');
  overlay.classList.add('open');

  try {
    const fd = new URLSearchParams();
    fd.append('codes', code);
    fd.append('months', '24');
    fd.append('reasoning', '1');
    fd.append('use_llm', '1');
    fd.append('backtest', '0');

    const r = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: fd.toString(),
    });
    const data = await r.json();

    if (!r.ok || data.error) {
      throw new Error(data.error || data.detail || '分析失败 (状态码: ' + r.status + ')');
    }

    loading.style.display = 'none';
    body.style.display = 'block';
    body.innerHTML = renderAnalysis(data, code);
  } catch (e) {
    loading.style.display = 'none';
    body.style.display = 'block';
    body.innerHTML = '<div style="text-align:center;padding:30px;color:#ef4444;">'
      + '<p style="font-size:16px;font-weight:600;margin-bottom:8px;">加载分析失败</p>'
      + '<p style="font-size:13px;color:#64748b;">' + escapeHtml(e.message) + '</p>'
      + '<button class="btn btn-primary" style="margin-top:16px;" onclick="openDetail(\'' + code + '\')">重试</button>'
      + '</div>';
  }
}

function closeDetail() {
  const panel = document.getElementById('detail-panel');
  const overlay = document.getElementById('panel-overlay');
  panel.classList.remove('open');
  overlay.classList.remove('open');
  currentDetailCode = null;
  // Markdown content may contain scripts from marked - safe since we only render LLM output
  document.getElementById('panel-body').innerHTML = '';
  document.getElementById('panel-title').textContent = '基金详情';
}

function renderAnalysis(data, targetCode) {
  const fund = data[targetCode];
  if (!fund) {
    // Try to find the first (and only) key
    const keys = Object.keys(data).filter(function(k) { return k !== '_record_id'; });
    if (keys.length > 0) {
      return renderAnalysis(data, keys[0]);
    }
    return '<p style="color:var(--text-muted);">无分析数据</p>';
  }

  const summary = fund.summary || {};
  const agents = fund.agents || {};
  const signal = summary.final_signal || 'neutral';
  const score = summary.score || 50;
  const confidence = summary.confidence || 0;
  const agentKeys = Object.keys(agents);

  const signalLabels = { bullish: '看多', neutral: '中性', bearish: '看空' };

  let html = '';

  // Signal card
  html += '<div class="panel-signal ' + signal + '">';
  html += '<span class="signal-dot"></span>';
  html += '<span class="signal-label">' + signalLabels[signal] + '</span>';
  html += '<div style="text-align:right;">';
  html += '<div class="signal-score">' + score + '</div>';
  html += '<div class="signal-conf">置信度 ' + confidence + '%</div>';
  html += '</div></div>';

  // LLM reasoning (markdown rendered)
  if (agents.llm && agents.llm.reasoning) {
    const llmReasoning = agents.llm.reasoning;
    try {
      if (typeof marked !== 'undefined' && marked.parse) {
        html += '<div class="llm-reasoning-box">' + marked.parse(llmReasoning) + '</div>';
      } else {
        // Fallback: simple markdown-like rendering
        html += '<div class="llm-reasoning-box"><pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;">' + escapeHtml(llmReasoning) + '</pre></div>';
      }
    } catch (e) {
      html += '<div class="llm-reasoning-box"><pre style="white-space:pre-wrap;">' + escapeHtml(llmReasoning) + '</pre></div>';
    }
  }

  // Agent scores summary bar
  if (summary.total_agents != null) {
    html += '<div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;">';
    html += '看多 ' + (summary.bullish_agents || 0) + ' · 看空 ' + (summary.bearish_agents || 0);
    html += ' · 共 ' + summary.total_agents + ' Agent';
    html += '</div>';
  }

  // Agent cards
  for (const key of agentKeys) {
    const a = agents[key];
    if (!a) continue;
    const aSignal = a.signal || 'neutral';
    const aScore = a.score || 0;
    const hasReasoning = a.reasoning && typeof a.reasoning === 'string' && a.reasoning.trim();

    html += '<div class="panel-agent-card" onclick="toggleAgentReasoning(this)"';
    if (hasReasoning) { html += ' style="cursor:pointer;"'; }
    html += '>';
    html += '<div class="agent-head">';
    html += '<span class="agent-name">' + escapeHtml(agentLabel(key)) + '</span>';
    html += '<div style="display:flex;align-items:center;gap:8px;">';
    html += '<span class="agent-signal ' + aSignal + '">' + signalLabels[aSignal] + '</span>';
    html += '<span class="agent-score">' + aScore + '</span>';
    if (hasReasoning) {
      html += '<span style="font-size:10px;color:var(--text-muted);">&#x25BC;</span>';
    }
    html += '</div></div>';
    if (hasReasoning) {
      html += '<div class="agent-reasoning">' + escapeHtml(a.reasoning) + '</div>';
    }
    html += '</div>';
  }

  return html;
}

function toggleAgentReasoning(card) {
  card.classList.toggle('expanded');
}

function agentLabel(key) {
  const map = { trend: '趋势分析', risk: '风险分析', manager: '经理分析', valuation: '估值分析', peer: '同类对比', llm: 'LLM 研判', holdings: '持仓分析' };
  return map[key] || key;
}

/* ===== Delete Favorite ===== */
async function deleteFavorite(code, btn) {
  if (!confirm('确定删除基金 ' + code + ' 吗？')) return;

  btn.disabled = true;
  btn.textContent = '...';

  try {
    const r = await fetch('/api/favorites/' + encodeURIComponent(code), { method: 'DELETE' });
    if (!r.ok) {
      const err = await r.json().catch(function() { return {}; });
      alert('删除失败: ' + (err.detail || '未知错误'));
    }
    await loadFavorites();
  } catch (e) {
    alert('删除失败: ' + e.message);
    btn.disabled = false;
    btn.textContent = '删除';
  }
}

/* ===== Keyboard ===== */
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeDetail();
    if (document.getElementById('add-modal').classList.contains('show')) {
      closeAddDialog();
    }
  }
});

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', loadFavorites);
</script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def index():
    return HTML
