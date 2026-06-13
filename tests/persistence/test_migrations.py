"""Schema migration idempotency + CRUD roundtrip tests"""

import os
import sqlite3
import tempfile

import pytest

from app.persistence import (
    DB_PATH,
    ensure_schema,
    get_conn,
    save_nav_history,
    get_nav_history,
    list_nav_history,
    update_nav_history,
    save_analysis_cache,
    get_analysis_cache,
    list_analysis_cache,
    update_analysis_cache,
)


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch):
    """每个测试使用独立的临时数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("AI_FUND_DB", tmp.name)
    # 刷新模块级 DB_PATH
    import importlib
    import app.persistence
    importlib.reload(app.persistence)
    yield
    os.unlink(tmp.name)


def _get_raw_conn() -> sqlite3.Connection:
    """直连数据库（不走 get_conn 的自动建表）"""
    conn = sqlite3.connect(os.environ["AI_FUND_DB"])
    conn.row_factory = sqlite3.Row
    return conn


class TestEnsureSchema:
    """ensure_schema 幂等性验证"""

    def test_idempotent_double_call(self):
        """连续调用两次 ensure_schema 不应报错"""
        conn = _get_raw_conn()
        try:
            # 第一次
            ensure_schema(conn)

            # 验证表存在
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            names = {r["name"] for r in tables}
            assert "fund_nav_history" in names
            assert "analysis_cache" in names

            # 第二次 — 不应抛异常
            ensure_schema(conn)

            # 表结构正确: 主键
            pk_info = conn.execute(
                "SELECT l.name FROM pragma_table_info('fund_nav_history') AS l "
                "JOIN pragma_table_xinfo('fund_nav_history') AS x ON l.cid = x.cid "
                "WHERE x.pk > 0"
            ).fetchall()
            pk_names = {r["name"] for r in pk_info}
            # sqlite3 复合主键通过 pragma_table_xinfo.pk 体现
            pks = conn.execute(
                "SELECT name FROM pragma_table_info('fund_nav_history') WHERE pk > 0"
            ).fetchall()
            assert len(pks) == 2, "fund_nav_history 应有复合主键 (code, date)"

            pks_c = conn.execute(
                "SELECT name FROM pragma_table_info('analysis_cache') WHERE pk > 0"
            ).fetchall()
            assert len(pks_c) == 2, "analysis_cache 应有复合主键 (code, window)"
        finally:
            conn.close()


class TestNavHistory:
    """fund_nav_history CRUD 往返测试"""

    def test_save_and_get(self):
        """保存 NAV 后应能完整读回"""
        save_nav_history(
            code="000001",
            date="2025-01-10",
            nav=1.2345,
            accumulated_nav=1.6789,
            source="eastmoney",
            fetched_at="2025-01-10 15:00:00",
        )
        row = get_nav_history("000001", "2025-01-10")
        assert row is not None
        assert row["code"] == "000001"
        assert row["date"] == "2025-01-10"
        assert row["nav"] == 1.2345
        assert row["accumulated_nav"] == 1.6789
        assert row["source"] == "eastmoney"
        assert row["fetched_at"] == "2025-01-10 15:00:00"

    def test_replace_on_duplicate(self):
        """相同 primary key 应覆盖旧记录"""
        save_nav_history("000001", "2025-01-10", 1.1, 1.2)
        save_nav_history("000001", "2025-01-10", 2.2, 2.3)
        rows = list_nav_history("000001")
        assert len(rows) == 1  # 只有一条记录
        assert rows[0]["nav"] == 2.2

    def test_list_ordered(self):
        """list_nav_history 应按日期降序排列"""
        dates = ["2025-01-03", "2025-01-01", "2025-01-02"]
        for d in dates:
            save_nav_history("000001", d, 1.0, 1.0)
        rows = list_nav_history("000001")
        assert [r["date"] for r in rows] == [
            "2025-01-03", "2025-01-02", "2025-01-01"
        ]

    def test_update_partial(self):
        """update_nav_history 仅更新指定字段"""
        save_nav_history("000001", "2025-01-10", 1.0, 1.0, source="a")
        update_nav_history("000001", "2025-01-10", nav=2.0)
        row = get_nav_history("000001", "2025-01-10")
        assert row["nav"] == 2.0
        assert row["accumulated_nav"] == 1.0  # 未改动
        assert row["source"] == "a"  # 未改动


class TestAnalysisCache:
    """analysis_cache CRUD 往返测试"""

    def test_save_and_get(self):
        """保存缓存后应能按 (code, window) 完整读回"""
        save_analysis_cache(
            code="000001",
            window="24m",
            metrics_json='{"trend": "up", "score": 85}',
            computed_at="2025-01-10 12:00:00",
        )
        row = get_analysis_cache("000001", "24m")
        assert row is not None
        assert row["code"] == "000001"
        assert row["window"] == "24m"
        assert row["computed_at"] == "2025-01-10 12:00:00"
        import json
        data = json.loads(row["metrics_json"])
        assert data["trend"] == "up"
        assert data["score"] == 85

    def test_replace_on_duplicate(self):
        """相同 primary key 应覆盖"""
        save_analysis_cache("000001", "24m", '{"v": 1}')
        save_analysis_cache("000001", "24m", '{"v": 2}')
        rows = list_analysis_cache("000001")
        assert len(rows) == 1
        import json
        assert json.loads(rows[0]["metrics_json"])["v"] == 2

    def test_list_filter_by_code(self):
        """list_analysis_cache 可按 code 过滤"""
        save_analysis_cache("A", "24m", '{}')
        save_analysis_cache("B", "24m", '{}')
        rows_a = list_analysis_cache("A")
        assert len(rows_a) == 1
        assert rows_a[0]["code"] == "A"
        rows_all = list_analysis_cache()
        assert len(rows_all) == 2

    def test_update_partial(self):
        """update_analysis_cache 仅更新指定字段"""
        save_analysis_cache("000001", "24m", '{"v": 1}', computed_at="old")
        update_analysis_cache("000001", "24m", metrics_json='{"v": 99}')
        row = get_analysis_cache("000001", "24m")
        import json
        assert json.loads(row["metrics_json"])["v"] == 99
        assert row["computed_at"] == "old"  # 未改动
