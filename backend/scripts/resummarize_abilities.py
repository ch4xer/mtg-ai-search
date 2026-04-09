"""Re-summarize keyword ability descriptions using DeepSeek, then re-embed.

Usage:
    1. Start PostgreSQL: docker compose up db -d
    2. Run: cd backend && python scripts/resummarize_abilities.py
"""

import os
import sys
import time

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mtg:mtg@localhost:5433/mtg")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

SYSTEM_PROMPT = (
    "You are a Magic: The Gathering rules expert. Given a keyword ability name and its full rules description, "
    "write a concise one-sentence summary focusing on the core game effect. "
    "Do NOT mention rule numbers or redundancy notes. "
    "Use simple MTG terms a player would search for.\n\n"
    "Examples:\n"
    'Input: Lifelink - "Lifelink is a static ability. Damage dealt by a source with lifelink causes that source\'s controller to gain that much life..."\n'
    'Output: Damage dealt by this creature also causes its controller to gain that much life.\n\n'
    'Input: Annihilator - "Annihilator is a triggered ability. \\"Annihilator N\\" means \\"Whenever this creature attacks, defending player sacrifices N permanents.\\"..."\n'
    'Output: Whenever this creature attacks, defending player sacrifices permanents.\n\n'
    'Input: Flying - "Flying is an evasion ability. A creature with flying can\'t be blocked except by creatures with flying or reach..."\n'
    'Output: This creature can only be blocked by creatures with flying or reach.\n\n'
    "Return ONLY the summary sentence, nothing else."
)


def summarize_ability(name: str, description: str) -> str:
    """Use DeepSeek to generate a concise summary of an ability."""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{name} - \"{description}\""},
        ],
        temperature=0.1,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


def main():
    from app.embedding import encode

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    # Fetch all abilities
    cur.execute("SELECT id, name, description FROM keyword_abilities ORDER BY name")
    abilities = cur.fetchall()
    print(f"Found {len(abilities)} abilities to summarize")

    # Summarize each ability
    summaries = []
    for i, (aid, name, description) in enumerate(abilities):
        summary = summarize_ability(name, description)
        summaries.append((aid, name, summary))
        print(f"  [{i+1}/{len(abilities)}] {name}: {summary}")
        time.sleep(0.1)  # rate limit

    # Generate embeddings in batch (prepend ability name for better matching)
    print("\nGenerating embeddings...")
    texts = [f"{s[1]}: {s[2]}" for s in summaries]
    embeddings = encode(texts)
    print(f"Generated {len(embeddings)} embeddings")

    # Reconnect for update (original connection may have timed out)
    conn.close()
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    # Update database: description and embedding
    for (aid, name, summary), emb in zip(summaries, embeddings):
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        cur.execute(
            "UPDATE keyword_abilities SET description = %s, embedding = %s::halfvec WHERE id = %s",
            (summary, emb_str, aid),
        )

    conn.commit()
    print(f"Updated {len(summaries)} abilities in database")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
