import uuid
from datetime import datetime, timezone

from app.db.models import Organization, SubscriptionPlan, UsageEvent, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_plan(self, org_id: uuid.UUID) -> SubscriptionPlan:
        org = await self.db.get(Organization, org_id)
        plan = await self.db.get(SubscriptionPlan, org.plan_id)
        return plan

    async def reports_used_this_month(self, org_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(func.count(UsageEvent.id))
            .where(UsageEvent.org_id == org_id)
            .where(UsageEvent.kind == "research_report")
            .where(UsageEvent.created_at >= month_start)
        )
        return result.scalar() or 0

    async def check_quota(self, user: User) -> dict:
        plan = await self.get_plan(user.org_id)
        used = await self.reports_used_this_month(user.org_id)
        limit = plan.monthly_report_quota
        remaining = max(0, limit - used)
        return {
            "plan_code": plan.code,
            "monthly_limit": limit,
            "used": used,
            "remaining": remaining,
            "allowed": remaining > 0,
        }

    async def record_usage(
        self,
        user: User,
        kind: str,
        units: int = 1,
        cost_usd: float = 0.0,
    ) -> UsageEvent:
        event = UsageEvent(
            id=uuid.uuid4(),
            org_id=user.org_id,
            user_id=user.id,
            kind=kind,
            units=units,
            cost_usd=cost_usd,
        )
        self.db.add(event)
        await self.db.commit()
        return event

    async def get_usage_summary(self, org_id: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        reports_cout = await self.reports_used_this_month(org_id)

        cost_result = await self.db.execute(
            select(func.sum(UsageEvent.cost_usd))
            .where(UsageEvent.org_id == org_id)
            .where(UsageEvent.created_at >= month_start)
        )
        total_cost = cost_result.scalar() or 0.0
        plan = await self.get_plan(org_id)

        return {
            "plan": plan.code,
            "monthly_report_usd": float(plan.monthly_price_usd),
            "reports_used": reports_cout,
            "reports_limit": plan.monthly_report_quota,
            "cost_this_month_usd": round(total_cost, 4),
            "reset_date": (
                month_start.replace(month=month_start.month % 12 + 1).isoformat()
            ),
        }
