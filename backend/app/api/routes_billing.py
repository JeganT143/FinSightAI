from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.billing import BillingService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/balance")
async def get_balance(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    billing_service = BillingService(db)
    quota_info = await billing_service.check_quota(current_user)
    return quota_info


@router.get("/usage")
async def get_usage_summary(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    billing_service = BillingService(db)
    usage_summary = await billing_service.get_usage_summary(current_user.org_id)
    return usage_summary


@router.get("/history")
async def get_usage_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models import UsageEvent
    from sqlalchemy import select

    result = await db.execute(
        select(UsageEvent)
        .where(UsageEvent.user_id == current_user.id)
        .order_by(UsageEvent.timestamp.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(event.id),
            "kind": event.kind,
            "units": event.units,
            "cost_usd": event.cost_usd,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    from app.db.models import SubscriptionPlan
    from sqlalchemy import select

    result = await db.execute(
        select(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price_usd)
    )
    plans = result.scalars().all()
    return [
        {
            "code": plan.code,
            "monthly_price_usd": plan.monthly_price_usd,
            "reports_per_month": plan.monthly_report_quota,
        }
        for plan in plans
    ]
