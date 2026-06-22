import { describe, it, expect, vi } from "vitest";
import { linkifyCitations } from "@/lib/markdown-citations";

describe("linkifyCitations", () => {
  it("detects [CIT-1-42] pattern", () => {
    const result = linkifyCitations("See source [CIT-1-42] for details.");
    expect(result).toContain('<span class="citation-link"');
    expect(result).toContain('[CIT-1-42]</span>');
    expect(result).toContain('data-citation="CIT-1-42"');
  });

  it("detects [web-1] pattern", () => {
    const result = linkifyCitations("Reference [web-1] shows the data.");
    expect(result).toContain('data-citation="web-1"');
  });

  it("detects [rag-3] pattern", () => {
    const result = linkifyCitations("As shown in [rag-3]");
    expect(result).toContain('data-citation="rag-3"');
  });

  it("detects [doc-3] pattern", () => {
    const result = linkifyCitations("Per [doc-3], the answer is yes.");
    expect(result).toContain('data-citation="doc-3"');
  });

  it("detects comma-separated numeric citations [1,2,3]", () => {
    const result = linkifyCitations("See sources [1,2,3] for more.");
    expect(result).toContain("citation-link");
  });

  it("protects inline code from rewriting", () => {
    const result = linkifyCitations("The file `[doc-3]` is referenced.");
    expect(result).not.toContain("citation-link");
    expect(result).toContain("`[doc-3]`");
  });

  it("protects fenced code blocks from rewriting", () => {
    const result = linkifyCitations("```\nconst ref = [doc-3]\n```\nSee [doc-3].");
    const first = result.indexOf("[doc-3]");
    const last = result.lastIndexOf("[doc-3]");
    expect(first).toBeLessThan(last);
  });

  it("passes through text without citations unchanged", () => {
    const input = "Hello, this is normal text.";
    expect(linkifyCitations(input)).toBe(input);
  });

  it("handles empty string", () => {
    expect(linkifyCitations("")).toBe("");
  });

  it("handles multiple citations on a line", () => {
    const result = linkifyCitations("Sources [1] and [web-1] agree with [CIT-3-7].");
    const matches = result.match(/citation-link/g);
    expect(matches).toHaveLength(3);
  });
});
