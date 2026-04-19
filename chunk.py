import re
import json


def parse_mtg_rules(text):
    text = text.replace("’", "'")
    result = {}

    current_name = None
    current_lines = []

    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 匹配新的 keyword 开头：702.2. Deathtouch（跳过 702.1）
        header_match = re.match(r"702\.(\d+)\.\s+(.+)", line)
        if header_match and int(header_match.group(1)) >= 2:
            # 保存上一个
            if current_name:
                result[current_name] = " ".join(current_lines)

            current_name = header_match.group(2).strip()
            current_lines = []
            continue

        # 匹配子规则：702.2a ...
        sub_match = re.match(r"702\.\d+[a-z]\s+(.+)", line)
        if sub_match and current_name:
            current_lines.append(sub_match.group(1).strip())

    # 保存最后一个
    if current_name:
        result[current_name] = " ".join(current_lines)

    return result


# ===== 测试 =====
text = """
702. Keyword Abilities

702.1. Most abilities describe exactly what they do in the card’s rules text. Some, though, are very common or would require too much space to define on the card. In these cases, the object lists only the name of the ability as a “keyword”; sometimes reminder text summarizes the game rule.

702.1a If an effect refers to a “[keyword ability] cost,” it refers only to the variable costs for that keyword.
Example: Varolz, the Scar-Striped has an ability that says “Each creature card in your graveyard has scavenge. The scavenge cost is equal to its mana cost.” A creature card’s scavenge cost is an amount of mana equal to its mana cost, and the activation cost of the scavenge ability is that amount of mana plus “Exile this card from your graveyard.”

702.1b An effect that grants an object a keyword ability may define a variable in that ability based on characteristics of that object or other information about the game state. For these abilities, the value of that variable is constantly reevaluated.
Example: Volcano Hellion has the ability “This creature has echo {X}, where X is your life total. If your life total is 10 when Volcano Hellion’s echo ability triggers but 5 when it resolves, the echo cost to pay is {5}.
Example: Fire//Ice is a split card whose halves have the mana costs {1}{R} and {1}{U}. Past in Flames reads “Each instant and sorcery card in your graveyard gains flashback until end of turn. The flashback cost is equal to its mana cost.” Fire//Ice has “Flashback {2}{U}{R}” while it is in your graveyard, but if you choose to cast Fire, the resulting spell has “Flashback {1}{R}.

702.1c An effect may state that “the same is true for” a list of keyword abilities or similar. If one of those keyword abilities has variants or variables and the effect grants that keyword or counters of that keyword to one or more objects and/or players, it grants each appropriate variant and variable of that keyword.
Example: Concerted Effort is an enchantment that reads “At the beginning of each upkeep, creatures you control gain flying until end of turn if a creature you control has flying. The same is true for fear, first strike, double strike, landwalk, protection, trample, and vigilance.” As that triggered ability resolves, each landwalk and protection ability from among creatures you control is granted to each creature you control.

702.1d An effect may refer to an object “with [keyword ability]” or “that has [keyword ability]. This means the same thing as an object “with a [keyword ability] ability” or an object “that has a [keyword ability] ability.

702.2. Deathtouch

702.2a Deathtouch is a static ability.

702.2b A creature with toughness greater than 0 that’s been dealt damage by a source with deathtouch since the last time state-based actions were checked is destroyed as a state-based action. See rule 704.

702.2c Any nonzero amount of combat damage assigned to a creature by a source with deathtouch is considered to be lethal damage for the purposes of determining if excess damage is being dealt.

702.2d The deathtouch rules function no matter what zone an object with deathtouch deals damage from.

702.2e If an object changes zones before an effect causes it to deal damage, its last known information is used to determine whether it had deathtouch.

702.2f Multiple instances of deathtouch on the same object are redundant.

702.3. Defender

702.3a Defender is a static ability.

702.3b A creature with defender can’t attack.

702.3c Multiple instances of defender on the same creature are redundant.
"""

parsed = parse_mtg_rules(text)

print(json.dumps(parsed, indent=2))
