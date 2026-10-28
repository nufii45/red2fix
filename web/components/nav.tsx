"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { RunsLeft } from "./runs-left";

const LINKS = [
  { href: "/", label: "try it" },
  { href: "/results", label: "results" },
  { href: "/install", label: "use it on your repo" },
  { href: "/recent", label: "recent reviews" },
];

function Links({ onClick }: { onClick?: () => void }) {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" || path.startsWith("/r/") : path.startsWith(href));
  return (
    <nav className="nav" aria-label="Main">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} aria-current={active(l.href) ? "page" : undefined} onClick={onClick}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}

function Foot() {
  return (
    <div className="side-foot">
      <RunsLeft />
      <a className="label" href="https://github.com/nufii45/red2fix" target="_blank" rel="noreferrer">
        source on github ↗
      </a>
    </div>
  );
}

export function Nav() {
  const [open, setOpen] = useState(false);
  const path = usePathname();
  // eslint-disable-next-line react-hooks/set-state-in-effect -- close the phone menu on navigation
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);

  return (
    <>
      <aside className="side">
        <Link href="/" className="wordmark">red2fix</Link>
        <Links />
        <Foot />
      </aside>
      <header className="top">
        <Link href="/" className="wordmark">red2fix</Link>
        <button className="menu-btn" aria-expanded={open} aria-controls="menu" onClick={() => setOpen((o) => !o)}>
          {open ? "close" : "menu"}
        </button>
      </header>
      {open && (
        <div className="overlay" id="menu">
          <Links onClick={() => setOpen(false)} />
          <Foot />
        </div>
      )}
    </>
  );
}
