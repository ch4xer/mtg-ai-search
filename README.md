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

- **AI Search.** Describe gameplay effects in natural language and get matching
  cards powered by Scryfall Tagger data.
- **Structured card filters.** Queries such as "blue creatures that create
  tokens" automatically apply constraints like color and card type.
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

- <http://localhost:60010>

During startup initialization, the frontend may briefly show a maintenance
notice.

## Required Configuration

All variables live in `.env` (see [`.env.example`](.env.example)).

| Variable | Required | Purpose |
|----------|----------|---------|
| `POSTGRES_PASSWORD` | Yes | Compose-provisioned Postgres password. |
| `JWT_SECRET` | Yes | Signing key for auth tokens. Generate one with `openssl rand -hex 32`. |
| `DEEPSEEK_API_KEY` | For AI features | Chat model key for AI Search, deck analysis, and keyword summaries. |
| `DEEPSEEK_MODEL` | No | Defaults to the value configured in Docker Compose. |
| `DEEPSEEK_BASE_URL` | No | Defaults to `https://api.deepseek.com`. |
| `SILICONFLOW_API_KEY` | For AI Search | API key used to match search intent with Scryfall Tagger data. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | No | Bootstrap or promote a built-in admin account on startup. |
| `RESEND_API_KEY` | No | Enables email verification and password reset. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS allowlist. |

## Initial Setup Notes

On first launch the backend:

- prepares the database,
- creates or promotes the optional built-in admin user,
- imports Scryfall card data,
- starts background card-data maintenance.

After the initial card import completes, log in as an admin and run:

`Admin -> Database Maintenance -> Function tag links -> Sync function tags`

This prepares the tag data used by AI Search.

## Admin Maintenance

The database maintenance screen currently exposes:

- **Keyword sync**: refreshes Exact Match ability filters.
- **Function tag links**: refreshes AI Search tag data.
- **Export card data**: downloads searchable card data.
- **Manual sync**: updates local card data when Scryfall has changed.
- **Force refresh**: refreshes local card data immediately.

## Scheduled Jobs

- A daily card-data sync runs at midnight CST.
- AI Search tag data and Exact Match ability filters can be refreshed manually
  from the admin console.

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

## Credits

- Card data and images © Wizards of the Coast.
  Provided as CC0 bulk data by [Scryfall](https://scryfall.com/docs/api/bulk-data).
- Scryfall Tagger tags and Scryfall search results power AI Search.
- Mana symbols: [`mana-font`](https://github.com/andrewgioia/mana) and
  [`keyrune`](https://github.com/andrewgioia/keyrune) by Andrew Gioia.
- Built with FastAPI, React, PostgreSQL/pgvector, and LangChain.

## Disclaimer

Unofficial Fan Content permitted under the Wizards of the Coast Fan Content
Policy. Not approved or endorsed by Wizards. *Magic: The Gathering* and its
related properties are © Wizards of the Coast LLC.

## License

[MIT](LICENSE).
