from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.app.api.deps import CurrentTenant
from src.app.db.models import Event

router = APIRouter(prefix="/api/v1", tags=["usage"])


class UsageTotals(BaseModel):
    llm_calls: int = 0
    stt_calls: int = 0
    tts_calls: int = 0
    whatsapp_messages: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    stt_seconds: float = 0.0
    tts_characters: int = 0
    total_cost_usd: float = 0.0


class UsageResponse(BaseModel):
    tenant_id: str
    from_date: str
    to_date: str
    totals: UsageTotals


FromDate = Annotated[date, Query(alias="from")]
ToDate = Annotated[date, Query(alias="to")]


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    tenant: CurrentTenant,
    from_date: FromDate,
    to_date: ToDate,
) -> Any:
    to_date_end = to_date + timedelta(days=1)

    events = await Event.filter(
        tenant_id=tenant.tenant_id,
        created_at__gte=from_date,
        created_at__lt=to_date_end,
    ).all()

    totals = UsageTotals()
    for ev in events:
        if ev.event_type == "llm_call":
            totals.llm_calls += 1
            totals.tokens_in += ev.input_tokens
            totals.tokens_out += ev.output_tokens
            totals.total_cost_usd += ev.cost_usd
        elif ev.event_type == "stt":
            totals.stt_calls += 1
            totals.stt_seconds += ev.audio_duration_s
        elif ev.event_type == "tts":
            totals.tts_calls += 1
            totals.tts_characters += ev.characters
        elif ev.event_type == "whatsapp_msg":
            totals.whatsapp_messages += 1

    totals.total_cost_usd = round(totals.total_cost_usd, 6)
    totals.stt_seconds = round(totals.stt_seconds, 2)

    return UsageResponse(
        tenant_id=tenant.tenant_id,
        from_date=str(from_date),
        to_date=str(to_date),
        totals=totals,
    )
