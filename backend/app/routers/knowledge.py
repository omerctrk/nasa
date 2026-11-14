"""Ground-control Knowledge Card CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import require_ground_control
from app.schemas.common import CurrentUser
from app.schemas.knowledge import KnowledgeCardContent, KnowledgeCardCreate, KnowledgeCardOut
from app.services import knowledge

router = APIRouter(prefix="/knowledge-cards", tags=["knowledge cards"])
Ground = Annotated[CurrentUser, Depends(require_ground_control)]
DB = Annotated[Session, Depends(get_db)]
CardPath = Annotated[str, Path(min_length=1, max_length=80)]


@router.get("", response_model=list[KnowledgeCardOut])
def list_cards(user: Ground, db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 50,
               offset: Annotated[int, Query(ge=0)] = 0):
    return knowledge.list_cards(db, limit, offset)


@router.post("", response_model=KnowledgeCardOut, status_code=201)
def create_card(body: KnowledgeCardCreate, user: Ground, db: DB):
    return knowledge.create_card(db, body)


@router.get("/{card_id}", response_model=KnowledgeCardOut)
def get_card(card_id: CardPath, user: Ground, db: DB):
    return knowledge.get_card(db, card_id)


@router.put("/{card_id}", response_model=KnowledgeCardOut)
def replace_card(card_id: CardPath, body: KnowledgeCardContent, user: Ground, db: DB):
    return knowledge.replace_card(db, card_id, body)


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: CardPath, user: Ground, db: DB):
    knowledge.delete_card(db, card_id)
    return Response(status_code=204)
