"""Knowledge Card CRUD routes backed by the configured persistence repository."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.repositories.knowledge_card_repository import CardAlreadyExistsError, CardNotFoundError
from app.schemas.knowledge_card import KnowledgeCard
from app.services.knowledge_card_service import KnowledgeCardService, get_knowledge_card_service


router = APIRouter(prefix="/knowledge-cards", tags=["knowledge-cards"])
ServiceDependency = Annotated[KnowledgeCardService, Depends(get_knowledge_card_service)]


@router.post("", response_model=KnowledgeCard, status_code=status.HTTP_201_CREATED)
def create_knowledge_card(card: KnowledgeCard, service: ServiceDependency) -> KnowledgeCard:
    """Create a card if its ID has not already been imported."""
    try:
        return service.create_card(card)
    except CardAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Knowledge Card '{error.args[0]}' already exists.",
        ) from error


@router.get("", response_model=list[KnowledgeCard])
def list_knowledge_cards(service: ServiceDependency) -> list[KnowledgeCard]:
    """Return all cards in stable ID order."""
    return service.list_cards()


@router.get("/{card_id}", response_model=KnowledgeCard)
def get_knowledge_card(card_id: str, service: ServiceDependency) -> KnowledgeCard:
    """Return one card by ID."""
    try:
        return service.get_card(card_id)
    except CardNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge Card '{error.args[0]}' was not found.",
        ) from error


@router.put("/{card_id}", response_model=KnowledgeCard)
def replace_knowledge_card(
    card_id: str,
    card: KnowledgeCard,
    service: ServiceDependency,
) -> KnowledgeCard:
    """Replace an existing card while keeping the path and payload IDs consistent."""
    if card.id != card_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Path card_id must match the Knowledge Card payload id.",
        )
    try:
        return service.update_card(card)
    except CardNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge Card '{error.args[0]}' was not found.",
        ) from error


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_card(card_id: str, service: ServiceDependency) -> Response:
    """Delete a card from temporary development storage."""
    try:
        service.delete_card(card_id)
    except CardNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge Card '{error.args[0]}' was not found.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
