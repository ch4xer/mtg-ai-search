from pydantic import BaseModel


class CreateDeckRequest(BaseModel):
    name: str
    format: str = "undefined"


class UpdateDeckRequest(BaseModel):
    name: str
    format: str | None = None


class UpdateDeckCoverRequest(BaseModel):
    cover_image_url: str


class AddCardRequest(BaseModel):
    card_id: str
    quantity: int = 1
    print_id: str | None = None
    image_url: str | None = None
    display_url: str | None = None
    board: str = "mainboard"


class UpdateCardImageRequest(BaseModel):
    print_id: str | None = None
    image_url: str | None = None
    display_url: str | None = None
    board: str | None = None


class ImportDeckRequest(BaseModel):
    text: str
