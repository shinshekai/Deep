import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

describe("Badge component", () => {
  it("renders correctly with default props", () => {
    render(<Badge>Test Badge</Badge>);
    const badge = screen.getByText("Test Badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-zinc-800");
  });

  it("renders correctly with dot prop", () => {
    const { container } = render(<Badge dot>Test Badge</Badge>);
    const dot = container.querySelector("span > span");
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveClass("bg-zinc-500");
  });
});
