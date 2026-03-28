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

        # 匹配新的 keyword 开头：702.2. Deathtouch
        header_match = re.match(r"702\.(\d+)\.\s+(.+)", line)
        if header_match:
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
