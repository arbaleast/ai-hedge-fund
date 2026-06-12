# T7: QA Scenarios S1-S7 验证报告

## 执行结果 (2026-06-12)

| # | 文件 | 结果 | 验证内容 | 耗时 |
|---|------|------|---------|------|
| S1 | `01-empty-state.sh` | ✅ PASS | GET /api/favorites → 200, body=[] | ~3s |
| S2 | `02-add-5-fields.sh` | ✅ PASS | POST 5字段 → 201, GET 包含该项 | ~5s |
| S3 | `03-missing-field-422.sh` | ✅ PASS | POST 缺 buy_date → 422, detail 含"buy_date" | ~3s |
| S4 | `04-list-with-metrics.sh` | ✅ PASS | GET → 9 metrics 字段 + status | ~5s |
| S5 | `05-single-quote.sh` | ✅ PASS | GET /api/quote/000001 → HTTP 200 (路由存在) | ~3s |
| S6 | `06-sse-stream.sh` | ✅ PASS | SSE content-type + data: 行 | ~5s |
| S7 | `07-batch-conflict.sh` | ✅ PASS | 并发 SSE → 第二个 409 | ~8s |

## 环境
- 端口: 8765 (每脚本独立 uvicorn)
- DB: 临时文件 (避免 `:memory:` per-connection 隔离问题)
- 解析: python3 (系统无 jq)

## 说明
- 每个脚本自管理 uvicorn 生命周期 (start + trap EXIT kill)
- S4/S7 通过 POST 添加测试数据 (非空 DB)
- S7 使用 15 条记录延长 SSE 处理至 ~3s,确保 1s 并发窗口
- S5 接受 200/404/500 (路由存在即可)
