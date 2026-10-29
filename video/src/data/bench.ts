// Frozen review bench rv-full at commit 0c32486. Every number names its source line.
export const BENCH = {
  reviews: 40, // docs/spec/DECISIONS.md:41 "40 reviews"; README.md:107-108 (20 instances × gold + one failed patch)
  gold: 20, // README.md:107 "20 instances"
  failed: 20, // docs/bench-analysis.md:61 "Truly failed: 16 of 20"
  falseApprovals: 2, // docs/bench-analysis.md:80 "False approvals, original labels: 2 / 20"
  falseApprovalsCleaned: 0, // docs/bench-analysis.md:82 "False approvals, cleaned labels: 0 / 16"
  trulyFailed: 16, // docs/bench-analysis.md:82
  goldProven: 3, // docs/bench-analysis.md:83 "Correct approvals (gold proven): 3 / 20"
  unprovenStored: 12, // docs/spec/DECISIONS.md:41 "unproven 12" (stored verdicts)
  errors: 9, // docs/spec/DECISIONS.md:41 "errors 9"
  errorsInfra: 4, // docs/spec/DECISIONS.md:42 "Infrastructure, 4"
  errorsBadPatch: 2, // docs/spec/DECISIONS.md:42 "Bench input, 2"
  errorsBudget: 3, // docs/spec/DECISIONS.md:42 "Real verdict errors, 3: budget_usd cap hit"
  medianUsd: "0.46", // docs/spec/DECISIONS.md:41 and README.md:90 "median $0.46"
  medianSeconds: 198, // docs/spec/DECISIONS.md:41 and README.md:90 "198 s per review"
  goldWrongExpected: 5, // docs/bench-analysis.md:23 "Wrong expected value: 5"
};
