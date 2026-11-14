"""Ground alert and durable notification HTTP contracts."""

from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import ContractModel


class ResolveAlertRequest(ContractModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=1000)


class ReceiptResponse(ContractModel):
    recorded: bool
    event_id: UUID
