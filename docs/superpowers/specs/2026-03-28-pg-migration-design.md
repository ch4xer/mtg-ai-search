# MTG-Online: PostgreSQL + pgvector 迁移设计

## 概述

将数据层从 SQLite + ChromaDB 迁移到 PostgreSQL + pgvector，重构搜索管道引入结构化筛选（tool calling）和三路向量搜索 + RRF 融合，Docker Compose 编排全部服务。

## 决策记录

| 问题 | 决策 |
|------|------|
| 异能搜索迁移 | 全部迁移到 pgvector，移除 ChromaDB |
| MCP 工具形式 | LangGraph 内部 tool calling，非独立 MCP Server |
| 向量列存储方式 | 同一张 cards 表，3 个 vector 列 |
| 筛选与向量搜索关系 | 先结构化筛选缩小候选集，再在候选集内向量搜索 |
| 异能数据存储 | PostgreSQL 独立表 keyword_abilities |
| Docker 范围 | docker-compose 编排全部服务（PostgreSQL + 后端 + 前端） |

---

## 1. 数据层

### 1.1 PostgreSQL Schema

**`cards` 表：**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE cards (
  id                    TEXT PRIMARY KEY,
  name                  TEXT NOT NULL,
  lang                  TEXT,
  released_at           DATE,
  uri                   TEXT,
  scryfall_uri          TEXT,
  layout                TEXT,
  image_art_crop        TEXT,
  image_border_crop     TEXT,
  mana_cost             TEXT,
  cmc                   REAL,
  type_line             TEXT,
  oracle_text           TEXT,
  power                 TEXT,
  toughness             TEXT,
  colors                TEXT[],
  name_embedding        vector(1024),
  type_line_embedding   vector(1024),
  oracle_text_embedding vector(1024)
);

CREATE INDEX idx_cards_name ON cards(name);
CREATE INDEX idx_cards_released_at ON cards(released_at);
CREATE INDEX idx_cards_cmc ON cards(cmc);
CREATE INDEX idx_cards_colors ON cards USING GIN(colors);
CREATE INDEX idx_cards_name_vec ON cards USING ivfflat(name_embedding vector_cosine_ops);
CREATE INDEX idx_cards_type_vec ON cards USING ivfflat(type_line_embedding vector_cosine_ops);
CREATE INDEX idx_cards_oracle_vec ON cards USING ivfflat(oracle_text_embedding vector_cosine_ops);
```

**`keyword_abilities` 表：**

```sql
CREATE TABLE keyword_abilities (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT NOT NULL,
  embedding   vector(1024)
);

CREATE INDEX idx_abilities_vec ON keyword_abilities USING ivfflat(embedding vector_cosine_ops);
```

### 1.2 数据层模块 `backend/app/db.py`

使用 `asyncpg` 异步连接池，提供：

- `get_pool()` — 应用启动时创建连接池
- `filter_cards(conditions: dict) -> list[str]` — 结构化条件筛选，返回 card ID 列表
- `vector_search_cards(column: str, query_embedding: list[float], n_results: int, card_ids: list[str] | None) -> list[tuple[str, float]]` — 在候选集内做向量搜索
- `search_abilities(query_embedding: list[float], n_results: int, distance_threshold: float) -> list[dict]` — 异能向量搜索
- `get_cards_by_ids(card_ids: list[str]) -> list[dict]` — 获取完整卡牌数据

### 1.3 Embedding 模块 `backend/app/embedding.py`

独立模块，封装 `BAAI/bge-large-en` 模型加载和 embedding 生成：

- `get_model()` — 懒加载 SentenceTransformer 模型
- `encode(texts: list[str]) -> list[list[float]]` — 批量生成 embedding

供迁移脚本和运行时查询共用。

---

## 2. Agent 管道

### 2.1 LangGraph 图结构

```
optimize_query
    ├──→ filter_cards_tool  (并行)
    └──→ search_abilities   (并行)
              ↓
         prepare_vector_queries
              ↓
         vector_search (三路搜索 + RRF 融合)
              ↓
            END
```

`optimize_query` 之后，`filter_cards_tool` 和 `search_abilities` 并行执行（LangGraph 扇出），两者完成后汇入 `prepare_vector_queries`。

### 2.2 节点职责

**① `optimize_query`**

保留现有逻辑，扩展输出。LLM 从用户 query 提取：

```json
{
  "optimized_query": "deal direct damage to target",
  "colors": ["Red"],
  "type": "Instant",
  "name": "",
  "filters": {
    "cmc": ">3",
    "released_at": ">2015-01-01",
    "power": null,
    "toughness": null,
    "layout": null,
    "mana_cost": null
  }
}
```

**② `filter_cards_tool`**

固定图节点，接收 `optimize_query` 提取的 `filters` 字典，直接拼接 SQL 查询。参数规则：

- 不可穷举参数（`cmc`、`power`、`toughness`、`released_at`、`mana_cost`）：条件表达式，如 `">5"`、`">=2020-01-01"`
- 可穷举参数（`colors`、`layout`）：精确匹配，如 `"B R"`、`"transform"`

内部解析条件表达式，拼接参数化 SQL WHERE 子句查询 PostgreSQL，返回候选 card ID 列表。如果 filters 中所有字段均为 null，则返回空列表表示不限制范围。

**③ `search_abilities`**

用 `optimized_query` 的 embedding 在 `keyword_abilities` 表做向量搜索，distance_threshold=0.2，返回相关异能列表。

**④ `prepare_vector_queries`**

根据 `optimized_query` + abilities 准备三路查询文本：

- `name_query`：指定了卡片名时使用，否则 None
- `type_line_query`：指定了卡片类型时使用，否则 None
- `oracle_text_query`：`optimized_query` + 匹配到的 ability 名称拼接（始终存在）

用 embedding 模型将非 None 的查询文本转为向量。

**⑤ `vector_search`**

- 对每个非 None 的查询向量，在 `cards` 表对应列做向量搜索
- 如果有候选 ID，用 `WHERE id = ANY($1)` 限制范围；否则全表搜索
- 每路返回 top-20
- RRF 算法融合：`score(d) = Σ 1/(k + rank_i(d))`，k=60
- 返回 top-10 最终结果

### 2.3 移除的节点

- `generate_card_description` — 不再需要 LLM 生成假设性卡牌描述
- `rank_results` — 被 RRF 算法替代

### 2.4 SearchState

```python
class SearchState(TypedDict):
    query: str
    optimized_query: str
    colors: list[str]
    type: str
    name: str
    filters: dict
    filtered_card_ids: list[str]
    abilities: list[dict]
    vector_queries: dict       # {name, type_line, oracle_text} 查询文本
    ranked_results: list[dict]
```

---

## 3. Docker 与基础设施

### 3.1 docker-compose.yml

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mtg
      POSTGRES_USER: mtg
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mtg"]
      interval: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://mtg:${POSTGRES_PASSWORD}@db:5432/mtg
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

### 3.2 Dockerfile

- **backend/Dockerfile**：Python 3.12 slim，安装 requirements.txt，CMD `uvicorn backend.app.main:app --host 0.0.0.0`
- **frontend/Dockerfile**：Node 构建阶段 `vite build`，Nginx 阶段 serve 静态文件，反向代理 `/api` 到 backend:8000

### 3.3 迁移脚本 `backend/scripts/migrate_to_pg.py`

用户手动执行，步骤：

1. 连接 PostgreSQL，创建 pgvector 扩展和表结构
2. 从 Scryfall 下载数据（复用 `data_loader.py`），拆字段写入 cards 表
3. 解析 `keyword_ability.txt`，写入 keyword_abilities 表
4. 批量生成 embedding（bge-large-en），更新向量列
5. 数据入库后创建 ivfflat 索引

### 3.4 环境变量

`.env` 新增：
```
DATABASE_URL=postgresql://mtg:password@localhost:5432/mtg
POSTGRES_PASSWORD=password
```

### 3.5 移除的文件

- `backend/app/database.py` → 被 `db.py` 替代
- `backend/app/vectorstore.py` → 被 `db.py` 替代
- `backend/cards.db` → SQLite 不再使用
- `backend/chroma_data/` → ChromaDB 不再使用
- `backend/scripts/setup_data.py` → 被 `migrate_to_pg.py` 替代

### 3.6 依赖变更

**requirements.txt 新增：**
- `asyncpg` — PostgreSQL 异步驱动
- `pgvector` — pgvector Python 支持（可选，asyncpg 可直接处理）

**requirements.txt 移除：**
- `chromadb`

---

## 4. 前端

无需改动。`/api/search` 接口的请求和响应格式保持不变。
