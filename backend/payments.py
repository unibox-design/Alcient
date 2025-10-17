
"""Stripe integration helpers for plan upgrades and top-ups."""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for local demos
    stripe = None  # type: ignore


class StripeUnavailable(RuntimeError):
    """Raised when Stripe is not configured but an integration is requested."""


def _ensure_stripe() -> None:
    if stripe is None:
        raise StripeUnavailable("stripe library not installed")
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise StripeUnavailable("STRIPE_API_KEY is not configured")
    stripe.api_key = api_key


def _plan_price_map() -> Dict[str, str]:
    raw = os.getenv("STRIPE_PLAN_PRICE_MAP", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items() if v}


def create_plan_checkout_session(
    *,
    user_email: str,
    plan_id: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, str]:
    _ensure_stripe()
    price_map = _plan_price_map()
    price_id = price_map.get(plan_id)
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan {plan_id}")

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": price_id, "quantity": 1}],
        allow_promotion_codes=True,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"plan_id": plan_id},
    )
    return {"id": session.get("id"), "url": session.get("url")}


def create_topup_checkout_session(
    *,
    user_email: str,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
    description: Optional[str] = None,
) -> Dict[str, str]:
    _ensure_stripe()
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    description = description or "Alcient token top-up"
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_intent_data={"metadata": {"type": "token_topup", "email": user_email}},
        customer_email=user_email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": description},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return {"id": session.get("id"), "url": session.get("url")}


def get_stripe_invoices(email: Optional[str] = None) -> list:
    _ensure_stripe()
    # Fetch customer by email
    customers = stripe.Customer.list(email=email, limit=1)
    if not customers.data:
        return []
    customer_id = customers.data[0].id
    invoices = stripe.Invoice.list(customer=customer_id, limit=20)
    result = []
    for inv in invoices.auto_paging_iter():
        result.append({
            "id": inv.id,
            "amount_due": inv.amount_due,
            "amount_paid": inv.amount_paid,
            "currency": inv.currency,
            "status": inv.status,
            "created": inv.created,
            "invoice_pdf": getattr(inv, "invoice_pdf", None),
        })
    return result

# Razorpay integration (India local payments)
import uuid  # Needed for Razorpay order receipts
try:
    import razorpay  # pip install razorpay
except ImportError:
    razorpay = None

def create_razorpay_order(amount_cents: int, currency: str = "INR", receipt: str = None) -> dict:
    if razorpay is None:
        raise RuntimeError("razorpay library not installed")
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise RuntimeError("RAZORPAY_KEY_ID/KEY_SECRET not configured")
    client = razorpay.Client(auth=(key_id, key_secret))
    order = client.order.create({
        "amount": amount_cents,
        "currency": currency,
        "receipt": receipt or f"alcient_{uuid.uuid4().hex}",
        "payment_capture": 1
    })
    return order



__all__ = [
    "StripeUnavailable",
    "create_plan_checkout_session",
    "create_topup_checkout_session",
]
