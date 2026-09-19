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
