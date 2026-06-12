/**
 * S8: UI Table Render — Verify the portfolio table renders correctly
 *
 * GIVEN: uvicorn running with an empty in-memory DB
 * WHEN:  POST /api/favorites with 5 fields, then GET /
 * THEN:  page title shows "我的基金组合", table has 1 row with 9 data columns + header
 */

import { test, expect } from '@playwright/test';
import { spawn, type ChildProcess } from 'child_process';
import * as net from 'net';
import * as fs from 'fs';

const PORT = 8766;
const BASE = `http://localhost:${PORT}`;
const TEST_DB = '/tmp/ai-fund-test-8766.db';

let server: ChildProcess | null = null;

/** Wait until TCP port is accepting connections */
async function waitForPort(port: number, timeoutMs = 30000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await new Promise<void>((resolve, reject) => {
        const sock = net.createConnection(port, '127.0.0.1', () => {
          sock.destroy();
          resolve();
        });
        sock.once('error', reject);
        sock.setTimeout(1000);
        sock.once('timeout', () => {
          sock.destroy();
          reject(new Error('connect timeout'));
        });
      });
      return;
    } catch {
      await new Promise(r => setTimeout(r, 300));
    }
  }
  throw new Error(`Port ${port} not ready after ${timeoutMs}ms`);
}

/** Remove a file if it exists (ignore errors) */
function rmSilent(p: string) {
  try { fs.unlinkSync(p); } catch { /* ok */ }
}

test.beforeAll(async () => {
  // Clean up stale test DB from previous runs
  rmSilent(TEST_DB);
  rmSilent(TEST_DB + '-wal');
  rmSilent(TEST_DB + '-shm');

  server = spawn(
    'uvicorn', ['app.web:app', '--port', String(PORT), '--log-level', 'warning'],
    {
      cwd: '/home/al/workspace/ai-hedge-fund',
      env: { ...process.env, AI_FUND_DB: TEST_DB },
      stdio: 'pipe',
    },
  );

  // Drain stdout/stderr to prevent backpressure hangs
  if (server.stdout) server.stdout.on('data', () => {});
  if (server.stderr) server.stderr.on('data', () => {});

  await waitForPort(PORT);
});

test.afterAll(async () => {
  if (server) {
    server.kill('SIGTERM');
    server = null;
  }
  rmSilent(TEST_DB);
  rmSilent(TEST_DB + '-wal');
  rmSilent(TEST_DB + '-shm');
});

// ──────────────────────────────────────────────
// S8-T1: Page loads with correct title
// ──────────────────────────────────────────────
test('S8-T1: 页面标题显示"我的基金组合"', async ({ page }) => {
  const resp = await page.goto(BASE + '/');
  expect(resp?.status()).toBe(200);
  await expect(page.locator('h1')).toHaveText('我的基金组合');
});

// ──────────────────────────────────────────────
// S8-T2: Add a fund via API, verify table renders
//       with 1 row and 9 data columns
// ──────────────────────────────────────────────
test('S8-T2: 添加基金后表格渲染 1 行 9 个数据格', async ({ page }) => {
  // POST a mock favorite with all 5 required fields
  const addResp = await page.request.post(BASE + '/api/favorites', {
    form: {
      code: '019305',
      name: '测试基金',
      buy_price: '1.500',
      buy_amount: '10000',
      buy_date: '2025-01-15',
    },
  });
  expect(addResp.status()).toBe(201);

  // Navigate to home page and wait for table to render
  await page.goto(BASE + '/');
  await page.waitForSelector('#favorites-table tbody tr', { timeout: 10000 });

  // Verify exactly 1 row in table body
  const rows = page.locator('#favorites-table tbody tr');
  await expect(rows).toHaveCount(1);

  // Verify 9 data columns exist in the row
  const cells = rows.locator('td');

  // 1 — code
  await expect(cells.nth(0)).toHaveText('019305');
  // 2 — name
  await expect(cells.nth(1)).toHaveText('测试基金');
  // 3 — buy_price
  await expect(cells.nth(2)).toBeVisible();
  // 4 — buy_amount / shares
  await expect(cells.nth(3)).toBeVisible();
  // 5 — buy_date
  await expect(cells.nth(4)).toBeVisible();
  // 6 — current_nav
  await expect(cells.nth(5)).toBeVisible();
  // 7 — current_value
  await expect(cells.nth(6)).toBeVisible();
  // 8 — return_pct
  await expect(cells.nth(7)).toBeVisible();
  // 9 — max_drawdown
  await expect(cells.nth(8)).toBeVisible();

  // Verify table header has 11 columns
  const headers = page.locator('#favorites-table thead th');
  await expect(headers).toHaveCount(11);
});
