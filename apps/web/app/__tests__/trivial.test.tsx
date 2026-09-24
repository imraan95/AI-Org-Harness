import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

describe("trivial", () => {
  it("renders a heading", () => {
    render(<h1>hello</h1>);
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
