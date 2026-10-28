import type { NextConfig } from "next";

const config: NextConfig = {
  // The fake GitHub mode reads recorded runs from fixtures/ at request time.
  outputFileTracingIncludes: { "/api/**": ["./fixtures/**"] },
};

export default config;
