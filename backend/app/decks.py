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
