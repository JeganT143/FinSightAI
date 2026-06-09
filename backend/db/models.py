import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reports: Mapped[list["ResearchReport"]] = relationship(back_populates="user")


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running")

    report_v1: Mapped[str] = mapped_column(Text, nullable=True)
    report_v2: Mapped[str] = mapped_column(Text, nullable=True)
    was_revised: Mapped[bool] = mapped_column(Boolean, default=False)

    fundamentals_output: Mapped[str] = mapped_column(Text, nullable=True)
    risk_output: Mapped[str] = mapped_column(Text, nullable=True)
    sentiment_output: Mapped[str] = mapped_column(Text, nullable=True)

    critic_challenges_found: Mapped[int] = mapped_column(Integer, nullable=True)
    critic_assessment: Mapped[str] = mapped_column(Text, nullable=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="reports")
