import re

from fastapi import HTTPException

from ..repositories.cards import get_card_by_oracle_id, get_card_print_by_set_cn, get_cards_by_names
from ..repositories.decks import add_card_to_deck
from ..schemas.decks import ImportDeckRequest
from .deck_access_service import require_owner

DECKLIST_ENTRY_RE = re.compile(
    r"^(\d+)\s+(.+?)(?:\s+\(([A-Za-z0-9]{2,6})\)\s+(\S+))?(?:\s+\*\w+\*)*\s*$"
)


def extract_front_face_name(name: str) -> str:
    name = name.strip()
    for sep in [" // ", " / "]:
        if sep in name:
            return name.split(sep)[0].strip()
    return name


def parse_decklist(text: str) -> list[tuple[int, str, str, str | None, str | None]]:
    entries: list[tuple[int, str, str, str | None, str | None]] = []
    board = "mainboard"
    has_sideboard_cards = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#") or line.startswith("//"):
            continue
        if "SIDEBOARD" in line.upper():
            board = "sideboard"
            has_sideboard_cards = False
            continue
        if not line:
            if board == "sideboard" and has_sideboard_cards:
                board = "mainboard"
            continue

        match = DECKLIST_ENTRY_RE.match(line)
        if match:
            entries.append(
                (
                    int(match.group(1)),
                    extract_front_face_name(match.group(2)),
                    board,
                    match.group(3),
                    match.group(4),
                )
            )
        else:
            entries.append((1, extract_front_face_name(line), board, None, None))

        if board == "sideboard":
            has_sideboard_cards = True

    return entries


async def import_owned_deck(deck_id: str, user_id: str, req: ImportDeckRequest) -> dict:
    await require_owner(deck_id, user_id)

    entries = parse_decklist(req.text)
    if not entries:
        raise HTTPException(status_code=400, detail="No cards found in text")

    name_to_id = await get_cards_by_names(list({name for _, name, _, _, _ in entries}))
    added = []
    not_found = []

    for qty, name, board, set_code, collector_num in entries:
        card_id = name_to_id.get(name.lower())
        image_url = None
        display_url = None
        selected_print_id = None
        resolved_name = None

        if card_id and set_code:
            selected_print = await get_card_print_by_set_cn(card_id, set_code, collector_num or "")
            if selected_print:
                selected_print_id = selected_print["id"]
                image_url = selected_print.get("image_large") or selected_print.get("image_png")
                display_url = selected_print.get("image_art_crop")

        if not card_id:
            card_info = await get_card_by_oracle_id(name)
            if card_info:
                card_id = card_info["id"]
                resolved_name = card_info["name"]

        if card_id:
            await add_card_to_deck(
                deck_id,
                card_id,
                qty,
                image_url=image_url,
                display_url=display_url,
                update_image=bool(image_url),
                board=board,
                print_id=selected_print_id,
            )
            result = {"name": resolved_name or name, "quantity": qty, "board": board}
            if set_code:
                result["set"] = set_code
            if resolved_name and resolved_name.lower() != name.lower():
                result["resolved_from"] = name
            added.append(result)
        else:
            not_found.append(name)

    return {"added": added, "not_found": not_found}
