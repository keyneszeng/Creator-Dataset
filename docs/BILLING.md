# Billing Architecture

## Billing Unit

The primary commercial unit is:

```text
1 Dataset Unlock Credit
=
permanent access to one Post Dataset
```

Credits are not charged for:

- viewing an already unlocked Dataset
- downloading it again
- repairing a failed processing Job
- regenerating the same Dataset schema version
- submitting a Creator URL

## Credit Buckets

Two buckets exist:

```text
free
paid
```

Unlock order:

```text
free first
↓
paid second
↓
payment required
```

This keeps promotional/free quota separate from purchased value.

## Ledger Model

Balances are derived from `credit_ledger`.

Examples:

```text
signup_grant       free  +5
dataset_unlock     free  -1
payment_purchase   paid +50
dataset_unlock     paid  -1
admin_grant        paid +10
```

The application does not maintain a mutable balance field as the source of truth.

Benefits:

- auditability
- refunds/adjustments later
- purchase history reconciliation
- safer concurrent updates

## Payment Provider Boundary

The core system is provider-neutral.

A payment integration should perform:

```text
Payment Provider
      ↓
verified webhook
      ↓
provider event_id
      ↓
billing_events
      ↓
paid credit ledger grant
```

The provider does not create Dataset entitlements directly.

Entitlements are still created only when a user unlocks a Dataset.

## Webhook Idempotency

`billing_events` has a unique constraint on:

```text
provider + event_id
```

Repeated delivery of the same payment event is safe.

Example:

```text
Stripe event evt_123 arrives
→ +100 paid credits

Stripe retries evt_123
→ event already processed
→ +0 credits
```

SQLite and PostgreSQL both implement this transactionally.

## Provider Adapter

The current code defines a BillingProvider boundary but does not choose a payment vendor yet.

Possible integrations:

- Stripe
- Paddle
- Lemon Squeezy
- regional payment provider

The future adapter should be responsible for:

- checkout creation
- webhook signature verification
- mapping product/SKU to credit amount
- applying a verified billing event

The core credit and entitlement system remains unchanged.

## Recommended Early Products

A simple initial structure:

```text
Free
5 Dataset credits

Pack 50
50 paid credits

Pack 200
200 paid credits

Pack 1000
1000 paid credits
```

Subscriptions can be added later by periodically granting paid credits after a verified recurring invoice event.

## Important Rule

Never trust the browser/client to tell the server how many credits a payment purchased.

The credit amount must be resolved server-side from a trusted product/price mapping after webhook verification.


## WeChat Pay Compatibility

WeChat Pay is a first-class future provider, not a special-case credit path.

The core rule remains:

```text
WeChat Pay
   ↓
Payment Order
   ↓
verified payment result
   ↓
Billing Event
   ↓
Paid Credit Ledger
   ↓
Dataset Unlock
   ↓
Entitlement
```

WeChat Pay never writes Dataset entitlements directly.

### Supported Future WeChat Payment Methods

The provider-neutral `payment_orders.payment_method` field already supports modeling:

```text
wechat_native
wechat_jsapi
wechat_miniprogram
wechat_h5
```

Recommended product usage:

```text
Desktop browser
→ Native QR Code payment

Inside WeChat / Official Account H5
→ JSAPI payment

Future WeChat Mini Program
→ Mini Program payment

Mobile browser outside WeChat
→ H5 payment where applicable
```

### Payment Orders

`payment_orders` is the commercial order source of truth.

Important fields:

```text
user_id
provider
payment_method
merchant_order_no
provider_order_id
product_code
credits
amount_minor
currency
status
expires_at
paid_at
```

The browser never decides the price or credit amount.

A server-side product catalog maps:

```text
product_code
→ credits
→ amount_minor
→ currency
```

before a payment order is created.

### WeChat Payment Identity

JSAPI / Mini Program scenarios may require a provider-side user identity such as an OpenID associated with an application ID.

The generic `payment_identities` table models this as:

```text
user_id
provider=wechat_pay
application_id=<appid>
subject_id=<provider subject, e.g. openid>
```

This keeps WeChat-specific identity data out of the core `users` table and supports multiple application IDs.

### WeChat Pay Notification Handling

The future WeChat Pay adapter must:

1. receive the raw callback body and WeChat Pay signature headers;
2. verify the notification signature before trusting the body;
3. decrypt the encrypted resource using the API v3 key;
4. resolve the internal payment order using the merchant order number;
5. verify amount/currency/order ownership against the server-side order;
6. create an idempotent `billing_events` record;
7. grant paid credits exactly once;
8. acknowledge the callback promptly;
9. support active order query/reconciliation when callbacks are delayed or missed.

The raw client must never be allowed to call a “grant credits” webhook endpoint directly.

### WeChat Configuration Boundary

Future provider configuration is reserved through environment variables:

```text
CREATOR_DATASET_WECHAT_PAY_MCH_ID
CREATOR_DATASET_WECHAT_PAY_APP_ID
CREATOR_DATASET_WECHAT_PAY_MINIPROGRAM_APP_ID
CREATOR_DATASET_WECHAT_PAY_MERCHANT_SERIAL_NO
CREATOR_DATASET_WECHAT_PAY_PRIVATE_KEY_PATH
CREATOR_DATASET_WECHAT_PAY_API_V3_KEY
CREATOR_DATASET_WECHAT_PAY_PLATFORM_PUBLIC_KEY_ID
CREATOR_DATASET_WECHAT_PAY_PLATFORM_PUBLIC_KEY_PATH
CREATOR_DATASET_WECHAT_PAY_NOTIFY_URL
```

Production secrets must live in a secret manager and must not be committed to Git.

### Multi-provider Future

One user may eventually purchase the same credit product through different providers:

```text
China user
→ WeChat Pay
→ paid credits

International user
→ Stripe / Paddle
→ paid credits
```

After payment confirmation both paths converge on the same ledger:

```text
paid +N
```

Therefore Dataset unlock, entitlement, generation and download logic remain provider-independent.
