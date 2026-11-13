"""Database models for DietCode's local credit ledger."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, update
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from ..database import Base
except ImportError:
    from database import Base


MODEL_PRICING_PER_MILLION = {
    "claude-3-5-sonnet": (Decimal("3.00"), Decimal("15.00")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gemini-2-0-flash": (Decimal("0.10"), Decimal("0.40")),
    "gemini-3-5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "gemini-1-5-pro": (Decimal("1.25"), Decimal("5.00")),
    "claude-3-5-haiku": (Decimal("0.80"), Decimal("4.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
}


def calculate_task_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Calculate USD cost from actual token usage.

    Ollama is local and has no provider token charge. The Gemini 3.5 Flash
    Lite rate uses DietCode's current Gemini benchmark rate until a provider
    specific billing catalog is configured.
    """
    normalized_model = model.lower().strip()
    if normalized_model.startswith("ollama/"):
        return Decimal("0")

    pricing_key = next(
        (key for key in MODEL_PRICING_PER_MILLION if key in normalized_model),
        None,
    )
    if pricing_key is None:
        raise ValueError(f"No billing rate configured for model: {model}")

    input_rate, output_rate = MODEL_PRICING_PER_MILLION[pricing_key]
    cost = (
        (Decimal(max(0, input_tokens)) / Decimal("1000000")) * input_rate
        + (Decimal(max(0, output_tokens)) / Decimal("1000000")) * output_rate
    )
    return cost.quantize(Decimal("0.000001"))


def has_sufficient_balance(balance: Decimal, estimated_cost: Decimal) -> bool:
    """Return whether a balance can cover an estimated execution cost."""
    return balance >= estimated_cost


def reserve_balance(session, user_id: int, amount: Decimal) -> bool:
    """Atomically reserve funds so concurrent executions cannot overspend."""
    if amount <= 0:
        return True
    result = session.execute(
        update(User)
        .where(User.id == user_id, User.credit_balance >= amount)
        .values(credit_balance=User.credit_balance - amount)
    )
    return result.rowcount == 1


def settle_reserved_balance(
    session,
    user_id: int,
    reserved_cost: Decimal,
    actual_cost: Decimal,
) -> tuple[bool, Decimal]:
    """Settle a reservation and return whether actual cost was fully charged."""
    difference = reserved_cost - actual_cost
    if difference >= 0:
        if difference:
            session.execute(
                update(User)
                .where(User.id == user_id)
                .values(credit_balance=User.credit_balance + difference)
            )
        return True, actual_cost

    additional_cost = -difference
    result = session.execute(
        update(User)
        .where(User.id == user_id, User.credit_balance >= additional_cost)
        .values(credit_balance=User.credit_balance - additional_cost)
    )
    if result.rowcount != 1:
        return False, reserved_cost
    return True, actual_cost


def allocate_charged_costs(
    task_costs: dict[str, Decimal],
    charged_total: Decimal,
) -> dict[str, Decimal]:
    """Allocate the amount actually charged across task execution logs."""
    remaining = max(Decimal("0"), charged_total)
    allocated: dict[str, Decimal] = {}
    for task_id, task_cost in task_costs.items():
        allocation = min(max(Decimal("0"), task_cost), remaining)
        allocated[task_id] = allocation
        remaining -= allocation
    return allocated


def calculate_credit_amount(amount_inr: Decimal, inr_per_usd: Decimal) -> Decimal:
    """Convert a payment amount in INR into the configured USD credit balance."""
    if amount_inr <= 0 or inr_per_usd <= 0:
        raise ValueError("Payment amount and INR_PER_USD must be positive")
    return (amount_inr / inr_per_usd).quantize(Decimal("0.000001"))


class User(Base):
    """A DietCode account with an available credit balance."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("10.00"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    execution_logs: Mapped[list["ExecutionLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ExecutionLog(Base):
    """Record of one task execution associated with a user."""

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_used: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_deducted: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    user: Mapped[User] = relationship(back_populates="execution_logs")


class PaymentTransaction(Base):
    """Idempotent record of a Stripe payment and its balance credit."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payment_provider_event"),
        UniqueConstraint("checkout_session_id", name="uq_payment_checkout_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="stripe")
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkout_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    credit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    inr_per_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    user: Mapped[User] = relationship()
