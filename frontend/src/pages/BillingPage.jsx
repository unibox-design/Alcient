import React, { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";
import {
  loadBillingPlans,
  loadBillingUsage,
  startPlanCheckout,
  startTopUpCheckout,
  resetCheckoutState,
} from "../store/billingSlice";

function formatCurrency(cents) {
  if (typeof cents !== "number") return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

function formatTimestamp(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch (err) {
    return value;
  }
}

export default function BillingPage() {
  const dispatch = useDispatch();
  const plansState = useSelector((state) => state.billing.plans);
  const usageState = useSelector((state) => state.billing.usage);
  const checkoutState = useSelector((state) => state.billing.checkout);
  const topupState = useSelector((state) => state.billing.topup);
  const tokenBalance = useSelector((state) => state.billing.tokenBalance);
  const activePlanId = useSelector((state) => state.billing.activePlanId);
  const [topUpAmount, setTopUpAmount] = useState(2000);
  const [flashMessage, setFlashMessage] = useState(null);

  useEffect(() => {
    dispatch(loadBillingPlans());
    dispatch(loadBillingUsage());
  }, [dispatch]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let nextMessage = null;
    const status = params.get("status");
    const topup = params.get("topup");

    if (status === "success") {
      nextMessage = { tone: "success", text: "Plan updated successfully." };
    } else if (status === "cancelled") {
      nextMessage = { tone: "info", text: "Plan checkout was cancelled." };
    } else if (topup === "success") {
      nextMessage = {
        tone: "success",
        text: "Top-up completed. Tokens will appear shortly.",
      };
    } else if (topup === "cancelled") {
      nextMessage = { tone: "info", text: "Top-up was cancelled before payment." };
    }

    if (nextMessage) {
      setFlashMessage(nextMessage);
    }

    if (status || topup) {
      params.delete("status");
      params.delete("topup");
      const nextSearch = params.toString();
      const nextUrl = nextSearch ? `${window.location.pathname}?${nextSearch}` : window.location.pathname;
      window.history.replaceState({}, "", nextUrl);
    }
  }, []);

  useEffect(() => {
    const sessionUrl = checkoutState.session?.url || topupState.session?.url;
    if (sessionUrl) {
      window.location.href = sessionUrl;
      dispatch(resetCheckoutState());
    }
  }, [checkoutState.session, topupState.session, dispatch]);

  useEffect(
    () => () => {
      dispatch(resetCheckoutState());
    },
    [dispatch]
  );

  const planCards = useMemo(() => {
    return (plansState.items || []).map((plan) => {
      const isActive = activePlanId === plan.id;
      return (
        <div
          key={plan.id}
          className={`rounded-xl border p-6 shadow-sm transition ${
            isActive ? "border-indigo-500 bg-indigo-50" : "border-gray-200 bg-white"
          }`}
        >
          <h3 className="text-lg font-semibold text-gray-800">{plan.name}</h3>
          <p className="text-sm text-gray-500 mt-1">
            {formatCurrency(plan.monthlyPriceCents)} / month · {plan.tokensIncluded} tokens included
          </p>
          <p className="text-xs text-gray-400 mt-2">
            {plan.secondsIncluded} render seconds · {plan.overageTokensPerMinute} tokens/min overage
          </p>
          <button
            type="button"
            disabled={checkoutState.status === "loading"}
            onClick={() => {
              const origin = window.location.origin;
              dispatch(
                startPlanCheckout({
                  planId: plan.id,
                  successUrl: `${origin}/billing?status=success`,
                  cancelUrl: `${origin}/billing?status=cancelled`,
                })
              );
            }}
            className={`mt-4 w-full rounded-lg px-3 py-2 text-sm font-medium transition ${
              isActive
                ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                : "bg-gray-900 text-white hover:bg-gray-700"
            }`}
          >
            {isActive ? "Current plan" : checkoutState.status === "loading" ? "Redirecting…" : "Select plan"}
          </button>
        </div>
      );
    });
  }, [plansState.items, activePlanId, checkoutState.status, dispatch]);

  const usageRows = useMemo(() => {
    return (usageState.items || []).map((entry) => (
      <tr key={entry.id} className="odd:bg-gray-50">
        <td className="px-4 py-2 text-sm text-gray-600">{formatTimestamp(entry.createdAt)}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{entry.actionType}</td>
        <td className="px-4 py-2 text-sm text-gray-500">{entry.model}</td>
        <td className="px-4 py-2 text-sm text-gray-600 text-right">{entry.tokensTotal}</td>
        <td className="px-4 py-2 text-sm text-gray-600 text-right">{entry.durationSeconds?.toFixed?.(1) ?? "—"}</td>
      </tr>
    ));
  }, [usageState.items]);

  const handleTopUpSubmit = (evt) => {
    evt.preventDefault();
    if (!topUpAmount || topUpAmount <= 0) return;
    const origin = window.location.origin;
    dispatch(
      startTopUpCheckout({
        amountCents: topUpAmount,
        description: "Alcient token top-up",
        successUrl: `${origin}/billing?topup=success`,
        cancelUrl: `${origin}/billing?topup=cancelled`,
      })
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <Link
          to="/"
          className="flex items-center gap-2 text-xl font-semibold text-gray-800 hover:text-gray-900 transition"
        >
          <img src="/alcient.svg" alt="Alcient" className="h-8 w-auto" />
          ALCIENT
        </Link>
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-700 transition">
          ← Back to Templates
        </Link>
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-8">
        <section className="max-w-5xl mx-auto">
          {flashMessage && (
            <div
              className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
                flashMessage.tone === "success"
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-blue-200 bg-blue-50 text-blue-700"
              }`}
            >
              {flashMessage.text}
            </div>
          )}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Usage & Billing</h1>
              <p className="text-sm text-gray-500">
                Review your current plan, token balance, and recent activity.
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-600">
              Token balance: <span className="font-semibold text-gray-900">{tokenBalance ?? "—"}</span>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-800">Plans</h2>
              {plansState.status === "failed" && (
                <p className="text-sm text-red-500">{plansState.error}</p>
              )}
              {plansState.status === "loading" && planCards.length === 0 ? (
                <p className="text-sm text-gray-500">Loading plans…</p>
              ) : (
                <div className="space-y-4">{planCards}</div>
              )}
            </div>

            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-800">Top up tokens</h2>
              <form onSubmit={handleTopUpSubmit} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
                <label htmlFor="topup-amount" className="text-sm font-medium text-gray-700">
                  Amount (USD)
                </label>
                <input
                  id="topup-amount"
                  type="number"
                  min="500"
                  step="100"
                  value={topUpAmount}
                  onChange={(event) => setTopUpAmount(Number(event.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
                <p className="text-xs text-gray-500">Minimum $5. Tokens are added immediately after payment.</p>
                <button
                  type="submit"
                  disabled={topupState.status === "loading"}
                  className={`w-full rounded-lg px-3 py-2 text-sm font-medium transition ${
                    topupState.status === "loading"
                      ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                      : "bg-indigo-600 text-white hover:bg-indigo-500"
                  }`}
                >
                  {topupState.status === "loading" ? "Redirecting…" : "Start top-up"}
                </button>
                {topupState.status === "failed" && (
                  <p className="text-xs text-red-500">{topupState.error}</p>
                )}
              </form>
            </div>
          </div>

          <section className="mt-10">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-800">Recent usage</h2>
              <button
                type="button"
                onClick={() => dispatch(loadBillingUsage())}
                className="text-sm text-indigo-600 hover:text-indigo-500"
              >
                Refresh
              </button>
            </div>
            {usageState.status === "failed" ? (
              <p className="text-sm text-red-500">{usageState.error}</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">When</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Tokens</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">{usageRows}</tbody>
                </table>
                {usageState.status === "loading" && (
                  <p className="px-4 py-3 text-sm text-gray-500">Loading usage history…</p>
                )}
                {!usageRows.length && usageState.status === "succeeded" && (
                  <p className="px-4 py-3 text-sm text-gray-500">No usage recorded yet.</p>
                )}
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}
