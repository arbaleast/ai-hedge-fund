# AI 基金分析系统 (ai-fund)

基于 LangGraph 的多 agent 基金分析平台。七个分析 agent 并行工作,
对开放式基金做趋势 / 风险 / 经理 / 估值 / 同类对比 / 持仓 / LLM 综合研判,
由 manager agent 汇总,生成可操作的买/卖/持有建议。

仅供学习研究,不构成投资建议。

## 特性

- **7 个分析 agent** 协同工作 (见下)
- **LangGraph 编排** 状态机驱动,断点续跑
- **回测引擎** 独立模块,SMA / 趋势跟踪两种策略
- **Web 界面** FastAPI + Jinja2 模板,无前后端分离
- **SQLite 持久化** 每次分析自动入库,可在 `/api/history` 拉取
- **新-api 网关** 通过 [new-api](https://github.com/songquanpeng/one-api) 兼容
  OpenAI 协议,支持 deepseek / gpt-4o / claude 等任意上游模型

## 分析 Agent

| Agent | 角色 | 关注点 |
|---|---|---|
| `trend_agent` | 趋势分析 | 净值走势、均线、动量 |
| `risk_agent` | 风险分析 | 波动率、回撤、夏普 |
| `manager_agent` | 经理画像 | 在管时长、任期回报、规模 |
| `fund_valuation_agent` | 估值分析 | 净值高低估、PE/PB 偏离 |
| `peer_agent` | 同类对比 | 同类基金排名、Alpha |
| `holdings_agent` | 持仓分析 | 前十大重仓、行业分布 |
| `llm_agent` | LLM 综合研判 | 自由文本推理 (调用 new-api) |
| `manager_agent` | 汇总 | 综合多 agent 输出,给出最终信号 |

## 快速开始

### 1. 配置环境

```bash
cp .env.example .env
# 编辑 .env,填入 new-api 凭据
```

```dotenv
NEW_API_KEY=sk-xxx
NEW_API_BASE=https://api.your-new-api.com/v1
NEW_API_MODEL=deepseek-v4-flash
```

### 2. 启动 (本地)

```bash
./run.sh
# 浏览器打开 http://localhost:8080
```

`run.sh` 会自动:
- 检测 `.env` (缺失则提示)
- 安装依赖 (Poetry)
- 准备 `./data/` 目录
- 启动 uvicorn 监听 0.0.0.0:8080

### 3. 启动 (Docker)

```bash
docker-compose up --build
# 同样 http://localhost:8080
```

## API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | Web 界面 |
| `/docs` | GET | FastAPI Swagger |
| `/api/analyze` | POST | 触发一次分析 |
| `/api/history` | GET | 历史分析记录 (JSON) |
| `/api/funds/{code}` | GET | 基金基本信息 |

`/api/analyze` 请求体示例:

```json
{
  "fund_codes": ["000001", "161725"],
  "months": 24,
  "show_reasoning": true,
  "selected_agents": ["trend", "risk", "manager", "llm"]
}
```

## 项目结构

```
.
├── app/                       # FastAPI Web 应用
│   ├── web.py                 #   入口 (uvicorn app.web:app)
│   ├── persistence.py         #   SQLite 持久化
│   └── templates/             #   Jinja2 模板
├── src/
│   ├── main.py                # LangGraph 编排 (analyze_fund)
│   ├── agents/                # 7 个分析 agent
│   ├── backtesting/           # 回测引擎 + 策略
│   ├── data/                  # 数据模型
│   ├── graph/                 # AgentState / FundData
│   └── tools/                 # 基金数据 API 客户端
├── data/                      # 运行时数据 (SQLite, gitignored)
├── pyproject.toml             # Poetry 依赖
├── Dockerfile                 # 镜像构建
├── docker-compose.yml         # 容器编排
└── run.sh                     # 本地启动脚本
```

## 开发

```bash
# 装依赖
poetry install

# 跑测试
poetry run pytest

# 启 dev server
poetry run uvicorn app.web:app --reload --port 8080
```

## License

MIT,见 [LICENSE](./LICENSE)。
