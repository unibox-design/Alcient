import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import {
  fetchBillingPlans,
  fetchBillingUsage,
  createPlanCheckoutSession,
  createTopUpCheckoutSession,
} from "../lib/billingApi";

const initialState = {
  plans: {
    status: "idle",
    items: [],
    error: null,
  },
  usage: {
    status: "idle",
    items: [],
    error: null,
  },
  checkout: {
    status: "idle",
    session: null,
    error: null,
  },
  topup: {
    status: "idle",
    session: null,
    error: null,
  },
  tokenBalance: null,
  activePlanId: null,
};

export const loadBillingPlans = createAsyncThunk(
  "billing/loadPlans",
  async (_, { rejectWithValue }) => {
    try {
      return await fetchBillingPlans();
    } catch (err) {
      return rejectWithValue(err.message || "Failed to load plans");
    }
  }
);

export const loadBillingUsage = createAsyncThunk(
  "billing/loadUsage",
  async (limit = 50, { rejectWithValue }) => {
    try {
      return await fetchBillingUsage(limit);
    } catch (err) {
      return rejectWithValue(err.message || "Failed to load usage history");
    }
  }
);

export const startPlanCheckout = createAsyncThunk(
  "billing/startPlanCheckout",
  async ({ planId, successUrl, cancelUrl }, { rejectWithValue }) => {
    try {
      return await createPlanCheckoutSession({ planId, successUrl, cancelUrl });
    } catch (err) {
      return rejectWithValue(err.message || "Failed to start checkout");
    }
  }
);

export const startTopUpCheckout = createAsyncThunk(
  "billing/startTopUpCheckout",
  async ({ amountCents, successUrl, cancelUrl, description }, { rejectWithValue }) => {
    try {
      return await createTopUpCheckoutSession({ amountCents, successUrl, cancelUrl, description });
    } catch (err) {
      return rejectWithValue(err.message || "Failed to start top-up");
    }
  }
);

const billingSlice = createSlice({
  name: "billing",
  initialState,
  reducers: {
    resetCheckoutState(state) {
      state.checkout = { status: "idle", session: null, error: null };
      state.topup = { status: "idle", session: null, error: null };
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadBillingPlans.pending, (state) => {
        state.plans.status = "loading";
        state.plans.error = null;
      })
      .addCase(loadBillingPlans.fulfilled, (state, action) => {
        const payload = action.payload || {};
        state.plans.status = "succeeded";
        state.plans.items = Array.isArray(payload.plans) ? payload.plans : [];
        state.activePlanId = payload.activePlanId || null;
        if (typeof payload.tokenBalance === "number") {
          state.tokenBalance = payload.tokenBalance;
        }
      })
      .addCase(loadBillingPlans.rejected, (state, action) => {
        state.plans.status = "failed";
        state.plans.error = action.payload || action.error?.message || "Failed to load plans";
      })
      .addCase(loadBillingUsage.pending, (state) => {
        state.usage.status = "loading";
        state.usage.error = null;
      })
      .addCase(loadBillingUsage.fulfilled, (state, action) => {
        const payload = action.payload || {};
        state.usage.status = "succeeded";
        state.usage.items = Array.isArray(payload.usage) ? payload.usage : [];
        if (typeof payload.tokenBalance === "number") {
          state.tokenBalance = payload.tokenBalance;
        }
      })
      .addCase(loadBillingUsage.rejected, (state, action) => {
        state.usage.status = "failed";
        state.usage.error = action.payload || action.error?.message || "Failed to load usage history";
      })
      .addCase(startPlanCheckout.pending, (state) => {
        state.checkout.status = "loading";
        state.checkout.error = null;
        state.checkout.session = null;
      })
      .addCase(startPlanCheckout.fulfilled, (state, action) => {
        state.checkout.status = "succeeded";
        state.checkout.session = action.payload?.checkoutSession || null;
      })
      .addCase(startPlanCheckout.rejected, (state, action) => {
        state.checkout.status = "failed";
        state.checkout.error = action.payload || action.error?.message || "Failed to start checkout";
      })
      .addCase(startTopUpCheckout.pending, (state) => {
        state.topup.status = "loading";
        state.topup.error = null;
        state.topup.session = null;
      })
      .addCase(startTopUpCheckout.fulfilled, (state, action) => {
        state.topup.status = "succeeded";
        state.topup.session = action.payload?.checkoutSession || null;
      })
      .addCase(startTopUpCheckout.rejected, (state, action) => {
        state.topup.status = "failed";
        state.topup.error = action.payload || action.error?.message || "Failed to start top-up";
      });
  },
});

export const { resetCheckoutState } = billingSlice.actions;

export default billingSlice.reducer;
