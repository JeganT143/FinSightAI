from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def pk() -> Mapped[UUID]:
    return mapped_column(primary_key=True, default=uuid4)


# 1. Organization - Multi tanant boundary
class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[UUID] = pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("subscription_plans.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    users: Mapped[list["User"]] = relationship(back_populates="org")


# 2. Users
class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = pk()
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="member"
    )  # owner/admin/member
    org: Mapped[Organization] = relationship(back_populates="users")


# 3. Subscription Plans
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[UUID] = pk()
    code: Mapped[str] = mapped_column(
        String(50), unique=True
    )  # free, pro, team, enterprise
    monthly_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    monthly_report_quota: Mapped[int]
    max_seats: Mapped[int]


# 4. Research sessions
class ResearchSession(Base):
    __tablename__ = "research_sessions"
    id: Mapped[UUID] = pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# 5. Agent messages
class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id: Mapped[UUID] = pk()
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(50))
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)


# 6. Tool invocations
class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    id: Mapped[UUID] = pk()
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255))
    arguments: Mapped[dict] = mapped_column(JSON)
    result_preview: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# 7. Research artifacts
class ResearchArtifact(Base):
    __tablename__ = "research_artifacts"
    id: Mapped[UUID] = pk()
    session_id: Mapped[UUID] = mapped_column(ForeignKey("research_sessions.id"))
    ticker: Mapped[str] = mapped_column(String(255), index=True)
    summery: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)


# 8. Portfolios
class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[UUID] = pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))


#   9. Portfolio holdings
class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    id: Mapped[UUID] = pk()
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(255), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(20, 4))
    cost_basis: Mapped[float] = mapped_column(Numeric(20, 4))


# 10. Usage events
class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[UUID] = pk()
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(50))
    units: Mapped[int] = mapped_column(default=1)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
