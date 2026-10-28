"use client";

import { useLimits } from "./use-limits";

export function RunsLeft() {
  const { limits, error } = useLimits();
  if (error) return <p className="label">runs left today unavailable</p>;
  if (!limits) return <div className="sk" style={{ height: 28, width: "70%" }} aria-label="Loading runs left" />;
  return (
    <p className="label">
      <span className="num" style={{ color: "var(--ink)" }}>{limits.remaining} of {limits.cap}</span>
      <br />
      free reviews left today
    </p>
  );
}
