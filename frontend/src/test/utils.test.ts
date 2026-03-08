import { describe, it, expect } from "vitest";
import { filtersToExtra, scaleValue, scaleLabel, comparatorLabel } from "../utils";
import type { Filters } from "../types";

/* ── filtersToExtra ─────────────────────────────────────────────── */

describe("filtersToExtra", () => {
  const base: Filters = {
    market_id: [],
    ta: [],
    product: [],
    comparator: "BUD",
    scale: "M",
    year: 2025,
    granularity: "year",
  };

  it("returns only comparator when all arrays are empty", () => {
    const result = filtersToExtra(base);
    expect(result).toEqual({ comparator: "BUD" });
  });

  it("includes market_id when markets are selected", () => {
    const result = filtersToExtra({ ...base, market_id: ["US", "CN"] });
    expect(result.market_id).toBe("US,CN");
  });

  it("includes ta when TAs are selected", () => {
    const result = filtersToExtra({ ...base, ta: ["Oncology"] });
    expect(result.ta).toBe("Oncology");
  });

  it("maps product filter to brand_id key", () => {
    const result = filtersToExtra({ ...base, product: ["TAGRISSO", "IMFINZI"] });
    expect(result.brand_id).toBe("TAGRISSO,IMFINZI");
    expect(result).not.toHaveProperty("product");
  });

  it("includes all filters when everything is set", () => {
    const result = filtersToExtra({
      ...base,
      market_id: ["US"],
      ta: ["CVRM"],
      product: ["FARXIGA"],
      comparator: "PYACT",
    });
    expect(result).toEqual({
      market_id: "US",
      ta: "CVRM",
      brand_id: "FARXIGA",
      comparator: "PYACT",
    });
  });
});

/* ── scaleValue ─────────────────────────────────────────────────── */

describe("scaleValue", () => {
  it("formats millions with 1 decimal place (default scale)", () => {
    expect(scaleValue(1234.5, "M")).toBe("1234.5");
  });

  it("formats billions with 2 decimal places", () => {
    expect(scaleValue(1500, "B")).toBe("1.50");
  });

  it("formats thousands as rounded integers with locale separators", () => {
    const result = scaleValue(1.5, "K");
    // 1.5M = 1,500K — locale string may include comma
    expect(result).toBe("1,500");
  });

  it("handles zero", () => {
    expect(scaleValue(0, "M")).toBe("0.0");
    expect(scaleValue(0, "B")).toBe("0.00");
    expect(scaleValue(0, "K")).toBe("0");
  });

  it("handles negative values", () => {
    expect(scaleValue(-500, "M")).toBe("-500.0");
    expect(scaleValue(-500, "B")).toBe("-0.50");
  });

  it("falls back to divisor 1 for unknown scale", () => {
    expect(scaleValue(42, "X")).toBe("42.0");
  });
});

/* ── scaleLabel ─────────────────────────────────────────────────── */

describe("scaleLabel", () => {
  it("returns $M for M", () => {
    expect(scaleLabel("M")).toBe("$M");
  });

  it("returns $K for K", () => {
    expect(scaleLabel("K")).toBe("$K");
  });

  it("returns $B for B", () => {
    expect(scaleLabel("B")).toBe("$B");
  });

  it("defaults to $B for unknown input", () => {
    expect(scaleLabel("Z")).toBe("$B");
  });
});

/* ── comparatorLabel ────────────────────────────────────────────── */

describe("comparatorLabel", () => {
  it("maps BUD to vs Bgt", () => {
    expect(comparatorLabel("BUD")).toBe("vs Bgt");
  });

  it("maps MTP to vs MTP", () => {
    expect(comparatorLabel("MTP")).toBe("vs MTP");
  });

  it("maps RBU2 to vs RBU2", () => {
    expect(comparatorLabel("RBU2")).toBe("vs RBU2");
  });

  it("maps PYACT to vs PY", () => {
    expect(comparatorLabel("PYACT")).toBe("vs PY");
  });

  it("defaults to vs Bgt for unknown comparator", () => {
    expect(comparatorLabel("UNKNOWN")).toBe("vs Bgt");
  });
});
