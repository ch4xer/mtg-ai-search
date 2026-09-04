import { describe, expect, it } from "vitest";
import {
  buildAiSearchUrl,
  buildExactSearchUrl,
  exactSearchToRequest,
  parseSearchLocation,
} from "./searchUrlState.js";

describe("searchUrlState", () => {
  it("round-trips an AI query with Chinese and special characters", () => {
    const url = buildAiSearchUrl("  抽两张牌 + 失去生命  ");
    const parsed = parseSearchLocation("/", url.slice(1));
    expect(parsed).toEqual({ mode: "ai", query: "抽两张牌 + 失去生命" });
  });

  it("canonicalizes similar tags and keeps the source card", () => {
    const url = buildExactSearchUrl({ functionTags: ["tempo", "draw", "draw"], sourceCardId: "card/id" });
    expect(url).toBe("/exact-match?q=tag%3Adraw+tag%3Atempo&source=card%2Fid");
    expect(url).not.toContain("&tag=");
    expect(parseSearchLocation("/exact-match", url.split("?")[1])).toMatchObject({
      mode: "exact",
      exact: {
        functionTags: ["draw", "tempo"],
        sourceCardId: "card/id",
      },
    });
  });

  it("round-trips exact-match filters and omits default page", () => {
    const url = buildExactSearchUrl({
      q: "Elf lord",
      colors: new Set(["G", "W"]),
      types: ["Creature"],
      rarity: "rare",
      setCodes: ["LTR", "ltr"],
      keywords: ["Vigilance", "Flying"],
      subtypes: ["Elf"],
      functionTags: ["mana-dork", "lord"],
      sourceCardId: "source-card",
      cmcMin: "2",
      cmcMax: "4",
      powerMin: "",
      powerMax: "5",
      toughnessMin: "1",
      toughnessMax: "",
      page: 1,
    });
    const parsed = parseSearchLocation("/exact-match", url.split("?")[1]);
    expect(parsed.mode).toBe("exact");
    expect(parsed.exact).toMatchObject({
      q: "Elf lord",
      colors: ["G", "W"],
      types: ["Creature"],
      rarity: "rare",
      setCodes: ["ltr"],
      keywords: ["Flying", "Vigilance"],
      subtypes: ["Elf"],
      functionTags: ["lord", "mana-dork"],
      sourceCardId: "source-card",
      cmcMin: "2",
      cmcMax: "4",
      powerMax: "5",
      toughnessMin: "1",
      page: 1,
    });
    expect(url).not.toContain("page=");
    expect(url).not.toContain("&tag=");
    expect(exactSearchToRequest(parsed.exact)).toMatchObject({
      q: "Elf lord",
      colors: ["G", "W"],
      set_codes: ["ltr"],
      function_tags: ["lord", "mana-dork"],
      exclude_card_id: "source-card",
      cmc_min: 2,
      page: 1,
      page_size: 60,
    });
  });

  it("stores free text and quoted function-tag labels in one q parameter", () => {
    const url = buildExactSearchUrl({
      q: "Elf payoff",
      functionTags: ["cast trigger you", "magecraft"],
    });
    const params = new URLSearchParams(url.split("?")[1]);

    expect(params.getAll("q")).toEqual(['Elf payoff tag:"cast trigger you" tag:magecraft']);
    expect(params.has("tag")).toBe(false);
    expect(parseSearchLocation("/exact-match", url.split("?")[1]).exact).toMatchObject({
      q: "Elf payoff",
      functionTags: ["cast trigger you", "magecraft"],
    });
  });

  it("ignores invalid enums and numeric values from a URL", () => {
    const parsed = parseSearchLocation(
      "/exact-match",
      "?color=X&type=Wizard&rarity=legendary&cmc_min=-2&power_max=nope&page=0",
    );
    expect(parsed.exact).toMatchObject({
      colors: [],
      types: [],
      rarity: "",
      cmcMin: "",
      powerMax: "",
      page: 1,
    });
  });
});
