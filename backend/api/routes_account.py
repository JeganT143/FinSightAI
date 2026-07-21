"""Account endpoints (SAAS §6.4): the signed-in user's own plan and usage."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.billing.limits import usage_summary
from backend.core.auth import get_current_user
from backend.db.models import User
from backend.db.session import get_db

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Current-period usage: {plan, runs_used, runs_limit, period_end}.

    Read by the billing page's usage meter and the Concierge's
    get_account_status tool (SAAS §8) — same numbers, one source.
    """
    return await usage_summary(db, user)


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    """Identity echo for the frontend: who am I, what plan am I on."""
    return {"id": str(user.id), "email": user.email, "plan": user.plan}
