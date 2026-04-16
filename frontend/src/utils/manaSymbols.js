/**
 * Parse a mana cost string like "{2}{W}{U}" into an array of symbol descriptors.
 * Returns array of objects: { classes: string, half: boolean }
 * e.g. [{classes: "ms-2", half: false}, {classes: "ms-w ms-cost", half: true}]
 */
export function parseManaCost(manaCost) {
  if (!manaCost) return [];

  // Match patterns like {W}, {2}, {2/B}, {HW}, {T}, etc.
  const symbolRegex = /\{([^}]+)\}/g;
  const symbols = [];

  let match;
  while ((match = symbolRegex.exec(manaCost)) !== null) {
    const content = match[1].toLowerCase();

    // Handle half mana like {HW}, {HR}, etc.
    if (content.startsWith("h") && content.length === 2) {
      const color = content[1];
      symbols.push({ classes: `ms-${color} ms-cost`, half: true });
    } else if (content.includes("/")) {
      // Handle hybrid mana like "2/B", "W/U", "C/B" → combined class ms-2b, ms-wu, ms-cb
      const parts = content.split("/");
      symbols.push({ classes: `ms-${parts[0]}${parts[1]} ms-cost`, half: false });
    } else if (content === "t") {
      symbols.push({ classes: "ms-tap", half: false });
    } else {
      symbols.push({ classes: `ms-${content}`, half: false });
    }
  }

  return symbols;
}

/**
 * Get mana symbol descriptor for a single symbol content (e.g., "w", "t", "2", "hw")
 * Returns { classes: string, half: boolean }
 */
function getSymbolDescriptor(content) {
  const lower = content.toLowerCase();

  if (lower.startsWith("h") && lower.length === 2 && !lower.includes("/")) {
    return { classes: `ms-${lower[1]} ms-cost`, half: true };
  }

  if (lower.includes("/")) {
    const parts = lower.split("/");
    return { classes: `ms-${parts[0]}${parts[1]} ms-cost`, half: false };
  }

  if (lower === "t") return { classes: "ms-tap", half: false };
  if (lower === "q") return { classes: "ms-untap", half: false };

  return { classes: `ms-${lower}`, half: false };
}

/**
 * Parse oracle text and replace mana symbols with icon elements.
 * Returns an array of React elements (text spans and icon elements).
 * @param {string} text - The oracle text to parse
 * @param {React.createElement} createElement - React createElement function
 */
export function parseOracleText(text, createElement) {
  if (!text) return null;

  // Split text by mana symbols like {W}, {2}, {T}, etc.
  const parts = [];
  const regex = /(\{[^}]+\})/g;
  let lastIndex = 0;
  let key = 0;

  let match;
  while ((match = regex.exec(text)) !== null) {
    // Add text before the symbol
    if (match.index > lastIndex) {
      parts.push(createElement("span", { key: key++ }, text.slice(lastIndex, match.index)));
    }

    // Add the symbol as an icon
    const symbolContent = match[1].slice(1, -1); // Remove { and }
    const sym = getSymbolDescriptor(symbolContent);
    if (sym.half) {
      parts.push(
        createElement("span", { key: key++, className: "ms-half" },
          createElement("i", { className: `ms ${sym.classes}`, "aria-hidden": "true" })
        )
      );
    } else {
      parts.push(
        createElement("i", {
          key: key++,
          className: `ms ${sym.classes}`,
          "aria-hidden": "true",
        })
      );
    }

    lastIndex = match.index + match[1].length;
  }

  // Add remaining text after last symbol
  if (lastIndex < text.length) {
    parts.push(createElement("span", { key: key++ }, text.slice(lastIndex)));
  }

  return parts.length > 0 ? parts : text;
}

/**
 * Map card colors to mana symbol classes (for mana cost display)
 */
export const COLOR_TO_MANA_CLASS = {
  W: "ms-w",
  U: "ms-u",
  B: "ms-b",
  R: "ms-r",
  G: "ms-g",
  C: "ms-c", // colorless
};

/**
 * Generate Color Indicator classes for a card's colors.
 * Returns class string like "ms ms-ci ms-ci-1 ms-ci-w" for single color,
 * or "ms ms-ci ms-ci-2 ms-ci-wu" for two colors.
 */
export function getColorIndicatorClass(colors) {
  if (!colors || colors.length === 0) return null;

  const sortedColors = [...colors].sort().join("");
  const count = colors.length;

  // Single color: ms-ci-1 + ms-ci-{color}
  // Multi color: ms-ci-{count} + ms-ci-{colors}
  return `ms ms-ci ms-ci-${count} ms-ci-${sortedColors.toLowerCase()}`;
}

/**
 * Map card types to mana symbol classes for type icons
 */
export const TYPE_TO_MANA_CLASS = {
  Creature: "ms-creature",
  Planeswalker: "ms-planeswalker",
  Instant: "ms-instant",
  Sorcery: "ms-sorcery",
  Enchantment: "ms-enchantment",
  Artifact: "ms-artifact",
  Land: "ms-land",
  Battle: "ms-battle",
  Other: null, // No specific icon for Other
};