#!/usr/bin/env python3
"""从万智牌官方规则文件中提取 Keyword Abilities (702章节)。"""

import argparse
import os
import re
import requests
from urllib.parse import quote


def _default_output_path() -> str:
    """返回默认的输出文件路径。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "..", "data", "keyword_ability.txt")


def get_latest_rules_url() -> str:
    """从规则页面获取最新的规则文件下载链接。"""
    page_url = "https://magic.wizards.com/en/rules"
    resp = requests.get(page_url, timeout=30)
    resp.raise_for_status()

    # 查找 .txt 链接
    match = re.search(r'href="([^"]+\.txt)"', resp.text)
    if match:
        raw_url = match.group(1)
        # URL 编码空格
        return quote(raw_url, safe=":/")
    raise ValueError("Could not find rules .txt link on page")


def fetch_rules_txt(url: str | None = None) -> str:
    """下载完整的万智牌规则文件。"""
    if url is None:
        url = get_latest_rules_url()
    print(f"Downloading from {url}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    # 检测编码，Wizards 的 txt 文件通常是 Windows-1252
    content = resp.content
    try:
        # 尝试 UTF-8
        return content.decode("utf-8")
    except UnicodeDecodeError:
        # 回退到 Windows-1252
        return content.decode("windows-1252")


def extract_keyword_abilities(rules_text: str) -> str:
    """从规则文本中提取 702 章节（Keyword Abilities），跳过 702.1 介绍段落。

    检测策略：真正的内容以 "702.2." 开头（Deathtouch），
    结束于 "703.1." 开头。
    """
    # 处理 Windows 行尾
    rules_text = rules_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = rules_text.splitlines()
    result_lines = []
    in_section = False

    for line in lines:
        stripped = line.strip()
        # 检测进入 702 章节（从 702.2. Deathtouch 开始，跳过 702.1 介绍）
        if stripped.startswith("702.2."):
            in_section = True

        # 检测离开 702 章节（703.1. 是 Turn-Based Actions 的第一条子规则）
        if stripped.startswith("703.1."):
            break

        # 在章节内，保留所有行
        if in_section:
            result_lines.append(line)

    return "\n".join(result_lines)


def download_and_extract_keywords(output_path: str | None = None, url: str | None = None) -> str:
    """下载规则文件并提取关键词，写入指定路径。供其他模块调用。

    Args:
        output_path: 输出文件路径，默认为 backend/data/keyword_ability.txt
        url: 规则文件 URL，默认自动从官网获取

    Returns:
        输出文件的路径
    """
    if output_path is None:
        output_path = _default_output_path()

    rules_text = fetch_rules_txt(url)
    keyword_text = extract_keyword_abilities(rules_text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(keyword_text)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="提取万智牌 702 章节 Keyword Abilities")
    parser.add_argument(
        "-i", "--input",
        help="本地规则文件路径（不指定则从官网下载）",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出文件路径（默认: backend/data/keyword_ability.txt）",
    )
    parser.add_argument(
        "-u", "--url",
        help="规则文件下载 URL（不指定则自动从官网获取最新链接）",
    )
    args = parser.parse_args()

    # 设置默认输出路径
    output_path = args.output or _default_output_path()

    # 获取规则文本
    if args.input:
        print(f"Reading from {args.input}...")
        with open(args.input, "r", encoding="utf-8") as f:
            rules_text = f.read()
    else:
        rules_text = fetch_rules_txt(args.url)

    # 提取 702 章节
    keyword_text = extract_keyword_abilities(rules_text)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(keyword_text)

    print(f"Extracted {len(keyword_text.splitlines())} lines to {output_path}")

    # 显示前几行预览
    preview_lines = keyword_text.splitlines()[:10]
    print("\nPreview (first 10 lines):")
    for line in preview_lines:
        print(f"  {line}")


if __name__ == "__main__":
    main()