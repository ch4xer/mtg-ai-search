# User Login & Deck Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user registration/login and deck management with drag-and-drop card adding to the MTG AI Card Search app.

**Architecture:** Backend adds JWT auth (bcrypt + python-jose) and deck CRUD endpoints to existing FastAPI + asyncpg stack. Frontend adds react-router for page routing, react-dnd for drag-and-drop, AuthContext for auth state, and new pages for login, deck list, and deck detail.

**Tech Stack:** FastAPI, asyncpg, bcrypt, python-jose, React 18, react-router-dom, react-dnd, react-dnd-html5-backend

---

## File Structure

### Backend — New Files
- `backend/app/auth.py` — JWT token creation/validation, password hashing, FastAPI `get_current_user` dependency
- `backend/app/decks.py` — FastAPI APIRouter with deck and deck-card CRUD endpoints

### Backend — Modified Files
- `backend/app/db.py` — Add user and deck database query functions
- `backend/app/main.py` — Register auth and decks routers, add schema creation to lifespan
- `backend/pyproject.toml` — Add bcrypt, python-jose dependencies
- `backend/scripts/seed_pg.py` — Add users/decks/deck_cards table creation to `create_schema()`
- `backend/.env` — Add JWT_SECRET
- `docker-compose.yml` — Pass JWT_SECRET env var to backend

### Frontend — New Files
- `frontend/src/contexts/AuthContext.jsx` — Auth state provider with login/register/logout/apiFetch
- `frontend/src/pages/SearchPage.jsx` — Existing search UI extracted from App.jsx
- `frontend/src/pages/LoginPage.jsx` — Login/register forms
- `frontend/src/pages/DecksPage.jsx` — User's deck list grid
- `frontend/src/pages/DeckDetailPage.jsx` — Single deck contents with card management
- `frontend/src/components/DraggableCard.jsx` — Wraps CardItem with useDrag
- `frontend/src/components/DeckSidebar.jsx` — Collapsible sidebar with deck list drop targets
- `frontend/src/components/DeckDropTarget.jsx` — Individual deck drop zone
- `frontend/src/components/Toast.jsx` — Auto-dismissing toast notifications

### Frontend — Modified Files
- `frontend/src/main.jsx` — Wrap App with BrowserRouter
- `frontend/src/App.jsx` — Becomes router shell with AuthProvider + DndProvider
- `frontend/src/App.css` — Add styles for new components
- `frontend/src/components/Header.jsx` — Add login/logout/my-decks navigation
- `frontend/src/components/CardGrid.jsx` — Use DraggableCard instead of CardItem when logged in
- `frontend/package.json` — Add react-router-dom, react-dnd dependencies

---

## Task 1: Backend Dependencies & Database Schema

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/.env`
- Modify: `docker-compose.yml`
- Modify: `backend/scripts/seed_pg.py:42-86`

- [ ] **Step 1: Add backend dependencies**

In `backend/pyproject.toml`, add to dependencies list:

```toml
    "bcrypt>=4.0.0",
    "python-jose[cryptography]>=3.3.0",
```

- [ ] **Step 2: Add JWT_SECRET to .env**

Append to `backend/.env`:

```
JWT_SECRET=REDACTED-JWT-SECRET
```

- [ ] **Step 3: Pass JWT_SECRET in docker-compose.yml**

In `docker-compose.yml`, under `mtg-backend.environment`, add:

```yaml
      JWT_SECRET: ${JWT_SECRET}
```

- [ ] **Step 4: Add user/deck tables to seed_pg.py create_schema()**

In `backend/scripts/seed_pg.py`, inside `create_schema()`, after the `keyword_abilities` table creation and before the index creation lines, add:

```python
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS decks (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deck_cards (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  TEXT NOT NULL REFERENCES cards(id),
                quantity INT NOT NULL DEFAULT 1,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id)")
```

- [ ] **Step 5: Run uv lock and verify**

```bash
cd backend && uv lock
```

Expected: resolves successfully with bcrypt and python-jose added.

- [ ] **Step 6: Create tables in running database**

```bash
cd backend && uv run python -c "
from scripts.seed_pg import get_conn, create_schema
conn = get_conn()
create_schema(conn)
conn.close()
print('Schema created successfully')
"
```

Expected: "Schema created successfully" — tables created without affecting existing card data.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/.env docker-compose.yml backend/scripts/seed_pg.py
git commit -m "feat: add user/deck database schema and auth dependencies"
```

---

## Task 2: Backend Auth Module

**Files:**
- Create: `backend/app/auth.py`

- [ ] **Step 1: Create auth.py with JWT and password utilities**

Create `backend/app/auth.py`:

```python
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "type": "access", "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "type": "refresh", "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> str:
    """Decode and validate a JWT token. Returns user_id."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """FastAPI dependency that extracts user_id from Bearer token."""
    return decode_token(credentials.credentials, expected_type="access")
```

- [ ] **Step 2: Verify module imports**

```bash
cd backend && uv run python -c "from app.auth import hash_password, verify_password, create_access_token, decode_token; print('auth module OK')"
```

Expected: "auth module OK"

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth.py
git commit -m "feat: add JWT auth module with password hashing"
```

---

## Task 3: Backend User & Deck Database Functions

**Files:**
- Modify: `backend/app/db.py`

- [ ] **Step 1: Add user database functions**

Append to `backend/app/db.py`:

```python
# ── User functions ──────────────────────────────────────────────────────


async def create_user(username: str, password_hash: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id, username, created_at",
        username, password_hash,
    )
    return {"id": str(row["id"]), "username": row["username"]}


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, password_hash FROM users WHERE username = $1",
        username,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "password_hash": row["password_hash"]}
```

- [ ] **Step 2: Add deck database functions**

Append to `backend/app/db.py`:

```python
# ── Deck functions ──────────────────────────────────────────────────────


async def create_deck(user_id: str, name: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO decks (user_id, name) VALUES ($1::uuid, $2) RETURNING id, name, created_at",
        user_id, name,
    )
    return {"id": str(row["id"]), "name": row["name"], "created_at": row["created_at"].isoformat()}


async def get_user_decks(user_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT d.id, d.name, d.created_at, d.updated_at,
                  COALESCE(SUM(dc.quantity), 0) AS card_count
           FROM decks d
           LEFT JOIN deck_cards dc ON dc.deck_id = d.id
           WHERE d.user_id = $1::uuid
           GROUP BY d.id
           ORDER BY d.updated_at DESC""",
        user_id,
    )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "card_count": int(r["card_count"]),
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def get_deck(deck_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT id, user_id, name, created_at, updated_at FROM decks WHERE id = $1::uuid", deck_id)
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def update_deck(deck_id: str, name: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE decks SET name = $1, updated_at = now() WHERE id = $2::uuid RETURNING id, name, updated_at",
        name, deck_id,
    )
    return {"id": str(row["id"]), "name": row["name"], "updated_at": row["updated_at"].isoformat()}


async def delete_deck(deck_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE id = $1::uuid", deck_id)


async def get_deck_cards(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.card_id, dc.quantity, dc.added_at, c.data
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at DESC""",
        deck_id,
    )
    return [
        {
            "card": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "quantity": r["quantity"],
            "added_at": r["added_at"].isoformat(),
        }
        for r in rows
    ]


async def add_card_to_deck(deck_id: str, card_id: str, quantity: int = 1) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO deck_cards (deck_id, card_id, quantity)
           VALUES ($1::uuid, $2, $3)
           ON CONFLICT (deck_id, card_id)
           DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity
           RETURNING card_id, quantity""",
        deck_id, card_id, quantity,
    )
    return {"card_id": row["card_id"], "quantity": row["quantity"]}


async def remove_card_from_deck(deck_id: str, card_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2", deck_id, card_id)
```

- [ ] **Step 3: Verify imports work**

```bash
cd backend && uv run python -c "from app.db import create_user, get_user_by_username, create_deck, get_user_decks, get_deck, update_deck, delete_deck, get_deck_cards, add_card_to_deck, remove_card_from_deck; print('db functions OK')"
```

Expected: "db functions OK"

- [ ] **Step 4: Commit**

```bash
git add backend/app/db.py
git commit -m "feat: add user and deck database query functions"
```

---

## Task 4: Backend Auth & Deck API Routers

**Files:**
- Create: `backend/app/decks.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create decks.py with auth and deck endpoints**

Create `backend/app/decks.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .db import (
    add_card_to_deck,
    create_deck,
    create_user,
    delete_deck,
    get_deck,
    get_deck_cards,
    get_user_by_username,
    get_user_decks,
    remove_card_from_deck,
    update_deck,
)

# ── Auth Router ─────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@auth_router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = await get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    pw_hash = hash_password(req.password)
    user = await create_user(req.username, pw_hash)
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user,
    )


@auth_router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user_info = {"id": user["id"], "username": user["username"]}
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user_info,
    )


@auth_router.post("/refresh")
async def refresh(req: RefreshRequest):
    user_id = decode_token(req.refresh_token, expected_type="refresh")
    return {"access_token": create_access_token(user_id)}


# ── Deck Router ─────────────────────────────────────────────────────────

deck_router = APIRouter(prefix="/api/decks", tags=["decks"])


class CreateDeckRequest(BaseModel):
    name: str


class UpdateDeckRequest(BaseModel):
    name: str


class AddCardRequest(BaseModel):
    card_id: str
    quantity: int = 1


async def _verify_deck_ownership(deck_id: str, user_id: str) -> dict:
    """Fetch deck and verify it belongs to the user. Raises 404 if not found or not owned."""
    deck = await get_deck(deck_id)
    if not deck or deck["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@deck_router.get("/")
async def list_decks(user_id: str = Depends(get_current_user)):
    return await get_user_decks(user_id)


@deck_router.post("/", status_code=201)
async def create_deck_endpoint(req: CreateDeckRequest, user_id: str = Depends(get_current_user)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return await create_deck(user_id, req.name.strip())


@deck_router.put("/{deck_id}")
async def update_deck_endpoint(deck_id: str, req: UpdateDeckRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return await update_deck(deck_id, req.name.strip())


@deck_router.delete("/{deck_id}", status_code=204)
async def delete_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    await delete_deck(deck_id)


@deck_router.get("/{deck_id}/cards")
async def list_deck_cards(deck_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    return await get_deck_cards(deck_id)


@deck_router.post("/{deck_id}/cards", status_code=201)
async def add_card(deck_id: str, req: AddCardRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    return await add_card_to_deck(deck_id, req.card_id, req.quantity)


@deck_router.delete("/{deck_id}/cards/{card_id}", status_code=204)
async def remove_card(deck_id: str, card_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    await remove_card_from_deck(deck_id, card_id)
```

- [ ] **Step 2: Register routers in main.py**

In `backend/app/main.py`, add import at top:

```python
from .decks import auth_router, deck_router
```

After the `app.add_middleware(...)` block, add:

```python
app.include_router(auth_router)
app.include_router(deck_router)
```

- [ ] **Step 3: Add schema creation to lifespan**

In `backend/app/main.py`, update the `_ensure_data` function. After `pool = await get_pool()` in the lifespan, add schema creation for user/deck tables so they're created even without running the full seed:

Replace the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    # Ensure user/deck tables exist (idempotent)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS decks (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS deck_cards (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  TEXT NOT NULL REFERENCES cards(id),
                quantity INT NOT NULL DEFAULT 1,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id)
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);
            CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id);
        """)
    await _ensure_data(pool)
    yield
    await close_pool()
```

- [ ] **Step 4: Verify server starts**

```bash
cd backend && timeout 5 uv run uvicorn app.main:app --port 8001 2>&1 || true
```

Expected: server starts without import errors (will timeout after 5s, that's OK).

- [ ] **Step 5: Commit**

```bash
git add backend/app/decks.py backend/app/main.py
git commit -m "feat: add auth and deck CRUD API endpoints"
```

---

## Task 5: Frontend Dependencies & Routing Setup

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/pages/SearchPage.jsx`

- [ ] **Step 1: Install frontend dependencies**

```bash
cd frontend && npm install react-router-dom react-dnd react-dnd-html5-backend
```

- [ ] **Step 2: Create SearchPage.jsx by extracting from App.jsx**

Create `frontend/src/pages/SearchPage.jsx`:

```jsx
import { useState } from "react";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";

function SearchPage({ imageMode, onToggleImageMode }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (query) => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <SearchBar onSearch={handleSearch} loading={loading} imageMode={imageMode} onToggleImageMode={onToggleImageMode} />
      {loading && (
        <div className="loading">
          <div className="loading-spinner" />
          <p>AI正在为你搜寻卡牌...</p>
        </div>
      )}
      {!loading && searched && results.length === 0 && (
        <div className="no-results">
          <p>未找到匹配的卡牌，请尝试其他描述</p>
        </div>
      )}
      {!loading && results.length > 0 && <CardGrid cards={results} imageMode={imageMode} />}
    </>
  );
}

export default SearchPage;
```

- [ ] **Step 3: Update main.jsx to add BrowserRouter**

Replace `frontend/src/main.jsx`:

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 4: Update App.jsx to be router shell**

Replace `frontend/src/App.jsx`:

```jsx
import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import Header from "./components/Header.jsx";
import SearchPage from "./pages/SearchPage.jsx";

function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("mtg-theme") || "dark";
  });
  const [imageMode, setImageMode] = useState(() => {
    return localStorage.getItem("mtg-image-mode") || "border_crop";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("mtg-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const toggleImageMode = () => {
    setImageMode((prev) => {
      const next = prev === "border_crop" ? "art_crop" : "border_crop";
      localStorage.setItem("mtg-image-mode", next);
      return next;
    });
  };

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SearchPage imageMode={imageMode} onToggleImageMode={toggleImageMode} />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: build succeeds, existing search functionality preserved.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.jsx frontend/src/App.jsx frontend/src/pages/SearchPage.jsx
git commit -m "feat: add react-router, extract SearchPage from App"
```

---

## Task 6: Frontend Auth Context

**Files:**
- Create: `frontend/src/contexts/AuthContext.jsx`

- [ ] **Step 1: Create AuthContext.jsx**

Create `frontend/src/contexts/AuthContext.jsx`:

```jsx
import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function apiFetch(path, options = {}) {
  const token = localStorage.getItem("mtg-access-token");
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(path, { ...options, headers }).then(async (res) => {
    if (res.status === 401 && token) {
      // Try refresh
      const refreshToken = localStorage.getItem("mtg-refresh-token");
      if (refreshToken) {
        const refreshRes = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          localStorage.setItem("mtg-access-token", data.access_token);
          headers["Authorization"] = `Bearer ${data.access_token}`;
          return fetch(path, { ...options, headers });
        }
      }
      // Refresh failed — clear auth
      localStorage.removeItem("mtg-access-token");
      localStorage.removeItem("mtg-refresh-token");
      localStorage.removeItem("mtg-user");
      window.location.href = "/login";
    }
    return res;
  });
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("mtg-user");
    return stored ? JSON.parse(stored) : null;
  });

  const login = useCallback(async (username, password) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("mtg-access-token", data.access_token);
    localStorage.setItem("mtg-refresh-token", data.refresh_token);
    localStorage.setItem("mtg-user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (username, password) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    localStorage.setItem("mtg-access-token", data.access_token);
    localStorage.setItem("mtg-refresh-token", data.refresh_token);
    localStorage.setItem("mtg-user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("mtg-access-token");
    localStorage.removeItem("mtg-refresh-token");
    localStorage.removeItem("mtg-user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

- [ ] **Step 2: Wrap App with AuthProvider**

In `frontend/src/App.jsx`, add import:

```jsx
import { AuthProvider } from "./contexts/AuthContext.jsx";
```

Wrap the return JSX — the outermost `<div className="app">` becomes:

```jsx
  return (
    <AuthProvider>
      <div className="app">
        <Header theme={theme} onToggleTheme={toggleTheme} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<SearchPage imageMode={imageMode} onToggleImageMode={toggleImageMode} />} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  );
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/contexts/AuthContext.jsx frontend/src/App.jsx
git commit -m "feat: add AuthContext with login/register/logout and token refresh"
```

---

## Task 7: Login Page

**Files:**
- Create: `frontend/src/pages/LoginPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create LoginPage.jsx**

Create `frontend/src/pages/LoginPage.jsx`:

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (isRegister && password !== confirmPassword) {
      setError("密码不匹配");
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register(username, password);
      } else {
        await login(username, password);
      }
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h2 className="login-title">{isRegister ? "注册" : "登录"}</h2>
        <div className="login-tabs">
          <button className={`login-tab ${!isRegister ? "active" : ""}`} onClick={() => { setIsRegister(false); setError(""); }}>
            登录
          </button>
          <button className={`login-tab ${isRegister ? "active" : ""}`} onClick={() => { setIsRegister(true); setError(""); }}>
            注册
          </button>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="login-input"
            required
          />
          <input
            type="password"
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="login-input"
            required
          />
          {isRegister && (
            <input
              type="password"
              placeholder="确认密码"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="login-input"
              required
            />
          )}
          {error && <p className="login-error">{error}</p>}
          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? "请稍候..." : isRegister ? "注册" : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
```

- [ ] **Step 2: Add login route to App.jsx**

In `frontend/src/App.jsx`, add import:

```jsx
import LoginPage from "./pages/LoginPage.jsx";
```

Add route inside `<Routes>`:

```jsx
<Route path="/login" element={<LoginPage />} />
```

- [ ] **Step 3: Add login page styles to App.css**

Append to `frontend/src/App.css`:

```css
/* ===== Login Page ===== */
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 2.5rem 2rem;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 4px 16px var(--shadow);
}

.login-title {
  font-family: "Cinzel", serif;
  font-size: 1.6rem;
  color: var(--accent);
  text-align: center;
  margin-bottom: 1.5rem;
}

.login-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
}

.login-tab {
  flex: 1;
  padding: 0.6rem;
  font-family: "Cinzel", serif;
  font-size: 0.9rem;
  font-weight: 600;
  background: transparent;
  color: var(--text-muted);
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.login-tab.active {
  background: var(--accent);
  color: #1a1a1a;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.login-input {
  padding: 0.85rem 1rem;
  font-family: "Crimson Text", Georgia, serif;
  font-size: 1.05rem;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 2px solid var(--border-subtle);
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s ease;
}

.login-input:focus {
  border-color: var(--accent);
}

.login-error {
  color: #d3202a;
  font-size: 0.9rem;
  text-align: center;
}

.login-submit {
  padding: 0.85rem;
  font-family: "Cinzel", serif;
  font-size: 1rem;
  font-weight: 600;
  background: var(--accent);
  color: #1a1a1a;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.login-submit:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.login-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/LoginPage.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add login/register page with medieval fantasy styling"
```

---

## Task 8: Header Navigation Update

**Files:**
- Modify: `frontend/src/components/Header.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Update Header.jsx with auth-aware navigation**

Replace `frontend/src/components/Header.jsx`:

```jsx
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

function Header({ theme, onToggleTheme }) {
  const { user, logout } = useAuth();

  return (
    <header className="header">
      <div className="header-inner">
        <Link to="/" className="logo-link">
          <div className="logo">
            <h1>MTG Card Search</h1>
            <p className="subtitle">AI-Powered Card Finder</p>
          </div>
        </Link>
        <nav className="header-nav">
          {user ? (
            <>
              <span className="header-username">{user.username}</span>
              <Link to="/decks" className="header-link">我的卡组</Link>
              <button className="header-btn" onClick={logout}>登出</button>
            </>
          ) : (
            <Link to="/login" className="header-link">登录</Link>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </nav>
      </div>
    </header>
  );
}

export default Header;
```

- [ ] **Step 2: Add header nav styles to App.css**

Append to `frontend/src/App.css`:

```css
/* ===== Header Nav ===== */
.logo-link {
  text-decoration: none;
  color: inherit;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-username {
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  color: var(--accent);
  font-weight: 600;
}

.header-link {
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-decoration: none;
  padding: 0.4rem 0.8rem;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.header-link:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.header-btn {
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s ease;
}

.header-btn:hover {
  color: var(--accent);
}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Header.jsx frontend/src/App.css
git commit -m "feat: add auth-aware header navigation"
```

---

## Task 9: Toast Component

**Files:**
- Create: `frontend/src/components/Toast.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create Toast.jsx**

Create `frontend/src/components/Toast.jsx`:

```jsx
import { useState, useCallback, createContext, useContext } from "react";

const ToastContext = createContext(null);

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "success") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

- [ ] **Step 2: Add toast styles**

Append to `frontend/src/App.css`:

```css
/* ===== Toast ===== */
.toast-container {
  position: fixed;
  top: 80px;
  right: 1.5rem;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}

.toast {
  padding: 0.75rem 1.25rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-family: "Crimson Text", serif;
  box-shadow: 0 4px 12px var(--shadow-strong);
  animation: toast-in 0.3s ease;
  pointer-events: auto;
}

.toast-success {
  background: var(--accent);
  color: #1a1a1a;
}

.toast-error {
  background: #d3202a;
  color: #fff;
}

@keyframes toast-in {
  from { opacity: 0; transform: translateX(50px); }
  to { opacity: 1; transform: translateX(0); }
}
```

- [ ] **Step 3: Wrap App with ToastProvider**

In `frontend/src/App.jsx`, add import:

```jsx
import { ToastProvider } from "./components/Toast.jsx";
```

Wrap inside AuthProvider:

```jsx
  return (
    <AuthProvider>
      <ToastProvider>
        <div className="app">
          ...
        </div>
      </ToastProvider>
    </AuthProvider>
  );
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Toast.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add toast notification component"
```

---

## Task 10: Drag & Drop — DraggableCard and DeckSidebar

**Files:**
- Create: `frontend/src/components/DraggableCard.jsx`
- Create: `frontend/src/components/DeckDropTarget.jsx`
- Create: `frontend/src/components/DeckSidebar.jsx`
- Modify: `frontend/src/components/CardGrid.jsx`
- Modify: `frontend/src/pages/SearchPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create DraggableCard.jsx**

Create `frontend/src/components/DraggableCard.jsx`:

```jsx
import { useDrag } from "react-dnd";
import CardItem from "./CardItem.jsx";

function DraggableCard({ card, imageMode }) {
  const [{ isDragging }, dragRef] = useDrag({
    type: "CARD",
    item: { card_id: card.id, card_name: card.name },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  return (
    <div ref={dragRef} style={{ opacity: isDragging ? 0.5 : 1, cursor: "grab" }}>
      <CardItem card={card} imageMode={imageMode} />
    </div>
  );
}

export default DraggableCard;
```

- [ ] **Step 2: Create DeckDropTarget.jsx**

Create `frontend/src/components/DeckDropTarget.jsx`:

```jsx
import { useDrop } from "react-dnd";

function DeckDropTarget({ deck, onDrop }) {
  const [{ isOver }, dropRef] = useDrop({
    accept: "CARD",
    drop: (item) => onDrop(deck, item),
    collect: (monitor) => ({
      isOver: monitor.isOver(),
    }),
  });

  return (
    <div ref={dropRef} className={`deck-drop-target ${isOver ? "drag-over" : ""}`}>
      <span className="deck-drop-name">{deck.name}</span>
      <span className="deck-drop-count">{deck.card_count} 张</span>
      {isOver && <span className="deck-drop-hint">松开添加</span>}
    </div>
  );
}

export default DeckDropTarget;
```

- [ ] **Step 3: Create DeckSidebar.jsx**

Create `frontend/src/components/DeckSidebar.jsx`:

```jsx
import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../contexts/AuthContext.jsx";
import { useToast } from "./Toast.jsx";
import DeckDropTarget from "./DeckDropTarget.jsx";

function DeckSidebar({ collapsed, onToggle }) {
  const [decks, setDecks] = useState([]);
  const [newDeckName, setNewDeckName] = useState("");
  const [creating, setCreating] = useState(false);
  const addToast = useToast();

  const fetchDecks = useCallback(async () => {
    const res = await apiFetch("/api/decks");
    if (res.ok) {
      setDecks(await res.json());
    }
  }, []);

  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  const handleCreateDeck = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) return;
    setCreating(true);
    const res = await apiFetch("/api/decks", {
      method: "POST",
      body: JSON.stringify({ name: newDeckName.trim() }),
    });
    if (res.ok) {
      setNewDeckName("");
      addToast("卡组创建成功");
      fetchDecks();
    }
    setCreating(false);
  };

  const handleDrop = async (deck, item) => {
    const res = await apiFetch(`/api/decks/${deck.id}/cards`, {
      method: "POST",
      body: JSON.stringify({ card_id: item.card_id }),
    });
    if (res.ok) {
      addToast(`已添加 ${item.card_name} 到 ${deck.name}`);
      fetchDecks();
    } else {
      addToast("添加失败", "error");
    }
  };

  return (
    <aside className={`deck-sidebar ${collapsed ? "collapsed" : ""}`}>
      <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? "展开卡组栏" : "收起卡组栏"}>
        {collapsed ? "◀" : "▶"}
      </button>
      {!collapsed && (
        <div className="sidebar-content">
          <h3 className="sidebar-title">我的卡组</h3>
          <form className="sidebar-create" onSubmit={handleCreateDeck}>
            <input
              type="text"
              placeholder="新卡组名称..."
              value={newDeckName}
              onChange={(e) => setNewDeckName(e.target.value)}
              className="sidebar-input"
            />
            <button type="submit" className="sidebar-create-btn" disabled={creating || !newDeckName.trim()}>+</button>
          </form>
          <div className="sidebar-decks">
            {decks.map((deck) => (
              <DeckDropTarget key={deck.id} deck={deck} onDrop={handleDrop} />
            ))}
            {decks.length === 0 && <p className="sidebar-empty">还没有卡组，创建一个吧</p>}
          </div>
        </div>
      )}
    </aside>
  );
}

export default DeckSidebar;
```

- [ ] **Step 4: Update CardGrid.jsx to support drag mode**

Replace `frontend/src/components/CardGrid.jsx`:

```jsx
import CardItem from "./CardItem.jsx";
import DraggableCard from "./DraggableCard.jsx";

function CardGrid({ cards, imageMode, draggable }) {
  return (
    <div className="card-grid">
      {cards.map((card, index) =>
        draggable ? (
          <DraggableCard key={`${card.name}-${index}`} card={card} imageMode={imageMode} />
        ) : (
          <CardItem key={`${card.name}-${index}`} card={card} imageMode={imageMode} />
        )
      )}
    </div>
  );
}

export default CardGrid;
```

- [ ] **Step 5: Update SearchPage.jsx with sidebar**

Replace `frontend/src/pages/SearchPage.jsx`:

```jsx
import { useState } from "react";
import { useAuth } from "../contexts/AuthContext.jsx";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";
import DeckSidebar from "../components/DeckSidebar.jsx";

function SearchPage({ imageMode, onToggleImageMode }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { user } = useAuth();

  const handleSearch = async (query) => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-page-layout">
      <div className="search-main">
        <SearchBar onSearch={handleSearch} loading={loading} imageMode={imageMode} onToggleImageMode={onToggleImageMode} />
        {loading && (
          <div className="loading">
            <div className="loading-spinner" />
            <p>AI正在为你搜寻卡牌...</p>
          </div>
        )}
        {!loading && searched && results.length === 0 && (
          <div className="no-results">
            <p>未找到匹配的卡牌，请尝试其他描述</p>
          </div>
        )}
        {!loading && results.length > 0 && <CardGrid cards={results} imageMode={imageMode} draggable={!!user} />}
      </div>
      {user && <DeckSidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />}
    </div>
  );
}

export default SearchPage;
```

- [ ] **Step 6: Wrap App with DndProvider**

In `frontend/src/App.jsx`, add imports:

```jsx
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
```

Wrap inside ToastProvider:

```jsx
  return (
    <AuthProvider>
      <ToastProvider>
        <DndProvider backend={HTML5Backend}>
          <div className="app">
            ...
          </div>
        </DndProvider>
      </ToastProvider>
    </AuthProvider>
  );
```

- [ ] **Step 7: Add sidebar and drag-drop styles**

Append to `frontend/src/App.css`:

```css
/* ===== Search Page Layout ===== */
.search-page-layout {
  display: flex;
  gap: 1rem;
}

.search-main {
  flex: 1;
  min-width: 0;
}

/* ===== Deck Sidebar ===== */
.deck-sidebar {
  width: 280px;
  flex-shrink: 0;
  position: relative;
}

.deck-sidebar.collapsed {
  width: 32px;
}

.sidebar-toggle {
  position: absolute;
  top: 0;
  left: -16px;
  width: 32px;
  height: 32px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 50%;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  z-index: 2;
  transition: all 0.2s ease;
}

.sidebar-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.sidebar-content {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1rem;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
}

.sidebar-title {
  font-family: "Cinzel", serif;
  font-size: 1rem;
  color: var(--accent);
  margin-bottom: 0.75rem;
}

.sidebar-create {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.sidebar-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  font-family: "Crimson Text", serif;
  font-size: 0.9rem;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  outline: none;
}

.sidebar-input:focus {
  border-color: var(--accent);
}

.sidebar-create-btn {
  width: 36px;
  height: 36px;
  background: var(--accent);
  color: #1a1a1a;
  border: none;
  border-radius: 6px;
  font-size: 1.2rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s ease;
}

.sidebar-create-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.sidebar-create-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sidebar-decks {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sidebar-empty {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: italic;
  text-align: center;
  padding: 1rem 0;
}

/* ===== Deck Drop Target ===== */
.deck-drop-target {
  padding: 0.75rem;
  background: var(--bg-secondary);
  border: 2px dashed var(--border-subtle);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.2s ease;
  position: relative;
}

.deck-drop-target.drag-over {
  border-color: var(--accent);
  background: var(--card-hover);
  box-shadow: 0 0 8px rgba(201, 169, 89, 0.3);
}

.deck-drop-name {
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.deck-drop-count {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.deck-drop-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(201, 169, 89, 0.15);
  color: var(--accent);
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 6px;
}

/* Sidebar responsive */
@media (max-width: 768px) {
  .deck-sidebar {
    display: none;
  }

  .search-page-layout {
    flex-direction: column;
  }
}
```

- [ ] **Step 8: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/DraggableCard.jsx frontend/src/components/DeckDropTarget.jsx frontend/src/components/DeckSidebar.jsx frontend/src/components/CardGrid.jsx frontend/src/pages/SearchPage.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add drag-and-drop card-to-deck with sidebar"
```

---

## Task 11: Decks List Page

**Files:**
- Create: `frontend/src/pages/DecksPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create DecksPage.jsx**

Create `frontend/src/pages/DecksPage.jsx`:

```jsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../contexts/AuthContext.jsx";
import { useToast } from "../components/Toast.jsx";

function DecksPage() {
  const [decks, setDecks] = useState([]);
  const [newDeckName, setNewDeckName] = useState("");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();
  const addToast = useToast();

  const fetchDecks = async () => {
    const res = await apiFetch("/api/decks");
    if (res.ok) {
      setDecks(await res.json());
    }
  };

  useEffect(() => {
    fetchDecks();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) return;
    setCreating(true);
    const res = await apiFetch("/api/decks", {
      method: "POST",
      body: JSON.stringify({ name: newDeckName.trim() }),
    });
    if (res.ok) {
      setNewDeckName("");
      addToast("卡组创建成功");
      fetchDecks();
    }
    setCreating(false);
  };

  const handleDelete = async (e, deckId, deckName) => {
    e.stopPropagation();
    if (!confirm(`确定要删除卡组 "${deckName}" 吗？`)) return;
    const res = await apiFetch(`/api/decks/${deckId}`, { method: "DELETE" });
    if (res.ok) {
      addToast(`已删除 ${deckName}`);
      fetchDecks();
    }
  };

  return (
    <div className="decks-page">
      <div className="decks-header">
        <h2 className="decks-title">我的卡组</h2>
        <form className="decks-create-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder="新卡组名称..."
            value={newDeckName}
            onChange={(e) => setNewDeckName(e.target.value)}
            className="login-input"
          />
          <button type="submit" className="search-btn" disabled={creating || !newDeckName.trim()}>
            创建
          </button>
        </form>
      </div>
      <div className="decks-grid">
        {decks.map((deck) => (
          <div key={deck.id} className="deck-card" onClick={() => navigate(`/decks/${deck.id}`)}>
            <h3 className="deck-card-name">{deck.name}</h3>
            <p className="deck-card-count">{deck.card_count} 张卡牌</p>
            <p className="deck-card-date">{new Date(deck.created_at).toLocaleDateString()}</p>
            <button
              className="deck-card-delete"
              onClick={(e) => handleDelete(e, deck.id, deck.name)}
              title="删除卡组"
            >
              &times;
            </button>
          </div>
        ))}
        {decks.length === 0 && (
          <div className="decks-empty">
            <p>还没有卡组，创建一个开始收集卡牌吧</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default DecksPage;
```

- [ ] **Step 2: Add decks route to App.jsx**

In `frontend/src/App.jsx`, add import:

```jsx
import DecksPage from "./pages/DecksPage.jsx";
```

Add route inside `<Routes>`:

```jsx
<Route path="/decks" element={<DecksPage />} />
```

- [ ] **Step 3: Add decks page styles**

Append to `frontend/src/App.css`:

```css
/* ===== Decks Page ===== */
.decks-page {
  max-width: 900px;
  margin: 0 auto;
}

.decks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.decks-title {
  font-family: "Cinzel", serif;
  font-size: 1.6rem;
  color: var(--accent);
}

.decks-create-form {
  display: flex;
  gap: 0.75rem;
}

.decks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1.25rem;
}

.deck-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.25s ease;
  position: relative;
  box-shadow: 0 2px 8px var(--shadow);
}

.deck-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px var(--shadow-strong);
  border-color: var(--accent);
}

.deck-card-name {
  font-family: "Cinzel", serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.deck-card-count {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.deck-card-date {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.deck-card-delete {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  background: none;
  border: 1px solid var(--border-subtle);
  border-radius: 50%;
  color: var(--text-muted);
  font-size: 1.1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  opacity: 0;
}

.deck-card:hover .deck-card-delete {
  opacity: 1;
}

.deck-card-delete:hover {
  background: #d3202a;
  color: #fff;
  border-color: #d3202a;
}

.decks-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
  font-style: italic;
  font-size: 1.1rem;
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DecksPage.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add deck list page with create/delete"
```

---

## Task 12: Deck Detail Page

**Files:**
- Create: `frontend/src/pages/DeckDetailPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create DeckDetailPage.jsx**

Create `frontend/src/pages/DeckDetailPage.jsx`:

```jsx
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch } from "../contexts/AuthContext.jsx";
import { useToast } from "../components/Toast.jsx";
import CardItem from "../components/CardItem.jsx";

function DeckDetailPage({ imageMode }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const addToast = useToast();
  const [deck, setDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [editing, setEditing] = useState(false);
  const [deckName, setDeckName] = useState("");

  const fetchDeck = async () => {
    const [deckRes, cardsRes] = await Promise.all([
      apiFetch(`/api/decks`),
      apiFetch(`/api/decks/${id}/cards`),
    ]);
    if (deckRes.ok) {
      const decks = await deckRes.json();
      const d = decks.find((d) => d.id === id);
      if (d) {
        setDeck(d);
        setDeckName(d.name);
      }
    }
    if (cardsRes.ok) {
      setCards(await cardsRes.json());
    }
  };

  useEffect(() => {
    fetchDeck();
  }, [id]);

  const handleRename = async () => {
    if (!deckName.trim() || deckName === deck?.name) {
      setEditing(false);
      return;
    }
    const res = await apiFetch(`/api/decks/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name: deckName.trim() }),
    });
    if (res.ok) {
      setDeck({ ...deck, name: deckName.trim() });
      addToast("卡组已重命名");
    }
    setEditing(false);
  };

  const handleDelete = async () => {
    if (!confirm(`确定要删除卡组 "${deck.name}" 吗？`)) return;
    const res = await apiFetch(`/api/decks/${id}`, { method: "DELETE" });
    if (res.ok) {
      addToast(`已删除 ${deck.name}`);
      navigate("/decks");
    }
  };

  const handleRemoveCard = async (cardId, cardName) => {
    const res = await apiFetch(`/api/decks/${id}/cards/${cardId}`, { method: "DELETE" });
    if (res.ok) {
      addToast(`已移除 ${cardName}`);
      setCards(cards.filter((c) => c.card.id !== cardId));
    }
  };

  const handleQuantityChange = async (cardId, delta) => {
    const entry = cards.find((c) => c.card.id === cardId);
    if (!entry) return;
    const newQty = entry.quantity + delta;
    if (newQty <= 0) {
      handleRemoveCard(cardId, entry.card.name);
      return;
    }
    // Remove then re-add with correct total
    await apiFetch(`/api/decks/${id}/cards/${cardId}`, { method: "DELETE" });
    const res = await apiFetch(`/api/decks/${id}/cards`, {
      method: "POST",
      body: JSON.stringify({ card_id: cardId, quantity: newQty }),
    });
    if (res.ok) {
      setCards(cards.map((c) => c.card.id === cardId ? { ...c, quantity: newQty } : c));
    }
  };

  if (!deck) return <div className="loading"><p>加载中...</p></div>;

  const totalCards = cards.reduce((sum, c) => sum + c.quantity, 0);

  return (
    <div className="deck-detail">
      <div className="deck-detail-header">
        <button className="deck-back-btn" onClick={() => navigate("/decks")}>&larr; 返回</button>
        <div className="deck-detail-title-row">
          {editing ? (
            <input
              className="deck-name-input"
              value={deckName}
              onChange={(e) => setDeckName(e.target.value)}
              onBlur={handleRename}
              onKeyDown={(e) => e.key === "Enter" && handleRename()}
              autoFocus
            />
          ) : (
            <h2 className="deck-detail-name" onClick={() => setEditing(true)}>{deck.name}</h2>
          )}
          <span className="deck-detail-count">{totalCards} 张卡牌</span>
        </div>
        <button className="deck-delete-btn" onClick={handleDelete}>删除卡组</button>
      </div>
      <div className="deck-cards-list">
        {cards.map((entry) => (
          <div key={entry.card.id} className="deck-card-entry">
            <div className="deck-card-image">
              <CardItem card={entry.card} imageMode={imageMode} />
            </div>
            <div className="deck-card-controls">
              <div className="quantity-controls">
                <button className="qty-btn" onClick={() => handleQuantityChange(entry.card.id, -1)}>-</button>
                <span className="qty-value">{entry.quantity}</span>
                <button className="qty-btn" onClick={() => handleQuantityChange(entry.card.id, 1)}>+</button>
              </div>
              <button className="deck-remove-btn" onClick={() => handleRemoveCard(entry.card.id, entry.card.name)}>
                移除
              </button>
            </div>
          </div>
        ))}
        {cards.length === 0 && (
          <div className="decks-empty">
            <p>卡组为空，从搜索页面拖拽卡牌到这里</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default DeckDetailPage;
```

- [ ] **Step 2: Add deck detail route to App.jsx**

In `frontend/src/App.jsx`, add import:

```jsx
import DeckDetailPage from "./pages/DeckDetailPage.jsx";
```

Add route inside `<Routes>`:

```jsx
<Route path="/decks/:id" element={<DeckDetailPage imageMode={imageMode} />} />
```

- [ ] **Step 3: Add deck detail styles**

Append to `frontend/src/App.css`:

```css
/* ===== Deck Detail Page ===== */
.deck-detail {
  max-width: 900px;
  margin: 0 auto;
}

.deck-detail-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

.deck-back-btn {
  font-family: "Cinzel", serif;
  font-size: 0.9rem;
  color: var(--text-secondary);
  background: none;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.deck-back-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.deck-detail-title-row {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 1rem;
}

.deck-detail-name {
  font-family: "Cinzel", serif;
  font-size: 1.5rem;
  color: var(--accent);
  cursor: pointer;
}

.deck-detail-name:hover {
  text-decoration: underline;
}

.deck-name-input {
  font-family: "Cinzel", serif;
  font-size: 1.5rem;
  color: var(--accent);
  background: var(--bg-input);
  border: 2px solid var(--accent);
  border-radius: 6px;
  padding: 0.2rem 0.5rem;
  outline: none;
}

.deck-detail-count {
  font-size: 0.95rem;
  color: var(--text-muted);
}

.deck-delete-btn {
  font-family: "Cinzel", serif;
  font-size: 0.85rem;
  color: #d3202a;
  background: none;
  border: 1px solid #d3202a;
  border-radius: 6px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.deck-delete-btn:hover {
  background: #d3202a;
  color: #fff;
}

/* Deck cards list */
.deck-cards-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.25rem;
}

.deck-card-entry {
  position: relative;
}

.deck-card-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-top: none;
  border-radius: 0 0 12px 12px;
}

.quantity-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.qty-btn {
  width: 28px;
  height: 28px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.qty-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.qty-value {
  font-family: "Cinzel", serif;
  font-size: 1rem;
  font-weight: 700;
  color: var(--accent);
  min-width: 24px;
  text-align: center;
}

.deck-remove-btn {
  font-family: "Crimson Text", serif;
  font-size: 0.85rem;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s ease;
}

.deck-remove-btn:hover {
  color: #d3202a;
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DeckDetailPage.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add deck detail page with card quantity management"
```

---

## Task 13: Protected Routes

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add route protection for deck pages**

In `frontend/src/App.jsx`, add import:

```jsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext.jsx";
```

Replace the Routes section. Move `useAuth()` into the App component body, then use it for protected routes:

```jsx
function App() {
  // ... existing state ...
  const { user } = useAuth();

  // ... existing handlers ...

  return (
    <AuthProvider>
      <ToastProvider>
        <DndProvider backend={HTML5Backend}>
          <div className="app">
            <Header theme={theme} onToggleTheme={toggleTheme} />
            <main className="main-content">
              <Routes>
                <Route path="/" element={<SearchPage imageMode={imageMode} onToggleImageMode={toggleImageMode} />} />
                <Route path="/login" element={user ? <Navigate to="/" /> : <LoginPage />} />
                <Route path="/decks" element={user ? <DecksPage /> : <Navigate to="/login" />} />
                <Route path="/decks/:id" element={user ? <DeckDetailPage imageMode={imageMode} /> : <Navigate to="/login" />} />
              </Routes>
            </main>
          </div>
        </DndProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
```

Note: `useAuth()` is called inside `<AuthProvider>`, so we need to split into an inner component. Restructure:

```jsx
import { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { AuthProvider, useAuth } from "./contexts/AuthContext.jsx";
import { ToastProvider } from "./components/Toast.jsx";
import Header from "./components/Header.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DecksPage from "./pages/DecksPage.jsx";
import DeckDetailPage from "./pages/DeckDetailPage.jsx";

function AppRoutes({ imageMode, onToggleImageMode, theme, onToggleTheme }) {
  const { user } = useAuth();

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={onToggleTheme} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SearchPage imageMode={imageMode} onToggleImageMode={onToggleImageMode} />} />
          <Route path="/login" element={user ? <Navigate to="/" /> : <LoginPage />} />
          <Route path="/decks" element={user ? <DecksPage /> : <Navigate to="/login" />} />
          <Route path="/decks/:id" element={user ? <DeckDetailPage imageMode={imageMode} /> : <Navigate to="/login" />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("mtg-theme") || "dark";
  });
  const [imageMode, setImageMode] = useState(() => {
    return localStorage.getItem("mtg-image-mode") || "border_crop";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("mtg-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const toggleImageMode = () => {
    setImageMode((prev) => {
      const next = prev === "border_crop" ? "art_crop" : "border_crop";
      localStorage.setItem("mtg-image-mode", next);
      return next;
    });
  };

  return (
    <AuthProvider>
      <ToastProvider>
        <DndProvider backend={HTML5Backend}>
          <AppRoutes
            imageMode={imageMode}
            onToggleImageMode={toggleImageMode}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
        </DndProvider>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add protected routes with auth redirect"
```

---

## Task 14: End-to-End Verification

Note: `frontend/nginx.conf` already has `try_files $uri $uri/ /index.html` — no changes needed.

- [ ] **Step 1: Final frontend build verification**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 2: End-to-end smoke test**

Start the backend and verify the full flow:

```bash
cd backend && timeout 10 uv run uvicorn app.main:app --port 8001 &
sleep 3

# Register a user
curl -s -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}' | python -m json.tool

# Login
curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}' | python -m json.tool

kill %1 2>/dev/null
```

Expected: both return `access_token`, `refresh_token`, and `user` object.
