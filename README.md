# MTG AI Search

An AI-driven *Magic: The Gathering* card finder.
Describe the card you want in natural language — Chinese or English — and the
agent finds it for you, even when you don't remember the exact name.

> 用自然语言描述你想要的万智牌，AI 会理解你的意图并为你找到。
> 支持中英文混合查询，并提供卡组管理、PDF 代牌打印等功能。

## Features

- **Natural-language search.** A LangGraph agent reasons over card text,
  rule-702 keyword abilities, and effect-level chunks before ranking results.
- **Bilingual UI.** Switch between English and 简体中文 from the header.
- **Deck management.** Build decks, import/export deck lists, generate
  AI-written analyses, export 3×3 A4 PDFs for proxy printing.
- **Admin console.** Database sync from Scryfall, embedding regeneration,
  rate-limit controls, and per-user usage statistics.
- **DeepSeek chat + SiliconFlow embeddings.** Reasoning runs on DeepSeek
  via the OpenAI-compatible API; semantic vectors come from SiliconFlow's
  hosted `Qwen/Qwen3-Embedding-4B`.

## Stack

| Layer       | Tech                                                       |
|-------------|------------------------------------------------------------|
| Frontend    | React 18, Vite 6, React Router 7                           |
| Backend     | FastAPI, LangChain / LangGraph, Pydantic                   |
| Database    | PostgreSQL 17 with [`pgvector`](https://github.com/pgvector/pgvector) |
| Card data   | [Scryfall](https://scryfall.com/) bulk data (CC0)          |
| Email       | [Resend](https://resend.com/) (optional)                   |

## Quick start (Docker)

Requires Docker + Docker Compose.

```bash
git clone https://github.com/ch4xer/MTG-AI-Search.git
cd MTG-AI-Search

cp .env.example .env
# Edit .env. The following are all required to start the app:
#   POSTGRES_PASSWORD, JWT_SECRET,
#   DEEPSEEK_API_KEY     (chat),
#   SILICONFLOW_API_KEY  (embeddings).

docker compose up -d
```

Then open:

- Frontend → <http://localhost:60010>
- Backend  → <http://localhost:8000/docs>

On first launch the backend automatically pulls Scryfall bulk data, seeds the
keyword-ability table and backfills embeddings — no admin action required.
The initial seed takes tens of minutes depending on your LLM provider; watch
`docker compose logs -f mtg-backend` for progress.

## Local development

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

## Configuration

All variables live in `.env` (see [`.env.example`](.env.example)).
The most important ones:

| Variable           | Required | Purpose                                         |
|--------------------|----------|-------------------------------------------------|
| `POSTGRES_PASSWORD`| ✅       | Compose-provisioned Postgres password.          |
| `JWT_SECRET`       | ✅       | Signing key for auth tokens. Use `openssl rand -hex 32`. |
| `DEEPSEEK_API_KEY` | ✅       | DeepSeek chat-completion key.                   |
| `SILICONFLOW_API_KEY` | ✅    | SiliconFlow key for the embedding endpoint.     |
| `DEEPSEEK_MODEL`   | ⬜       | Defaults to `deepseek-v4-flash`.                |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | ⬜ | Bootstrap an admin on first run. Otherwise register via UI. |
| `RESEND_API_KEY`   | ⬜       | Enables email verification & password reset.    |
| `ALLOWED_ORIGINS`  | ⬜       | Comma-separated CORS allowlist.                 |

## Project layout

```
.
├── backend/      FastAPI app, LangGraph agent, Postgres migrations
├── frontend/     React app (Vite)
├── docker-compose.yml
└── .env.example
```

## Credits

- Card data and images © Wizards of the Coast.
  Provided as CC0 bulk data by [Scryfall](https://scryfall.com/docs/api/bulk-data).
- Mana symbols: [`mana-font`](https://github.com/andrewgioia/mana) and
  [`keyrune`](https://github.com/andrewgioia/keyrune) by Andrew Gioia.
- Built with the [LangChain](https://github.com/langchain-ai/langchain) /
  [LangGraph](https://github.com/langchain-ai/langgraph) ecosystem.

## Disclaimer

Unofficial Fan Content permitted under the Wizards of the Coast Fan Content
Policy. Not approved or endorsed by Wizards. *Magic: The Gathering* and its
related properties are © Wizards of the Coast LLC.

## License

[MIT](LICENSE).
