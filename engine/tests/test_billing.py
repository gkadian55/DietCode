import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.database import Base
from engine.models.billing import ExecutionLog, User


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


if __name__ == "__main__":
    unittest.main()
