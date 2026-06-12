# T8: Playwright UI Scenarios S8-S9

## Evidence: Test Run Output

```
Running 4 tests using 1 worker

  ✓  1 tests/qa/portfolio-watchlist/scenarios/08-table-render.spec.ts:85:5 › S8-T1: 页面标题显示"我的基金组合" (923ms)
  ✓  2 tests/qa/portfolio-watchlist/scenarios/08-table-render.spec.ts:95:5 › S8-T2: 添加基金后表格渲染 1 行 9 个数据格 (1.9s)
  ✓  3 tests/qa/portfolio-watchlist/scenarios/09-slideout-panel.spec.ts:86:5 › S9-T1: 点击详情按钮打开滑出面板并显示分析内容 (2.8s)
  ✓  4 tests/qa/portfolio-watchlist/scenarios/09-slideout-panel.spec.ts:125:5 › S9-T2: 按 Esc 键关闭滑出面板 (1.8s)

  4 passed (9.2s)
```

## Files Created

| # | File | Lines | Description |
|---|------|-------|-------------|
| 1 | `tests/qa/portfolio-watchlist/scenarios/08-table-render.spec.ts` | 120 | S8: Title check + API add + table 9-column render + header count |
| 2 | `tests/qa/portfolio-watchlist/scenarios/09-slideout-panel.spec.ts` | 161 | S9: Detail panel open with .open class + Escape key close |

## Test Details

- **S8-T1**: GET `/` returns 200, `<h1>` contains "我的基金组合"
- **S8-T2**: POST `/api/favorites` (code=019305, name=测试基金, buy_price=1.5, buy_amount=10000, buy_date=2025-01-15) → 201, then GET `/` → table has 1 row, 9 data td cells visible, 11 header columns
- **S9-T1**: Same add flow, click "详情" button (aria-label="查看详情"), wait 500ms → `#detail-panel` has `.open` class, `#panel-body` populated from POST `/analyze`
- **S9-T2**: After panel opens, press Escape → `#detail-panel` loses `.open` class

## Configuration

- Port: 8766 (T7 uses 8765, no conflict)
- Database: `/tmp/ai-fund-test-8766.db` (temp file, cleaned in afterAll, `:memory:` incompatible with multi-request flow)
- Playwright version: latest from `@playwright/test`
- Chromium browser: installed from global cache
- Runner: `--workers=1` (both files share port 8766)
