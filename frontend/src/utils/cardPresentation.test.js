import { describe, expect, it } from "vitest";
import {
  getCardImage,
  getCardPresentation,
  getLocalizedCardName,
  hasDoubleFacedLayout,
  isDoubleFacedCard,
} from "./cardPresentation.js";

const transformCard = {
  name: "Front // Back",
  layout: "transform",
  zh: {
    name: "不应回退到整卡译名",
    card_faces: [{ name: "正面", oracle_text: "正面规则" }],
  },
  card_faces: [
    { name: "Front", oracle_text: "Front rules", image_uris: { normal: "front-normal" } },
    { name: "Back", oracle_text: "Back rules", image_uris: { normal: "back-normal" } },
  ],
};

describe("cardPresentation", () => {
  it("keeps double-faced localization and images aligned to the active face", () => {
    const front = getCardPresentation(transformCard, { language: "zh" });
    const back = getCardPresentation(transformCard, { language: "zh", faceIndex: 1 });

    expect(isDoubleFacedCard(transformCard)).toBe(true);
    expect(hasDoubleFacedLayout({ layout: "transform" })).toBe(true);
    expect(front).toMatchObject({ name: "正面", oracle_text: "正面规则", imageUrl: "front-normal" });
    expect(back).toMatchObject({ name: "Back", oracle_text: "Back rules", imageUrl: "back-normal" });
  });

  it("uses card-level translations and keeps the English name as secondary text", () => {
    const presentation = getCardPresentation({
      name: "Lightning Bolt",
      oracle_text: "Deal 3 damage.",
      zh: { name: "闪电击", oracle_text: "造成3点伤害。" },
    });

    expect(presentation.name).toBe("闪电击");
    expect(presentation.secondaryName).toBe("Lightning Bolt");
    expect(presentation.oracle_text).toBe("造成3点伤害。");
    expect(getLocalizedCardName({ name: "Opt" }, "zh")).toBe("Opt");
  });

  it("lets a selected print override the single-faced image source", () => {
    const card = { name: "Opt", layout: "normal", image_uris: { normal: "default" } };
    expect(getCardImage(card, { imageUris: { normal: "selected" } })).toBe("selected");
  });
});
