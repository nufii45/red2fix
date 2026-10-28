"use client";

import { useEffect, useState } from "react";

export type Limits = { used: number; cap: number; remaining: number; simulated?: boolean };

// One shared poll for every component that shows the count.
let cache: Limits | null = null;
let failed = false;
const subs = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

async function load() {
  try {
    const res = await fetch("/api/limits", { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    cache = await res.json();
    failed = false;
  } catch {
    failed = true;
  }
  subs.forEach((f) => f());
}

export const refreshLimits = load;

export function useLimits() {
  const [, tick] = useState(0);
  useEffect(() => {
    const f = () => tick((n) => n + 1);
    subs.add(f);
    if (!timer) {
      load();
      timer = setInterval(load, 30_000);
    }
    return () => {
      subs.delete(f);
      if (!subs.size && timer) {
        clearInterval(timer);
        timer = null;
      }
    };
  }, []);
  return { limits: cache, error: failed && !cache };
}
