# Razorpay Integration

Our transaction schema mirrors Razorpay's Payment entity structure so this could integrate with real Razorpay transaction data with minimal changes to ingestion, and no changes to detection or cost logic.

At a minimum, the schema implements:
- `amount` — stored as an integer in the smallest currency unit (paise for INR).
- `currency` — strictly 'INR'.
- `method` — accurate Razorpay methods like 'card', 'upi', 'netbanking', 'wallet', 'emi'.
- `email`, `contact` — synthetic standard identifiers.
- `status` — accurate states like 'captured', 'failed', 'authorized'.
- `notes` — a free-form key-value dictionary acting as a carrier for merchant metadata (like `merchant_id` and `tier`), aligning with how Razorpay attaches custom application metadata.

## Webhook Integration

PulseGuard can consume Razorpay's own dispute webhooks as real, delayed ground truth, closing the loop between the delayed-label problem we identified and the cost model's assumptions — this is a genuine integration point, not a simulated one.

The integration utilizes Razorpay's webhook signature verification (`X-Razorpay-Signature` payload signing via HMAC-SHA256). This verification is crucial because without it, anyone could POST a fake payload to the endpoint and trigger false actions or poison the delayed ground-truth metrics.

When a `payment.dispute.created` event is securely verified and ingested, it is logged as a confirmed fraud chargeback event and directly impacts the recalibration report, visualizing the cost shift of missed anomalies.
