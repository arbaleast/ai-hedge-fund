/**
 * S9: Slide-Out Panel — Verify the detail slide-out panel opens and closes
 *
 * GIVEN: uvicorn running, 1 favorite in DB
 * WHEN:  Click "详情" button on the row
 * THEN:  #detail-panel gets .open class, panel body loads POST /analyze content
 * WHEN:  Press Escape key
 * THEN:  #detail-panel loses .open class
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
// S9-T1: Open detail panel and verify content
// ──────────────────────────────────────────────
test('S9-T1: 点击详情按钮打开滑出面板并显示分析内容', async ({ page }) => {
  // Add a mock favorite via API
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

  // Navigate to home page and wait for table
  await page.goto(BASE + '/');
  await page.waitForSelector('#favorites-table tbody tr', { timeout: 10000 });

  // Click "详情" button (aria-label="查看详情")
  await page.getByRole('button', { name: '查看详情' }).click();

  // Wait 500ms for the slide-out animation (CSS transition: right 0.3s ease)
  await page.waitForTimeout(500);

  // Verify #detail-panel has the .open class
  const panel = page.locator('#detail-panel');
  await expect(panel).toHaveClass(/open/);

  // Wait for POST /analyze response to populate the panel body
  // The panel-body starts hidden (display:none) and becomes visible once content loads.
  // Allow up to 20s since /analyze may involve LLM calls that timeout or fail gracefully.
  await expect(async () => {
    const bodyHtml = await page.locator('#panel-body').innerHTML();
    expect(bodyHtml.trim()).not.toBe('');
  }).toPass({ timeout: 20000, intervals: [500] });
});

// ──────────────────────────────────────────────
// S9-T2: Close detail panel with Escape key
// ──────────────────────────────────────────────
test('S9-T2: 按 Esc 键关闭滑出面板', async ({ page }) => {
  // Add a mock favorite via API
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

  // Navigate and open panel
  await page.goto(BASE + '/');
  await page.waitForSelector('#favorites-table tbody tr', { timeout: 10000 });
  await page.getByRole('button', { name: '查看详情' }).click();

  // Wait for slide-in animation
  await page.waitForTimeout(500);

  // Confirm panel is open
  const panel = page.locator('#detail-panel');
  await expect(panel).toHaveClass(/open/);

  // Press Escape to close
  await page.keyboard.press('Escape');

  // Wait for slide-out transition
  await page.waitForTimeout(400);

  // Verify panel no longer has .open class
  await expect(panel).not.toHaveClass(/open/);
});
