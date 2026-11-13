import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.database import Base
from engine.models.billing import (
    ExecutionLog,
    User,
    allocate_charged_costs,
    calculate_task_cost,
    calculate_credit_amount,
    has_sufficient_balance,
    reserve_balance,
    settle_reserved_balance,
)


class BillingModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_user_has_default_credit_balance(self):
        user = User(email="test@example.com")
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        self.assertEqual(user.credit_balance, Decimal("10.000000"))

    def test_execution_log_belongs_to_user(self):
        user = User(email="test@example.com")
        user.execution_logs.append(
            ExecutionLog(
                task_name="Build API",
                model_used="ollama/qwen2.5-coder:7b",
                input_tokens=100,
                output_tokens=200,
                cost_deducted=Decimal("0.01"),
                status="completed",
            )
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        self.assertEqual(len(user.execution_logs), 1)
        self.assertEqual(user.execution_logs[0].task_name, "Build API")
        self.assertEqual(user.execution_logs[0].user_id, user.id)

    def test_deleting_user_deletes_execution_logs(self):
        user = User(email="test@example.com")
        user.execution_logs.append(
            ExecutionLog(
                task_name="Test task",
                model_used="gemini-3-5-flash-lite",
                status="failed",
            )
        )
        self.session.add(user)
        self.session.commit()
        log_id = user.execution_logs[0].id

        self.session.delete(user)
        self.session.commit()

        self.assertIsNone(self.session.get(ExecutionLog, log_id))

    def test_calculates_cloud_model_cost_from_actual_tokens(self):
        cost = calculate_task_cost("gemini-3-5-flash-lite", 1000, 2000)
        self.assertEqual(cost, Decimal("0.000900"))

    def test_local_ollama_cost_is_zero(self):
        self.assertEqual(
            calculate_task_cost("ollama/qwen2.5-coder:7b", 1000, 2000),
            Decimal("0"),
        )

    def test_user_balance_can_be_decremented_by_measured_cost(self):
        user = User(email="test@example.com", credit_balance=Decimal("10.00"))
        self.session.add(user)
        self.session.commit()

        user.credit_balance -= calculate_task_cost(
            "gemini-3-5-flash-lite",
            1000,
            2000,
        )
        self.session.commit()
        self.session.refresh(user)

        self.assertEqual(user.credit_balance, Decimal("9.999100"))

    def test_zero_balance_cannot_cover_paid_estimate(self):
        self.assertFalse(has_sufficient_balance(Decimal("0"), Decimal("0.000520")))

    def test_balance_can_cover_zero_cost_local_execution(self):
        self.assertTrue(has_sufficient_balance(Decimal("0"), Decimal("0")))

    def test_balance_guard_allows_exact_estimate(self):
        self.assertTrue(has_sufficient_balance(Decimal("0.000520"), Decimal("0.000520")))

    def test_reservation_is_atomic_and_settlement_refunds_unused_estimate(self):
        user = User(email="reserve@example.com", credit_balance=Decimal("1.00"))
        self.session.add(user)
        self.session.commit()

        self.assertTrue(reserve_balance(self.session, user.id, Decimal("0.40")))
        self.session.commit()
        self.session.refresh(user)
        self.assertEqual(user.credit_balance, Decimal("0.60"))

        fully_charged, charged = settle_reserved_balance(
            self.session,
            user.id,
            Decimal("0.40"),
            Decimal("0.25"),
        )
        self.session.commit()
        self.session.refresh(user)
        self.assertTrue(fully_charged)
        self.assertEqual(charged, Decimal("0.25"))
        self.assertEqual(user.credit_balance, Decimal("0.75"))

    def test_reservation_rejects_insufficient_balance_without_negative_balance(self):
        user = User(email="reserve-low@example.com", credit_balance=Decimal("0.10"))
        self.session.add(user)
        self.session.commit()

        self.assertFalse(reserve_balance(self.session, user.id, Decimal("0.11")))
        self.session.rollback()
        self.session.refresh(user)
        self.assertEqual(user.credit_balance, Decimal("0.10"))

    def test_settlement_caps_charge_when_actual_cost_exceeds_reservation(self):
        user = User(email="reserve-overrun@example.com", credit_balance=Decimal("0.10"))
        self.session.add(user)
        self.session.commit()

        self.assertTrue(reserve_balance(self.session, user.id, Decimal("0.08")))
        self.session.commit()
        fully_charged, charged = settle_reserved_balance(
            self.session,
            user.id,
            Decimal("0.08"),
            Decimal("0.12"),
        )
        self.session.commit()
        self.session.refresh(user)
        self.assertFalse(fully_charged)
        self.assertEqual(charged, Decimal("0.08"))
        self.assertEqual(user.credit_balance, Decimal("0.02"))

    def test_log_costs_never_exceed_amount_charged(self):
        allocated = allocate_charged_costs(
            {
                "first": Decimal("0.07"),
                "second": Decimal("0.05"),
            },
            Decimal("0.08"),
        )
        self.assertEqual(allocated, {
            "first": Decimal("0.07"),
            "second": Decimal("0.01"),
        })
        self.assertEqual(sum(allocated.values()), Decimal("0.08"))

    def test_inr_payment_uses_configured_usd_conversion(self):
        self.assertEqual(
            calculate_credit_amount(Decimal("500.00"), Decimal("100")),
            Decimal("5.000000"),
        )

    def test_payment_conversion_rejects_non_positive_values(self):
        with self.assertRaises(ValueError):
            calculate_credit_amount(Decimal("500.00"), Decimal("0"))


if __name__ == "__main__":
    unittest.main()
