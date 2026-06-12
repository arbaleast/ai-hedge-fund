"""SQLite 持久化 — 基金分析历史记录"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional


DB_PATH = os.environ.get("AI_FUND_DB", "/data/ai_fund.db")


def _ensure_dir():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def get_conn():
    """获取数据库连接（自动建表）"""
    _ensure_dir()
    is_new = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if is_new:
            _init_schema(conn)
        else:
            # 检查表是否存在
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis'"
            )
            if not cur.fetchone():
                _init_schema(conn)
        _migrate_favorites(conn)
        yield conn
    finally:
        conn.commit()
        conn.close()


def _init_schema(conn: sqlite3.Connection):
    """初始化数据库结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            codes TEXT NOT NULL,
            months INTEGER,
            use_llm INTEGER DEFAULT 0,
            backtest INTEGER DEFAULT 0,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_ts ON analysis(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_codes ON analysis(codes);

        CREATE TABLE IF NOT EXISTS fund_favorites (
            code TEXT PRIMARY KEY,
            name TEXT,
            note TEXT,
            added_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)


def _migrate_favorites(conn: sqlite3.Connection):
    """幂等迁移 fund_favorites 表 — 安全多次调用"""
    new_columns = {
        "buy_price": "REAL",
        "buy_amount": "REAL",
        "buy_date": "TEXT",
    }
    for col, typ in new_columns.items():
        try:
            conn.execute(f"ALTER TABLE fund_favorites ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                raise
    conn.commit()


def save_analysis(
    codes: list[str],
    result: dict,
    months: int = 24,
    use_llm: bool = False,
    backtest: bool = False,
) -> int:
    """保存一次分析记录 — 返回记录 ID"""
    ts = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO analysis (ts, codes, months, use_llm, backtest, result_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ts,
                ",".join(codes),
                months,
                1 if use_llm else 0,
                1 if backtest else 0,
                json.dumps(result, ensure_ascii=False, default=str),
            ),
        )
        return int(cur.lastrowid) if cur.lastrowid else 0


def list_history(limit: int = 30) -> list[dict]:
    """列出最近的分析记录"""
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT id, ts, codes, months, use_llm, backtest, created_at
               FROM analysis ORDER BY ts DESC LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "ts": r["ts"],
                "datetime": datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M"),
                "codes": r["codes"],
                "months": r["months"],
                "use_llm": bool(r["use_llm"]),
                "backtest": bool(r["backtest"]),
            })
        return results


def get_analysis(record_id: int) -> Optional[dict]:
    """获取某次分析的完整结果"""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT result_json FROM analysis WHERE id = ?",
            (record_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return json.loads(row["result_json"])


def add_favorite(code: str, name: str, buy_price: float, buy_amount: float, buy_date: str, note: str = ""):
    """添加关注 (5 字段必填, app-layer 校验)"""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO fund_favorites (code, name, note, buy_price, buy_amount, buy_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, name, note, buy_price, buy_amount, buy_date),
        )


def put_favorite(
    code: str,
    name: str | None = None,
    buy_price: float | None = None,
    buy_amount: float | None = None,
    buy_date: str | None = None,
    note: str | None = None,
):
    """更新关注基金 (部分字段更新, None 保留原值)"""
    with get_conn() as conn:
        conn.execute(
            """UPDATE fund_favorites SET
                   name = COALESCE(?, name),
                   buy_price = COALESCE(?, buy_price),
                   buy_amount = COALESCE(?, buy_amount),
                   buy_date = COALESCE(?, buy_date),
                   note = COALESCE(?, note)
               WHERE code = ?""",
            (name, buy_price, buy_amount, buy_date, note, code),
        )


def remove_favorite(code: str):
    """取消关注"""
    with get_conn() as conn:
        conn.execute("DELETE FROM fund_favorites WHERE code = ?", (code,))


def list_favorites() -> list[dict]:
    """列出关注的基金"""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT code, name, note, buy_price, buy_amount, buy_date, added_at FROM fund_favorites ORDER BY added_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]
