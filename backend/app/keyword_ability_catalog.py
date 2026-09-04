"""Bilingual keyword explanations and deterministic rules-text fallbacks."""

from __future__ import annotations

import re


CORE_KEYWORD_EXPLANATIONS: dict[str, dict[str, str]] = {
    "cascade": {"name_zh": "倾曳", "description_en": "When you cast this spell, exile cards until you find a cheaper nonland card that you may cast for free.", "description_zh": "施放此咒语时，放逐牌直到找到费用更低的非地牌，你可以不支付费用施放它。"},
    "conjure": {"name_zh": "凭空召集", "description_en": "Create a specified card from outside the game and put it into the stated zone; this is primarily a digital mechanic.", "description_zh": "从游戏外生成一张指定牌并置于所述区域；此机制主要用于数字版万智牌。"},
    "crew": {"name_zh": "搭载", "description_en": "Tap creatures you control with enough total power to turn this Vehicle into an artifact creature for the turn.", "description_zh": "横置由你操控且总力量足够的生物，使此载具本回合成为神器生物。"},
    "cycling": {"name_zh": "循环", "description_en": "Pay the cycling cost and discard this card to draw a card.", "description_zh": "支付循环费用并弃掉此牌，以抓一张牌。"},
    "deathtouch": {"name_zh": "死触", "description_en": "Any amount of damage this source deals to a creature is enough to destroy that creature.", "description_zh": "此来源对生物造成的任何非零伤害都足以消灭该生物。"},
    "defender": {"name_zh": "守军", "description_en": "A creature with defender can't attack.", "description_zh": "具有守军异能的生物不能攻击。"},
    "double strike": {"name_zh": "连击", "description_en": "This creature deals combat damage in both the first-strike and regular combat damage steps.", "description_zh": "此生物会在先攻战斗伤害步骤和正常战斗伤害步骤各造成一次战斗伤害。"},
    "enchant": {"name_zh": "结附", "description_en": "This Aura can target and remain attached only to an object or player matching the stated quality.", "description_zh": "此灵气只能指定并结附于符合所述条件的物件或牌手。"},
    "equip": {"name_zh": "佩带", "description_en": "Pay the equip cost as a sorcery to attach this Equipment to a creature you control.", "description_zh": "仅于法术时机支付佩带费用，将此武具装备在由你操控的生物上。"},
    "first strike": {"name_zh": "先攻", "description_en": "This creature deals combat damage before creatures without first strike.", "description_zh": "此生物会先于不具先攻的生物造成战斗伤害。"},
    "flash": {"name_zh": "闪现", "description_en": "You may cast this card any time you could cast an instant.", "description_zh": "你可以于能够施放瞬间的时机施放此牌。"},
    "flashback": {"name_zh": "返照", "description_en": "You may cast this card from your graveyard for its flashback cost, then exile it.", "description_zh": "你可以从坟墓场支付返照费用施放此牌，然后将它放逐。"},
    "flying": {"name_zh": "飞行", "description_en": "This creature can be blocked only by creatures with flying or reach.", "description_zh": "此生物只能被具飞行或延势异能的生物阻挡。"},
    "food": {"name_zh": "食品", "description_en": "A Food token can be sacrificed for two mana to gain 3 life.", "description_zh": "食品衍生物可以支付两点法术力并牺牲，以获得3点生命。"},
    "fight": {"name_zh": "互斗", "description_en": "Two creatures each deal damage equal to their power to the other.", "description_zh": "两个生物各向对方造成等同于自身力量的伤害。"},
    "haste": {"name_zh": "敏捷", "description_en": "This creature can attack and use tap abilities immediately after it comes under your control.", "description_zh": "此生物刚受你操控时便能攻击，也能立即起动包含横置符号的异能。"},
    "hexproof": {"name_zh": "辟邪", "description_en": "This permanent can't be the target of spells or abilities your opponents control.", "description_zh": "此永久物不能成为由对手操控之咒语或异能的目标。"},
    "indestructible": {"name_zh": "不灭", "description_en": "This permanent can't be destroyed by lethal damage or effects that say destroy.", "description_zh": "此永久物不会因致命伤害或注明“消灭”的效应而被消灭。"},
    "kicker": {"name_zh": "增幅", "description_en": "You may pay an additional cost as you cast this spell to receive its stated bonus.", "description_zh": "施放此咒语时，你可以支付额外的增幅费用来获得所述加成。"},
    "landfall": {"name_zh": "地落", "description_en": "This ability triggers whenever a land enters the battlefield under your control.", "description_zh": "每当一个地在你的操控下进战场时，此异能便会触发。"},
    "lifelink": {"name_zh": "系命", "description_en": "Damage dealt by this source also causes its controller to gain that much life.", "description_zh": "此来源造成伤害时，其操控者同时获得等量生命。"},
    "menace": {"name_zh": "威慑", "description_en": "This creature can't be blocked except by two or more creatures.", "description_zh": "此生物只能被两个或更多生物共同阻挡。"},
    "mill": {"name_zh": "磨牌", "description_en": "To mill cards, put that many cards from the top of a library into its owner's graveyard.", "description_zh": "磨若干牌时，将牌库顶等量的牌置入其拥有者的坟墓场。"},
    "morph": {"name_zh": "变身", "description_en": "You may cast this card face down as a 2/2 creature, then turn it face up for its morph cost.", "description_zh": "你可以将此牌牌面朝下施放为2/2生物，再支付其变身费用将它翻回正面。"},
    "protection": {"name_zh": "保护", "description_en": "Protection prevents damage, enchanting or equipping, blocking, and targeting from sources with the stated quality.", "description_zh": "保护会防止具指定特性的来源对其造成伤害、结附或装备、阻挡以及指定目标。"},
    "prowess": {"name_zh": "灵技", "description_en": "Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.", "description_zh": "每当你施放非生物咒语时，此生物得+1/+1直到回合结束。"},
    "reach": {"name_zh": "延势", "description_en": "This creature can block creatures with flying.", "description_zh": "此生物可以阻挡具飞行异能的生物。"},
    "regenerate": {"name_zh": "重生", "description_en": "A regeneration shield prevents the next destruction event, taps the permanent, and removes it from combat.", "description_zh": "重生护盾会防止下一次消灭，将该永久物横置并移出战斗。"},
    "scry": {"name_zh": "占卜", "description_en": "Look at cards from the top of your library, put any on the bottom, and leave the rest on top in any order.", "description_zh": "检视牌库顶的牌，将任意数量置于牌库底，其余以任意顺序留在牌库顶。"},
    "surveil": {"name_zh": "刺探", "description_en": "Look at cards from the top of your library, put any into your graveyard, and leave the rest on top.", "description_zh": "检视牌库顶的牌，将任意数量置入坟墓场，其余留在牌库顶。"},
    "toxic": {"name_zh": "毒性", "description_en": "When this creature deals combat damage to a player, that player gets the stated number of poison counters.", "description_zh": "此生物对牌手造成战斗伤害时，该牌手得到所述数量的中毒指示物。"},
    "trample": {"name_zh": "践踏", "description_en": "After assigning lethal damage to blockers, this creature may deal its remaining combat damage to the defending player.", "description_zh": "对阻挡者分配致命伤害后，此生物可将剩余战斗伤害分配给防御牌手。"},
    "transform": {"name_zh": "转化", "description_en": "Turn this double-faced card over so its other face is up.", "description_zh": "将此双面牌翻到另一面。"},
    "treasure": {"name_zh": "珍宝", "description_en": "A Treasure token can be tapped and sacrificed to add one mana of any color.", "description_zh": "珍宝衍生物可以横置并牺牲，以加一点任意颜色的法术力。"},
    "vigilance": {"name_zh": "警戒", "description_en": "Attacking doesn't cause this creature to tap.", "description_zh": "此生物攻击时不需横置。"},
    "ward": {"name_zh": "守护", "description_en": "When an opponent targets this permanent, counter that spell or ability unless they pay the ward cost.", "description_zh": "当对手指定此永久物为目标时，除非其支付守护费用，否则反击该咒语或异能。"},
}


_GENERIC_SENTENCE_RE = re.compile(
    r"\b(is (?:a|an) (?:static|activated|triggered|spell|evasion) ability|multiple instances|see rule)\b",
    re.IGNORECASE,
)


def concise_rules_fallback(description: str, limit: int = 240) -> str:
    """Pick a useful short sentence when an LLM-generated summary is unavailable."""
    sentences = [
        part.strip()
        for part in re.findall(r'.+?(?:[.!?]["”’]?(?=\s|$)|$)', description.strip())
        if part.strip()
    ]
    selected = next((sentence for sentence in sentences if not _GENERIC_SENTENCE_RE.search(sentence)), "")
    if not selected and sentences:
        selected = sentences[0]
    if len(selected) <= limit:
        return selected
    return selected[: limit - 1].rstrip() + "…"


def core_keyword_explanation(name: str) -> dict[str, str] | None:
    return CORE_KEYWORD_EXPLANATIONS.get(name.strip().lower())
