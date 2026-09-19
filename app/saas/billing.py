from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class PaymentProvider(StrEnum):
    WECHAT_PAY = "wechat_pay"
    STRIPE = "stripe"
    PADDLE = "paddle"


class PaymentMethod(StrEnum):
    WECHAT_NATIVE = "wechat_native"
    WECHAT_JSAPI = "wechat_jsapi"
    WECHAT_MINIPROGRAM = "wechat_miniprogram"
    WECHAT_H5 = "wechat_h5"
    STRIPE_CHECKOUT = "stripe_checkout"
    PADDLE_CHECKOUT = "paddle_checkout"


class PaymentStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    CLOSED = "closed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class CreditProduct:
    code: str
    credits: int
    amount_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class CreatePaymentRequest:
    user_id: int
    merchant_order_no: str
    product: CreditProduct
    payment_method: PaymentMethod
    success_url: str | None = None
    cancel_url: str | None = None
    client_ip: str | None = None
    provider_identity: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PaymentLaunch:
    provider: PaymentProvider
    payment_method: PaymentMethod
    merchant_order_no: str
    provider_order_id: str | None = None
    redirect_url: str | None = None
    qr_code_url: str | None = None
    client_payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VerifiedPaymentEvent:
    provider: PaymentProvider
    event_id: str
    merchant_order_no: str
    provider_order_id: str | None
    paid: bool
    amount_minor: int
    currency: str
    raw: dict[str, Any]


class BillingProviderAdapter(Protocol):
    """
    Provider-specific payment boundary.

    Implementations create provider orders and verify/decrypt provider
    notifications. They never grant Dataset entitlements directly.
    """

    provider: PaymentProvider

    def create_payment(
        self,
        request: CreatePaymentRequest,
    ) -> PaymentLaunch:
        ...

    def verify_notification(
        self,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> VerifiedPaymentEvent:
        ...

    def query_payment(
        self,
        *,
        merchant_order_no: str,
    ) -> VerifiedPaymentEvent:
        ...


class BillingNotConfigured(RuntimeError):
    pass
