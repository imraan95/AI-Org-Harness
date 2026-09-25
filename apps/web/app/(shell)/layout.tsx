// T069: the authenticated 4-pane shell - a nav with Memory, Conflicts,
// Sources, Harness, wrapping every page in this route group. Middleware
// (T068) already keeps anyone unauthenticated out of every route except
// /login, so nothing extra is needed here to gate access - this layout
// is reached only when logged in.
import Link from "next/link";

import { logout } from "./actions";

const NAV_ITEMS = [
  { href: "/memory", label: "Memory" },
  { href: "/conflicts", label: "Conflicts" },
  { href: "/sources", label: "Sources" },
  { href: "/harness", label: "Harness" },
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
