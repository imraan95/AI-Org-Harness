"use client";

// T068: the login page - plain email/password (see build-plan T068's
// status note for why: local dev has no email delivery configured, so
// magic links can't actually be tested without extra setup).
import { useActionState } from "react";

import { login } from "./actions";

const initialState = { error: "" };

async function loginAction(_prevState: { error: string }, formData: FormData) {
  const result = await login(formData);
  return result ?? initialState;
}

export default function LoginPage() {
  const [state, formAction, pending] = useActionState(loginAction, initialState);

  return (
    <main style={{ maxWidth: 360, margin: "4rem auto", fontFamily: "sans-serif" }}>
      <h1>Log in</h1>
      <form action={formAction} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label>
          Email
          <input name="email" type="email" required autoComplete="email" style={{ width: "100%" }} />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            required
            autoComplete="current-password"
            style={{ width: "100%" }}
          />
        </label>
        {state.error ? <p style={{ color: "crimson" }}>{state.error}</p> : null}
        <button type="submit" disabled={pending}>
          {pending ? "Logging in..." : "Log in"}
        </button>
      </form>
    </main>
  );
}
