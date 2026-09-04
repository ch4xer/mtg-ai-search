import { describe, expect, it } from "vitest";
import { getCardTypeLabel, getSearchableCardTypes } from "./cardTypes.js";

describe("cardTypes", () => {
  it("uses one bilingual catalog for filters and deck groups", () => {
    const chineseTypes = getSearchableCardTypes("zh");
    expect(chineseTypes.find((type) => type.value === "Planeswalker")?.label).toBe("鹏洛客");
    expect(getCardTypeLabel("Planeswalker", "zh")).toBe("鹏洛客");
    expect(getCardTypeLabel("Unknown", "en")).toBe("Other");
  });
});
