import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, Disclaimer, EmptyState, ErrorState } from "./ui";

describe("UI states", () => {
  it("Badge humanizes the value", () => {
    render(<Badge value="potentially_out_of_scope" />);
    expect(screen.getByText("potentially out of scope")).toBeInTheDocument();
  });

  it("ErrorState uses an alert role", () => {
    render(<ErrorState message="Boom" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
  });

  it("EmptyState renders title and hint", () => {
    render(<EmptyState title="Nothing here" hint="Try again" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("Disclaimer states findings are not legal advice", () => {
    render(<Disclaimer />);
    expect(screen.getByText(/not legal or accounting advice/i)).toBeInTheDocument();
  });
});
