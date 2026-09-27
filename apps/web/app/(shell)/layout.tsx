// T069: the authenticated shell - a nav wrapping every page in this route
// group. Middleware (T068) already keeps anyone unauthenticated out of
// every route except /login, so nothing extra is needed here to gate
// access - this layout is reached only when logged in.
//
// Nav cut down (by decision) from 5 items to 3: Harness (now the homepage,
// "/"), Conflicts, Taxonomy. Memory and Sources were removed outright.
import Link from "next/link";

import { logout } from "./actions";

const NAV_ITEMS = [
  { href: "/", label: "Harness" },
  { href: "/conflicts", label: "Conflicts" },
  { href: "/taxonomy", label: "Taxonomy" },
];

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "sans-serif" }}>
      <nav
        style={{
          width: 200,
          borderRight: "1px solid #333",
          padding: "1.5rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <form action={logout}>
          <button type="submit">Log out</button>
        </form>
        <hr style={{ width: "100%", border: "none", borderTop: "1px solid #333" }} />
        {NAV_ITEMS.map((item) => (
          <Link key={item.href} href={item.href}>
            {item.label}
          </Link>
        ))}
      </nav>
      <main style={{ flex: 1, padding: "2rem" }}>{children}</main>
    </div>
  );
}
