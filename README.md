# MTG AI Search

An AI-assisted *Magic: The Gathering* card finder and deck manager.
Describe the card you want in natural language, and the app maps that request
to Scryfall Tagger function tags, then returns cards linked to those tags.

> 用自然语言描述你想要的万智牌。系统会抽取颜色、类别等筛选条件，
> 再把玩法意图匹配到 Scryfall Tagger 的功能标签，返回标签关联的卡牌。

![Search · 1](docs/images/search-dark-1.png)
![Search · 2](docs/images/search-dark-2.png)
![Deck detail](docs/images/deck-detail.png)

## Features

- **AI Search backed by Scryfall Tagger.** Natural-language queries are
  rewritten into gameplay intent, matched against real Scryfall Tagger function
  tags, and expanded through the local card-tag relation table.
- **Structured card filters.** Queries such as "blue creatures that create
  tokens" extract card constraints like color and type before tag matching.
- **Constrained LLM usage.** The chat model may rewrite and rerank candidates,
  but final tags must come from the stored Tagger catalog.
- **Exact Match.** Deterministic card search with filters for color, type,
  subtype, rarity, mana value, power/toughness, playtest cards, and keyword
  abilities.
- **Deck management.** Create decks, import/export deck lists, share deck
  links, generate deck analyses, and export A4 proxy PDFs or image bundles.
- **Admin console.** Manage users, rate limits, Scryfall card sync, function
  tag-card links, keyword ability sync, card-data export, and usage statistics.
- **Bilingual UI.** English and 简体中文 are available from the header.
- **External API.** API-key protected endpoints are available for AI Search and
  Exact Match.

## Current Search Model

The current AI Search path does **not** use the old card/keyword/effect
embedding pipeline.

At runtime:

1. `/api/search` receives a natural-language query.
2. The backend extracts structured filters such as colors and card types.
3. The remaining gameplay intent is matched against Scryfall Tagger function
   tags using lexical scoring, tag embeddings, and optional LLM reranking.
4. Matched tags are resolved to cards through `card_tagger_tags`.
5. The final card list is returned to the frontend.

`/api/tag-search` still exists as a compatibility/debug endpoint, but the
frontend default entry is `/api/search` and is labeled **AI Search**.

`keyword_abilities` is only used as Exact Match filter data. Keyword sync does
not generate embeddings.

## Stack

| Layer       | Tech |
|-------------|------|
| Frontend    | React 18, Vite 6, React Router 7 |
| Backend     | FastAPI, LangChain ChatOpenAI client, Pydantic |
| Database    | PostgreSQL 17 with [`pgvector`](https://github.com/pgvector/pgvector) |
| Card data   | [Scryfall](https://scryfall.com/) bulk data (CC0) |
| Tag data    | Scryfall Tagger function tags and Scryfall search API results |
| Email       | [Resend](https://resend.com/) (optional) |

## Quick Start (Docker)

Requires Docker + Docker Compose.

```bash
git clone https://github.com/ch4xer/MTG-AI-Search.git
cd MTG-AI-Search

cp .env.example .env
# Edit .env before starting.

docker compose up -d
```

Open:

- Frontend: <http://localhost:60010>
- Backend docs: <http://localhost:8000/docs>

The backend returns `503` for API routes while startup initialization is still
running. The frontend shows a maintenance notice during that window.

## Required Configuration

All variables live in `.env` (see [`.env.example`](.env.example)).

| Variable | Required | Purpose |
|----------|----------|---------|
| `POSTGRES_PASSWORD` | Yes | Compose-provisioned Postgres password. |
| `JWT_SECRET` | Yes | Signing key for auth tokens. Generate one with `openssl rand -hex 32`. |
| `DEEPSEEK_API_KEY` | For AI features | Chat model key for AI Search rewriting/reranking, deck analysis, and keyword summaries. |
| `DEEPSEEK_MODEL` | No | Defaults to the value configured in Docker Compose. |
| `DEEPSEEK_BASE_URL` | No | Defaults to `https://api.deepseek.com`. |
| `SILICONFLOW_API_KEY` | For tag vector search | Embedding key for Scryfall Tagger tag vectors. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | No | Bootstrap or promote a built-in admin account on startup. |
| `RESEND_API_KEY` | No | Enables email verification and password reset. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS allowlist. |

Tag bootstrap settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `TAG_BOOTSTRAP_ENABLED` | `true` | Generate function-tag expansion text and tag embeddings in background batches. |
| `TAG_EXPANSION_BATCH_SIZE` | `10` | Function-tag expansion batch size. |
| `TAG_EMBEDDING_BATCH_SIZE` | `64` | Tag embedding batch size. |
| `TAG_SAMPLE_SIZE` | `3` | Sample cards fetched per tag when building expansion text. |
| `SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS` | `0.8` | Delay between Scryfall sample-card requests. |
| `TAG_PRINT_EMBEDDING_TEXT` | `true` | Log generated tag embedding text. |

## Initial Setup Notes

On first launch the backend:

- runs database migrations,
- creates/promotes the optional built-in admin user,
- imports Scryfall bulk card data if `cards` is empty,
- initializes `keyword_abilities` if it is empty,
- loads persisted rate-limit settings,
- starts the daily Scryfall card sync loop,
- starts background function-tag expansion and tag-embedding generation if
  `TAG_BOOTSTRAP_ENABLED` is enabled.

AI Search needs the local function tag-card relation table. After the initial
card import completes, log in as an admin and run:

`Admin -> Database Maintenance -> Function tag links -> Sync function tags`

That task refreshes Scryfall function tags, fetches the cards for each tag, and
writes `card_tagger_tags`. A single card may be linked to multiple tags.

## Admin Maintenance

The database maintenance screen currently exposes:

- **Keyword sync**: refreshes `keyword_abilities` from rule 702 for Exact Match
  ability filters. It does not generate embeddings.
- **Function tag links**: refreshes function tags and syncs tag-card
  relationships for AI Search.
- **Export card data**: downloads card-search tables as JSONL files in a ZIP.
- **Manual sync**: checks Scryfall bulk data and updates local card data if
  Scryfall changed.
- **Force refresh**: bypasses the Scryfall timestamp check and refreshes card
  data.

The old card/keyword/effect embedding regeneration admin tasks have been
removed.

## Scheduled Jobs

- A daily card-data sync runs at midnight CST.
- Daily sync updates Scryfall card/printing data only.
- Keyword abilities are initialized only when the table is empty, and can be
  refreshed manually with **Keyword sync**.
- Function tag-card links are refreshed manually from the admin console.

## Local Development

Backend (Python 3.12+, [`uv`](https://github.com/astral-sh/uv) recommended):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Both processes read environment variables from the project-root `.env`.

## API Surface

Common endpoints:

- `POST /api/search`: AI Search card results.
- `POST /api/tag-search`: compatibility/debug tag-search response with matched
  tags and catalog metadata.
- `POST /api/discover`: Exact Match / faceted card search.
- `GET /api/keywords`: keyword ability list for Exact Match filters.
- `GET /api/cards/{oracle_id}/prints`: all local printings for a card.
- `POST /api/external/ai-search`: API-key protected AI Search.
- `POST /api/external/exact-match`: API-key protected Exact Match.

Admin endpoints are under `/api/admin/*` and require an admin account.

## Project Layout

```
.
├── backend/
│   ├── app/              FastAPI app, routes, services, repositories
│   ├── data/             Local keyword/tag helper data
│   └── scripts/          Scryfall import and maintenance scripts
├── frontend/             React app (Vite)
├── docs/images/          README screenshots
├── docker-compose.yml
└── .env.example
```

## Credits

- Card data and images © Wizards of the Coast.
  Provided as CC0 bulk data by [Scryfall](https://scryfall.com/docs/api/bulk-data).
- Scryfall Tagger tags and Scryfall search results power the tag-card search
  workflow.
- Mana symbols: [`mana-font`](https://github.com/andrewgioia/mana) and
  [`keyrune`](https://github.com/andrewgioia/keyrune) by Andrew Gioia.
- Built with FastAPI, React, PostgreSQL/pgvector, and the LangChain
  OpenAI-compatible chat client.

## Disclaimer

Unofficial Fan Content permitted under the Wizards of the Coast Fan Content
Policy. Not approved or endorsed by Wizards. *Magic: The Gathering* and its
related properties are © Wizards of the Coast LLC.

## License

[MIT](LICENSE).
