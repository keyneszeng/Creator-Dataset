from typing import Protocol


class BillingProvider(Protocol):
    """Boundary for future Stripe/Paddle/other payment integrations."""

    def create_credit_checkout(
        self,
        *,
        user_id: int,
        credit_amount: int,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, str]:
        ...


class BillingNotConfigured(RuntimeError):
    pass
