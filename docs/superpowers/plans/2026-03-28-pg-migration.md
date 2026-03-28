# PostgreSQL + pgvector 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate MTG-Online from SQLite + ChromaDB to PostgreSQL + pgvector, refactor the search pipeline with structured filtering + 3-way vector search + RRF fusion, and containerize all services with Docker Compose.

**Architecture:** PostgreSQL with pgvector stores both structured card data and vector embeddings in a single `cards` table (3 vector columns for name/type_line/oracle_text). A `keyword_abilities` table holds ability embeddings. The LangGraph agent pipeline fans out to parallel filter + ability search, then performs 3-way vector search with RRF fusion. Docker Compose orchestrates PostgreSQL, FastAPI backend, and Nginx-served frontend.

**Tech Stack:** PostgreSQL 17 + pgvector, asyncpg, sentence-transformers (BAAI/bge-large-en), LangGraph, FastAPI, React + Vite, Docker Compose, Nginx

**Important note on schema:** The `cards` table includes a `data JSONB` column storing the full Scryfall card object. This is needed because the frontend renders fields (image_uris.normal, card_faces, keywords, rarity, flavor_text, set_name, loyalty) that are not individually extracted as columns. The extracted columns serve filtering and vector search; the JSONB column serves frontend display via `get_cards_by_ids()`.

---

## File Structure

| Action | Path | Purpose |
|--------|------|---------|
| Create | `docker-compose.yml` | Orchestrate all services |
| Create | `backend/Dockerfile` | Backend container |
| Create | `frontend/Dockerfile` | Frontend build + Nginx |
| Create | `frontend/nginx.conf` | Nginx config with /api proxy |
| Create | `backend/app/embedding.py` | Shared embedding model |
| Create | `backend/app/db.py` | PostgreSQL connection pool + queries |
| Create | `backend/scripts/migrate_to_pg.py` | Data migration script |
| Modify | `backend/app/agent.py` | Rewrite search pipeline |
| Modify | `backend/app/main.py` | Add connection pool lifecycle |
| Modify | `backend/requirements.txt` | Update dependencies |
| Modify | `backend/.env` | Add DATABASE_URL, POSTGRES_PASSWORD |
| Delete | `backend/app/database.py` | Replaced by db.py |
| Delete | `backend/app/vectorstore.py` | Replaced by db.py |
| Delete | `backend/scripts/setup_data.py` | Replaced by migrate_to_pg.py |

---

### Task 1: Docker Infrastructure

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Create docker-compose.yml**

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
    volumes:
      - backend-models:/root/.cache

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  pgdata:
  backend-models:
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create frontend/nginx.conf**

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 4: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 5: Update backend/.env**

Add these lines to `backend/.env`:
```
DATABASE_URL=postgresql://mtg:mtg_password@localhost:5432/mtg
POSTGRES_PASSWORD=mtg_password
```

Also create a root `.env` file for docker-compose:
```
POSTGRES_PASSWORD=mtg_password
DEEPSEEK_API_KEY=REDACTED-DEEPSEEK-KEY
```

- [ ] **Step 6: Verify PostgreSQL starts**

Run: `docker compose up db -d && docker compose logs db --tail 20`
Expected: "database system is ready to accept connections"

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf .env
git commit -m "infra: add Docker Compose with PostgreSQL, backend, and frontend services"
```

---

### Task 2: Embedding Module

**Files:**
- Create: `backend/app/embedding.py`

- [ ] **Step 1: Create backend/app/embedding.py**

```python
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model."""
    global _model
    if _model is None:
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        _model = SentenceTransformer("BAAI/bge-large-en")
        logger.info("Loaded embedding model: BAAI/bge-large-en")
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    """Encode texts into embedding vectors."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
```

- [ ] **Step 2: Verify it works**

Run: `cd /home/ch4ser/Projects/MTG-Online/backend && python -c "from app.embedding import encode; v = encode(['hello']); print(len(v[0]))"`
Expected: `1024`

- [ ] **Step 3: Commit**

```bash
git add backend/app/embedding.py
git commit -m "feat: add shared embedding module for bge-large-en"
```

---

### Task 3: Database Module

**Files:**
- Create: `backend/app/db.py`

- [ ] **Step 1: Create backend/app/db.py with connection pool**

```python
import os
import re
import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL", "postgresql://mtg:mtg_password@localhost:5432/mtg")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        logger.info("Created asyncpg connection pool")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Closed asyncpg connection pool")
```

- [ ] **Step 2: Add filter_cards function**

Append to `backend/app/db.py`:

```python
# Operators allowed in condition expressions like ">5", ">=2020-01-01"
_CONDITION_RE = re.compile(r"^(>=|<=|>|<|=)\s*(.+)$")


def _parse_condition(expr: str) -> tuple[str, str]:
    """Parse a condition expression like '>5' into (operator, value)."""
    m = _CONDITION_RE.match(expr.strip())
    if not m:
        return ("=", expr.strip())
    return (m.group(1), m.group(2).strip())


async def filter_cards(filters: dict) -> list[str]:
    """Filter cards by structured conditions. Returns list of card IDs.

    filters keys: released_at, layout, mana_cost, cmc, power, toughness, colors
    - Enumerable (colors, layout): exact match, e.g. "B R", "transform"
    - Non-enumerable (cmc, power, toughness, released_at, mana_cost): condition expr, e.g. ">5"
    """
    pool = await get_pool()

    clauses: list[str] = []
    params: list = []
    idx = 1

    for key, value in filters.items():
        if value is None:
            continue

        if key == "colors":
            # "B R" means colors must contain both B and R
            color_list = value.split()
            clauses.append(f"colors @> ${idx}::text[]")
            params.append(color_list)
            idx += 1

        elif key == "layout":
            clauses.append(f"layout = ${idx}")
            params.append(value)
            idx += 1

        elif key in ("cmc", "power", "toughness", "released_at", "mana_cost"):
            op, val = _parse_condition(value)
            col = key
            if key in ("cmc",):
                clauses.append(f"{col} {op} ${idx}::real")
                params.append(float(val))
            elif key in ("power", "toughness"):
                # power/toughness are TEXT, cast for numeric comparison
                clauses.append(f"CAST(NULLIF({col}, '*') AS real) {op} ${idx}::real")
                params.append(float(val))
            elif key == "released_at":
                clauses.append(f"{col} {op} ${idx}::date")
                params.append(val)
            elif key == "mana_cost":
                clauses.append(f"{col} {op} ${idx}")
                params.append(val)
            idx += 1

    if not clauses:
        return []

    where = " AND ".join(clauses)
    query = f"SELECT id FROM cards WHERE {where}"
    logger.info("filter_cards SQL: %s params: %s", query, params)

    rows = await pool.fetch(query, *params)
    return [row["id"] for row in rows]
```

- [ ] **Step 3: Add vector search functions**

Append to `backend/app/db.py`:

```python
async def vector_search_cards(
    column: str,
    query_embedding: list[float],
    n_results: int = 20,
    card_ids: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Vector search on a specific embedding column. Returns [(id, distance), ...]."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    if card_ids:
        query = f"""
            SELECT id, {column} <=> $1::vector AS distance
            FROM cards
            WHERE id = ANY($2) AND {column} IS NOT NULL
            ORDER BY distance
            LIMIT $3
        """
        rows = await pool.fetch(query, embedding_str, card_ids, n_results)
    else:
        query = f"""
            SELECT id, {column} <=> $1::vector AS distance
            FROM cards
            WHERE {column} IS NOT NULL
            ORDER BY distance
            LIMIT $2
        """
        rows = await pool.fetch(query, embedding_str, n_results)

    return [(row["id"], row["distance"]) for row in rows]


async def search_abilities(
    query_embedding: list[float],
    n_results: int = 5,
    distance_threshold: float = 0.2,
) -> list[dict]:
    """Search keyword abilities by vector similarity."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = await pool.fetch(
        """
        SELECT name, description, embedding <=> $1::vector AS distance
        FROM keyword_abilities
        WHERE embedding IS NOT NULL
        ORDER BY distance
        LIMIT $2
        """,
        embedding_str,
        n_results,
    )

    return [
        {"name": row["name"], "description": row["description"], "distance": row["distance"]}
        for row in rows
        if row["distance"] < distance_threshold
    ]


async def get_cards_by_ids(card_ids: list[str]) -> list[dict]:
    """Retrieve full card data by IDs, preserving order."""
    if not card_ids:
        return []

    pool = await get_pool()
    rows = await pool.fetch("SELECT id, data FROM cards WHERE id = ANY($1)", card_ids)

    card_map = {}
    for row in rows:
        import json
        card_map[row["id"]] = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]

    return [card_map[cid] for cid in card_ids if cid in card_map]
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db.py
git commit -m "feat: add PostgreSQL database module with filter, vector search, and abilities search"
```

---

### Task 4: Migration Script

**Files:**
- Create: `backend/scripts/migrate_to_pg.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update backend/requirements.txt**

Replace contents with:
```
fastapi
uvicorn[standard]
langchain
langchain-openai
langgraph
asyncpg
psycopg2-binary
sentence-transformers
requests
httpx
python-dotenv
```

(Removed `chromadb`, added `asyncpg` for runtime and `psycopg2-binary` for migration script)

- [ ] **Step 2: Install new dependencies**

Run: `cd /home/ch4ser/Projects/MTG-Online/backend && pip install asyncpg psycopg2-binary`

- [ ] **Step 3: Create backend/scripts/migrate_to_pg.py**

```python
"""Migration script: download Scryfall data, populate PostgreSQL + pgvector.

Usage:
    1. Start PostgreSQL: docker compose up db -d
    2. Run: cd backend && python scripts/migrate_to_pg.py
"""

import json
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data_loader import download_scryfall_cards, parse_keyword_abilities
from app.embedding import encode

KEYWORD_ABILITY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "keyword_ability.txt",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mtg:mtg_password@localhost:5432/mtg"
)


def log(msg: str):
    print(msg, flush=True)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def create_schema(conn):
    """Create pgvector extension and tables."""
    log("Creating schema...")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
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
                data                  JSONB NOT NULL,
                name_embedding        vector(1024),
                type_line_embedding   vector(1024),
                oracle_text_embedding vector(1024)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keyword_abilities (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                embedding   vector(1024)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_released_at ON cards(released_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_cmc ON cards(cmc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_colors ON cards USING GIN(colors)")
    conn.commit()
    log("Schema created.")


def insert_cards(conn, cards: list[dict]):
    """Insert card rows (without embeddings) in batches."""
    log(f"Inserting {len(cards)} cards...")
    batch_size = 1000

    with conn.cursor() as cur:
        for i in range(0, len(cards), batch_size):
            batch = cards[i:i + batch_size]
            values = []
            for card in batch:
                image_uris = card.get("image_uris") or {}
                colors = card.get("colors") or []
                values.append((
                    card["id"],
                    card.get("name", ""),
                    card.get("lang"),
                    card.get("released_at"),
                    card.get("uri"),
                    card.get("scryfall_uri"),
                    card.get("layout"),
                    image_uris.get("art_crop"),
                    image_uris.get("border_crop"),
                    card.get("mana_cost"),
                    card.get("cmc"),
                    card.get("type_line"),
                    card.get("oracle_text"),
                    card.get("power"),
                    card.get("toughness"),
                    colors,
                    json.dumps(card),
                ))
            execute_values(
                cur,
                """INSERT INTO cards (
                    id, name, lang, released_at, uri, scryfall_uri, layout,
                    image_art_crop, image_border_crop, mana_cost, cmc, type_line,
                    oracle_text, power, toughness, colors, data
                ) VALUES %s ON CONFLICT (id) DO NOTHING""",
                values,
            )
            conn.commit()
            log(f"  Inserted cards {i + 1}-{min(i + batch_size, len(cards))}")


def insert_abilities(conn, abilities: dict[str, str]):
    """Insert keyword abilities (without embeddings)."""
    log(f"Inserting {len(abilities)} keyword abilities...")
    with conn.cursor() as cur:
        values = [
            (name.lower().replace(" ", "_"), name, desc)
            for name, desc in abilities.items()
        ]
        execute_values(
            cur,
            "INSERT INTO keyword_abilities (id, name, description) VALUES %s ON CONFLICT (id) DO NOTHING",
            values,
        )
    conn.commit()
    log("Abilities inserted.")


def generate_card_embeddings(conn, batch_size: int = 200):
    """Generate and store embeddings for cards."""
    log("Generating card embeddings...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, type_line, oracle_text FROM cards WHERE name_embedding IS NULL")
        rows = cur.fetchall()

    log(f"  {len(rows)} cards need embeddings")
    total = len(rows)

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        ids = [r[0] for r in batch]
        names = [r[1] or "" for r in batch]
        type_lines = [r[2] or "" for r in batch]
        oracle_texts = [r[3] or "" for r in batch]

        t0 = time.time()
        name_vecs = encode(names)
        type_vecs = encode(type_lines)
        oracle_vecs = encode(oracle_texts)

        with conn.cursor() as cur:
            for j, card_id in enumerate(ids):
                cur.execute(
                    """UPDATE cards SET
                        name_embedding = %s::vector,
                        type_line_embedding = %s::vector,
                        oracle_text_embedding = %s::vector
                    WHERE id = %s""",
                    (str(name_vecs[j]), str(type_vecs[j]), str(oracle_vecs[j]), card_id),
                )
        conn.commit()

        elapsed = time.time() - t0
        log(f"  [{i + batch_size}/{total}] Embedded {len(batch)} cards ({elapsed:.1f}s)")


def generate_ability_embeddings(conn):
    """Generate and store embeddings for keyword abilities."""
    log("Generating ability embeddings...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM keyword_abilities WHERE embedding IS NULL")
        rows = cur.fetchall()

    if not rows:
        log("  No abilities need embeddings.")
        return

    texts = [f"{r[1]}: {r[2]}" for r in rows]
    vecs = encode(texts)

    with conn.cursor() as cur:
        for i, row in enumerate(rows):
            cur.execute(
                "UPDATE keyword_abilities SET embedding = %s::vector WHERE id = %s",
                (str(vecs[i]), row[0]),
            )
    conn.commit()
    log(f"  Embedded {len(rows)} abilities.")


def create_vector_indexes(conn):
    """Create ivfflat indexes after data is loaded."""
    log("Creating vector indexes...")
    with conn.cursor() as cur:
        # ivfflat needs lists parameter; use sqrt(n) as a reasonable default
        cur.execute("SELECT COUNT(*) FROM cards WHERE name_embedding IS NOT NULL")
        card_count = cur.fetchone()[0]
        lists = max(1, int(card_count ** 0.5))
        log(f"  Using {lists} lists for ivfflat (based on {card_count} cards)")

        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_name_vec ON cards USING ivfflat(name_embedding vector_cosine_ops) WITH (lists = {lists})")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_type_vec ON cards USING ivfflat(type_line_embedding vector_cosine_ops) WITH (lists = {lists})")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_oracle_vec ON cards USING ivfflat(oracle_text_embedding vector_cosine_ops) WITH (lists = {lists})")

        cur.execute("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NOT NULL")
        ability_count = cur.fetchone()[0]
        ability_lists = max(1, int(ability_count ** 0.5))
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_abilities_vec ON keyword_abilities USING ivfflat(embedding vector_cosine_ops) WITH (lists = {ability_lists})")
    conn.commit()
    log("Vector indexes created.")


def main():
    t_start = time.time()

    conn = get_conn()
    try:
        create_schema(conn)

        # Download and insert cards
        raw_cards = download_scryfall_cards()
        valid_cards = [c for c in raw_cards if c.get("layout") not in ("token", "emblem", "art_series")]
        insert_cards(conn, valid_cards)

        # Parse and insert abilities
        abilities = parse_keyword_abilities(KEYWORD_ABILITY_FILE)
        insert_abilities(conn, abilities)

        # Generate embeddings
        generate_card_embeddings(conn)
        generate_ability_embeddings(conn)

        # Create vector indexes
        create_vector_indexes(conn)

    finally:
        conn.close()

    log(f"\nMigration complete! Total time: {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/scripts/migrate_to_pg.py
git commit -m "feat: add PostgreSQL migration script with Scryfall data import and pgvector embeddings"
```

---

### Task 5: Rewrite Agent Pipeline

**Files:**
- Modify: `backend/app/agent.py`

- [ ] **Step 1: Rewrite backend/app/agent.py**

Replace the entire file with:

```python
import json
import logging
import os
from collections import defaultdict
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .db import filter_cards, get_cards_by_ids, search_abilities, vector_search_cards
from .embedding import encode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_API_KEY,
    temperature=0.3,
)

ABILITY_DISTANCE_THRESHOLD = 0.2
RRF_K = 60


class SearchState(TypedDict):
    query: str
    optimized_query: str
    colors: list[str]
    type: str
    name: str
    filters: dict
    filtered_card_ids: list[str]
    abilities: list[dict]
    vector_queries: dict
    ranked_results: list[dict]


# ── Node 1: optimize_query ──────────────────────────────────────────────

def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize query and extract structured card constraints."""
    response = llm.invoke([
        SystemMessage(content=(
            "You are a Magic: The Gathering expert. Given a user's card search query, "
            "extract structured information and generate an optimized ability search query.\n\n"
            "Return a JSON object with these fields:\n"
            '- "optimized_query": English query for ability vector search (focus on mechanics/effects)\n'
            '- "colors": array of color codes (W, U, B, R, G) if specified\n'
            '- "type": card type if specified (Creature, Instant, Sorcery, Enchantment, Artifact, Land, etc.)\n'
            '- "name": exact card name if the user specified a specific card\n'
            '- "filters": object with optional keys: released_at, layout, mana_cost, cmc, power, toughness, colors.\n'
            '  - For non-enumerable fields (cmc, power, toughness, released_at, mana_cost), use condition expressions like ">5", ">=2020-01-01"\n'
            '  - For enumerable fields (colors, layout), use exact values like "B R", "transform"\n'
            '  - Use null for fields not mentioned in the query\n\n'
            "Examples:\n"
            'Input: "能让对手弃牌的黑色生物"\n'
            'Output: {"optimized_query": "discard cards from opponent hand", "colors": ["B"], "type": "Creature", "name": "", '
            '"filters": {"colors": "B", "released_at": null, "layout": null, "mana_cost": null, "cmc": null, "power": null, "toughness": null}}\n\n'
            'Input: "red instant that deals damage with cmc less than 3"\n'
            'Output: {"optimized_query": "deal direct damage to target", "colors": ["R"], "type": "Instant", "name": "", '
            '"filters": {"colors": "R", "cmc": "<3", "released_at": null, "layout": null, "mana_cost": null, "power": null, "toughness": null}}\n\n'
            'Input: "creatures with power greater than 10 released after 2020"\n'
            'Output: {"optimized_query": "powerful creature", "colors": [], "type": "Creature", "name": "", '
            '"filters": {"power": ">10", "released_at": ">2020-01-01", "colors": null, "layout": null, "mana_cost": null, "cmc": null, "toughness": null}}\n\n'
            'Input: "Liliana of the Veil"\n'
            'Output: {"optimized_query": "", "colors": [], "type": "", "name": "Liliana of the Veil", '
            '"filters": {"colors": null, "released_at": null, "layout": null, "mana_cost": null, "cmc": null, "power": null, "toughness": null}}\n\n'
            "Return ONLY the JSON object, nothing else."
        )),
        HumanMessage(content=state["query"]),
    ])

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.info(">>> Original query: %s", state["query"])

    try:
        data = json.loads(content)
        optimized = data.get("optimized_query", state["query"])
        colors = data.get("colors", [])
        card_type = data.get("type", "")
        card_name = data.get("name", "")
        filters = data.get("filters", {})
        # Clean null values from filters
        filters = {k: v for k, v in filters.items() if v is not None}
    except (json.JSONDecodeError, TypeError):
        optimized = content if isinstance(content, str) else str(content)
        colors = []
        card_type = ""
        card_name = ""
        filters = {}

    logger.info("<<< Optimized: %s, Colors: %s, Type: %s, Name: %s, Filters: %s",
                optimized, colors, card_type, card_name, filters)

    return {
        "optimized_query": optimized,
        "colors": colors,
        "type": card_type,
        "name": card_name,
        "filters": filters,
    }


# ── Node 2a: filter_cards_node (parallel) ───────────────────────────────

async def filter_cards_node(state: SearchState) -> dict:
    """Filter cards by structured conditions from optimize_query."""
    filters = state.get("filters", {})
    if not filters:
        logger.info("<<< No filters, skipping structured filtering")
        return {"filtered_card_ids": []}

    card_ids = await filter_cards(filters)
    logger.info("<<< Filtered to %d cards", len(card_ids))
    return {"filtered_card_ids": card_ids}


# ── Node 2b: search_abilities_node (parallel) ───────────────────────────

async def search_abilities_node(state: SearchState) -> dict:
    """Search keyword abilities by vector similarity."""
    query = state.get("optimized_query") or state["query"]
    if not query:
        return {"abilities": []}

    query_vec = encode([query])[0]
    abilities = await search_abilities(
        query_vec, n_results=5, distance_threshold=ABILITY_DISTANCE_THRESHOLD
    )

    for a in abilities:
        logger.info("  - %s (distance: %.3f)", a["name"], a["distance"])
    logger.info("<<< Found %d relevant abilities", len(abilities))

    return {"abilities": abilities}


# ── Node 3: prepare_vector_queries ───────────────────────────────────────

def prepare_vector_queries(state: SearchState) -> dict:
    """Prepare vector query texts for 3-way search."""
    optimized = state.get("optimized_query") or state["query"]
    abilities = state.get("abilities", [])
    card_name = state.get("name", "")
    card_type = state.get("type", "")

    queries = {}

    # name query: only if a specific card name was given
    if card_name:
        queries["name"] = card_name

    # type_line query: only if a card type was specified
    if card_type:
        queries["type_line"] = card_type

    # oracle_text query: always present, combine with abilities
    oracle_parts = [optimized] if optimized else []
    for a in abilities:
        oracle_parts.append(a["name"])
    queries["oracle_text"] = " ".join(oracle_parts) if oracle_parts else ""

    logger.info("<<< Vector queries: %s", queries)
    return {"vector_queries": queries}


# ── Node 4: vector_search_node ───────────────────────────────────────────

async def vector_search_node(state: SearchState) -> dict:
    """3-way vector search with RRF fusion."""
    queries = state.get("vector_queries", {})
    filtered_ids = state.get("filtered_card_ids", [])
    card_ids_filter = filtered_ids if filtered_ids else None

    # Map query keys to embedding column names
    column_map = {
        "name": "name_embedding",
        "type_line": "type_line_embedding",
        "oracle_text": "oracle_text_embedding",
    }

    # Run each vector search
    rankings: dict[str, list[str]] = {}
    for key, text in queries.items():
        if not text:
            continue
        col = column_map[key]
        query_vec = encode([text])[0]
        results = await vector_search_cards(col, query_vec, n_results=20, card_ids=card_ids_filter)
        rankings[key] = [r[0] for r in results]  # list of card IDs in rank order
        logger.info("  Vector search [%s]: %d results", key, len(results))

    # RRF fusion
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings.values():
        for rank, card_id in enumerate(ranking, start=1):
            scores[card_id] += 1.0 / (RRF_K + rank)

    # Sort by RRF score descending, take top 10
    top_ids = sorted(scores, key=scores.get, reverse=True)[:10]

    # Fetch full card data
    cards = await get_cards_by_ids(top_ids)
    logger.info("<<< RRF fusion: %d results", len(cards))

    return {"ranked_results": cards}


# ── Graph assembly ───────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_query", optimize_query)
    graph.add_node("filter_cards", filter_cards_node)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("prepare_vector_queries", prepare_vector_queries)
    graph.add_node("vector_search", vector_search_node)

    graph.set_entry_point("optimize_query")

    # Fan out: optimize_query -> [filter_cards, search_abilities] in parallel
    graph.add_edge("optimize_query", "filter_cards")
    graph.add_edge("optimize_query", "search_abilities")

    # Fan in: both -> prepare_vector_queries
    graph.add_edge("filter_cards", "prepare_vector_queries")
    graph.add_edge("search_abilities", "prepare_vector_queries")

    graph.add_edge("prepare_vector_queries", "vector_search")
    graph.add_edge("vector_search", END)

    return graph.compile()


search_agent = build_graph()


async def run_search(query: str) -> list[dict]:
    """Run the search agent with a query."""
    result = await search_agent.ainvoke({
        "query": query,
        "optimized_query": "",
        "colors": [],
        "type": "",
        "name": "",
        "filters": {},
        "filtered_card_ids": [],
        "abilities": [],
        "vector_queries": {},
        "ranked_results": [],
    })
    return result["ranked_results"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent.py
git commit -m "feat: rewrite agent pipeline with structured filter, 3-way vector search, and RRF fusion"
```

---

### Task 6: Update FastAPI Lifecycle

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update backend/app/main.py**

Replace the entire file with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .db import close_pool, get_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(title="MTG AI Card Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: list[dict]


@app.post("/api/search", response_model=SearchResponse)
async def search_cards(request: SearchRequest):
    results = await run_search(request.query)
    return SearchResponse(results=results)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add asyncpg connection pool lifecycle to FastAPI"
```

---

### Task 7: Cleanup Old Files

**Files:**
- Delete: `backend/app/database.py`
- Delete: `backend/app/vectorstore.py`
- Delete: `backend/scripts/setup_data.py`

- [ ] **Step 1: Remove old database and vectorstore modules**

```bash
git rm backend/app/database.py backend/app/vectorstore.py backend/scripts/setup_data.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove old SQLite/ChromaDB modules replaced by PostgreSQL"
```

---

### Task 8: End-to-End Verification

- [ ] **Step 1: Start PostgreSQL**

```bash
cd /home/ch4ser/Projects/MTG-Online && docker compose up db -d
```

- [ ] **Step 2: Run migration script**

```bash
cd /home/ch4ser/Projects/MTG-Online/backend && python scripts/migrate_to_pg.py
```

Expected: Downloads Scryfall cards, inserts into PostgreSQL, generates embeddings, creates indexes. May take 30+ minutes for embedding generation.

- [ ] **Step 3: Start backend locally and test**

```bash
cd /home/ch4ser/Projects/MTG-Online/backend && uvicorn app.main:app --reload
```

In another terminal:
```bash
curl -X POST http://localhost:8000/api/search -H "Content-Type: application/json" -d '{"query": "red instant that deals damage"}'
```

Expected: JSON response with `results` array containing card objects.

- [ ] **Step 4: Test with Docker Compose (full stack)**

```bash
cd /home/ch4ser/Projects/MTG-Online && docker compose up --build
```

Open `http://localhost:5173` in browser, enter a search query, verify cards display correctly.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: address issues found during end-to-end testing"
```
