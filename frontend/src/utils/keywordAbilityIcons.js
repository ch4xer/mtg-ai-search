const MANA_FONT_ABILITY_ICONS = new Set(`
  activated adamant adapt addendum adventure afflict afterlife aftermath alliance amass
  amass-orcs amass-zombies annihilator ascend backup bargain battle-cry blitz boast
  cannot-block cannot-untap case-solved case-solved-print casualty celebration changeling
  channel cleave cloak cohort collect-evidence combat-condition companion constellation
  convoke convoke-original copy corrupted coven craft crew crime cycling d20
  daybound-nightbound day-night deathtouch decayed defender delirium delve descend detain
  devotion dfc discover disguise disturb domain double-strike dungeon eerie embalm enchant
  enlist enrage enrage-original escape eternalize evolve exalted exile expend exploit explore
  fabricate fading fear ferocious finality first-strike flash flying forage forestwalk foretell
  for-mirrodin gift goad haktos-the-unscarred haste haunt hexproof hexproof-black
  hexproof-blue hexproof-green hexproof-red hexproof-white hideaway impending improvise
  incubate indestructible infect ingest intimidate investigate islandwalk jumpstart kicker
  landfall learn legendary lifelink lifelink-original magecraft manifest-dread meld menace
  mentor monstrous morph mountainwalk must-attack mutate ninjutsu obscura offspring outlast
  party phyrexian plainswalk plot prevent-damage proliferate protection protection-black
  protection-blue protection-green protection-red protection-white prototype prowess raid
  rally reach read-ahead reconfigure regenerate renowned revolt ring-bearer riot
  robber-of-the-rich role-cursed role-monster role-royal role-sorceror role-wicked
  role-young-hero saddle shroud skulk soulshift specialize spectacle spree static
  summoning-sickness surveil surveil-original survival suspect swampwalk temporary-control
  the-ring-tempts-you totem-armor toxic training trample transform triggered unblockable
  undergrowth undying unearth valiant vigilance ward
`.trim().split(/\s+/));

const ICON_ALIASES = {
  daybound: "daybound-nightbound",
  nightbound: "daybound-nightbound",
  "jump-start": "jumpstart",
};

const FALLBACK_ICON = "activated";

function keywordToIconSlug(name) {
  const normalized = String(name || "")
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const slug = ICON_ALIASES[normalized] || normalized;
  return MANA_FONT_ABILITY_ICONS.has(slug) ? slug : FALLBACK_ICON;
}

export function getKeywordAbilityIconClass(name) {
  return `ms ms-ability-${keywordToIconSlug(name)}`;
}
