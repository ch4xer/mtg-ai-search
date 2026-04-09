# User Login & Deck Management Design

## Overview

Add user authentication and deck management to the MTG AI Card Search app. Users can register/login, create decks, and drag search result cards into decks via a sidebar.

## Decisions

- **Auth**: Username + password, JWT tokens (HS256), bcrypt hashing
- **Drag & drop**: react-dnd + HTML5 backend
- **Routing**: react-router-dom
- **Backend style**: Hand-written asyncpg queries (consistent with existing codebase)
- **No card limits**: Unlimited decks, unlimited cards per deck, unlimited copies

## Database Schema

Three new tables in the existing PostgreSQL + pgvector database.

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE decks (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE deck_cards (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id  TEXT NOT NULL REFERENCES cards(id),
    quantity INT NOT NULL DEFAULT 1,
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(deck_id, card_id)
);
```

Indexes: `users(username)`, `decks(user_id)`, `deck_cards(deck_id)`.

## Backend API

### New Files

- `app/auth.py` — JWT utilities, password hashing, auth dependency
- `app/decks.py` — Deck CRUD router

### New Dependencies

- `bcrypt` — password hashing
- `python-jose[cryptography]` — JWT encoding/decoding

### Auth Endpoints (prefix: `/api/auth`)

| Method | Path | Body | Response | Auth |
|--------|------|------|----------|------|
| POST | `/register` | `{username, password}` | `{access_token, refresh_token, user: {id, username}}` | No |
| POST | `/login` | `{username, password}` | `{access_token, refresh_token, user: {id, username}}` | No |
| POST | `/refresh` | `{refresh_token}` | `{access_token}` | No |

- Access token: 30 min expiry, contains `{sub: user_id, type: "access"}`
- Refresh token: 7 day expiry, contains `{sub: user_id, type: "refresh"}`
- JWT secret from `JWT_SECRET` env var

### Deck Endpoints (prefix: `/api/decks`)

All require `Authorization: Bearer <access_token>` header.

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/` | — | `[{id, name, card_count, created_at, updated_at}]` |
| POST | `/` | `{name}` | `{id, name, created_at}` |
| PUT | `/{deck_id}` | `{name}` | `{id, name, updated_at}` |
| DELETE | `/{deck_id}` | — | `204 No Content` |
| GET | `/{deck_id}/cards` | — | `[{card: <full card data>, quantity, added_at}]` |
| POST | `/{deck_id}/cards` | `{card_id, quantity?}` | `{card_id, quantity}` |
| DELETE | `/{deck_id}/cards/{card_id}` | — | `204 No Content` |

All deck operations verify ownership (deck.user_id == current user).

### Auth Dependency

FastAPI dependency `get_current_user` extracts and validates JWT from `Authorization` header, returns user_id. Used on all `/api/decks` routes.

### Database Functions (added to `app/db.py`)

- `create_user(username, password_hash) -> dict`
- `get_user_by_username(username) -> dict | None`
- `create_deck(user_id, name) -> dict`
- `get_user_decks(user_id) -> list[dict]`
- `get_deck(deck_id) -> dict | None`
- `update_deck(deck_id, name) -> dict`
- `delete_deck(deck_id)`
- `get_deck_cards(deck_id) -> list[dict]`
- `add_card_to_deck(deck_id, card_id, quantity) -> dict` — uses `INSERT ... ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity`
- `remove_card_from_deck(deck_id, card_id)`

### Schema Creation

Add table creation SQL to `seed_pg.py`'s `create_schema()` function using `CREATE TABLE IF NOT EXISTS`, so existing data is untouched.

## Frontend Architecture

### New Dependencies

- `react-router-dom` — client-side routing
- `react-dnd` + `react-dnd-html5-backend` — drag and drop

### Routing

| Path | Component | Auth Required |
|------|-----------|---------------|
| `/` | `SearchPage` (existing App content) | No |
| `/login` | `LoginPage` | No |
| `/decks` | `DecksPage` | Yes |
| `/decks/:id` | `DeckDetailPage` | Yes |

`App.jsx` becomes the router shell. Existing search UI moves into `SearchPage`. Protected routes redirect to `/login` if not authenticated.

### Auth State

- JWT tokens stored in `localStorage` (`mtg-access-token`, `mtg-refresh-token`)
- Auth context (`AuthContext`) provides: `user`, `login()`, `logout()`, `register()`
- `apiFetch()` utility wraps `fetch` to auto-attach `Authorization` header and handle 401 (auto-refresh or redirect to login)

### Component Structure

```
App.jsx (Router + AuthProvider + DndProvider)
├── Header.jsx (updated: login/logout/my-decks links)
├── SearchPage.jsx (existing search + sidebar when logged in)
│   ├── SearchBar.jsx (unchanged)
│   ├── CardGrid.jsx (cards become drag sources)
│   │   └── DraggableCard.jsx (wraps CardItem with useDrag)
│   └── DeckSidebar.jsx (drop targets, collapsible)
│       └── DeckDropTarget.jsx (individual deck drop zone)
├── LoginPage.jsx (login/register forms)
├── DecksPage.jsx (deck list grid)
│   └── DeckCard.jsx (deck summary card)
└── DeckDetailPage.jsx (deck contents)
    └── DeckCardItem.jsx (card + quantity controls + remove)
```

### Search Page Sidebar

- Right side, 280px wide, collapsible via toggle button
- Shows only when user is logged in
- Lists all decks with name and card count
- "New Deck" button with inline name input at top
- Each deck is a `DeckDropTarget`: highlights on drag hover, shows "Drop to add" text
- After successful drop: brief toast notification "Added [card name] to [deck name]"

### Drag & Drop Flow

1. `DraggableCard` wraps `CardItem`, provides `{type: "CARD", card_id, card_name}` via `useDrag`
2. During drag: card shows semi-transparent preview, sidebar deck targets highlight
3. `DeckDropTarget` uses `useDrop`, accepts type "CARD"
4. On drop: calls `POST /api/decks/{deck_id}/cards` with `{card_id}`
5. If card already in deck: backend increments quantity, frontend shows toast
6. On error (e.g. not logged in): shows error toast

### Login/Register Page

Single page with tab switch between "Login" and "Register":
- Login: username + password fields
- Register: username + password + confirm password fields
- Medieval fantasy styling consistent with existing theme
- On success: redirect to `/` (search page)

### Decks List Page (`/decks`)

- Grid of deck summary cards (reuses card grid layout)
- Each card shows: deck name, card count, created date
- "New Deck" button opens inline creation
- Click deck card navigates to `/decks/:id`

### Deck Detail Page (`/decks/:id`)

- Header: editable deck name, total card count, delete button (with confirmation)
- Card list: CardItem components with quantity display (+/- buttons) and remove button
- Uses existing `imageMode` setting for card images
- Back button to `/decks`

### Toast Notifications

Simple self-managed toast component (no library). Renders fixed-position messages that auto-dismiss after 3 seconds. Used for: add-to-deck confirmation, errors, deck creation confirmation.
