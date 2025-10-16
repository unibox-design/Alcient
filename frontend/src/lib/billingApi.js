const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

async function jsonRequest(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  const body = await res.json();
  if (!res.ok) {
    const error = body?.error || res.statusText;
    throw new Error(error);
  }
  return body;
}

export async function fetchBillingUsage(limit = 50) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  const suffix = params.toString();
  const url = suffix ? `${BASE}/api/billing/usage?${suffix}` : `${BASE}/api/billing/usage`;
  return jsonRequest(url);
}

export async function fetchBillingPlans() {
  return jsonRequest(`${BASE}/api/billing/plans`);
}

export async function createPlanCheckoutSession({ planId, successUrl, cancelUrl }) {
  return jsonRequest(`${BASE}/api/billing/checkout`, {
    method: "POST",
    body: JSON.stringify({ planId, successUrl, cancelUrl }),
  });
}

export async function createTopUpCheckoutSession({ amountCents, successUrl, cancelUrl, description }) {
  return jsonRequest(`${BASE}/api/billing/topup`, {
    method: "POST",
    body: JSON.stringify({ amountCents, successUrl, cancelUrl, description }),
  });
}

