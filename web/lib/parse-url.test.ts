import { describe, expect, it } from "vitest";
import { parseTarget, prUrl } from "./parse-url";

describe("parseTarget", () => {
  it.each([
    ["https://github.com/nufii45/red2fix-minikit/pull/4", { kind: "pr", repo: "nufii45/red2fix-minikit", number: 4 }],
    ["github.com/nufii45/red2fix-minikit/pull/4", { kind: "pr", repo: "nufii45/red2fix-minikit", number: 4 }],
    ["https://www.github.com/a/b/pull/12/files", { kind: "pr", repo: "a/b", number: 12 }],
    ["https://github.com/a/b/pulls/7", { kind: "pr", repo: "a/b", number: 7 }],
    ["  https://github.com/a/b/pull/3?diff=split  ", { kind: "pr", repo: "a/b", number: 3 }],
    ["https://github.com/nufii45/red2fix-minikit", { kind: "repo", repo: "nufii45/red2fix-minikit" }],
    ["https://github.com/a/b.git", { kind: "repo", repo: "a/b" }],
    ["https://github.com/a/b/tree/main/src", { kind: "repo", repo: "a/b" }],
  ])("accepts %s", (input, expected) => {
    expect(parseTarget(input)).toEqual(expected);
  });

  it.each([
    "", "   ", "not a url", "https://gitlab.com/a/b/pull/1", "https://github.com.evil.com/a/b/pull/1",
    "https://evil.com/github.com/a/b/pull/1", "https://github.com/a", "https://github.com/a/b/pull/",
    "https://github.com/a/b/pull/x", "https://github.com/a b/c", "https://github.com/a/b%2Fc/pull/1",
    "javascript:alert(1)", "ftp://github.com/a/b",
  ])("refuses %j", (input) => {
    expect(parseTarget(input)).toBeNull();
  });

  it("builds the exact URL the workflow accepts", () => {
    expect(prUrl("a/b", 4)).toMatch(/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/[1-9]\d*$/);
  });
});
