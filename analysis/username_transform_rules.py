#!/usr/bin/env python3
"""
分析用户名与口令之间的确定性变换规则，并输出统计与热力图。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "analysis" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = [
    ("csdn", DATA_DIR / "csdn.txt"),
    ("yahoo", DATA_DIR / "yahoo.txt"),
]

LEET_MAP = str.maketrans({"a": "@", "e": "3", "i": "1", "o": "0", "s": "5", "l": "1"})


def parse_line(raw: str, dataset: str) -> Tuple[str, str] | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    if "#" in line:
        parts = [p.strip() for p in line.split("#")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    if ":" in line:
        parts = [p.strip() for p in line.split(":")]
        if len(parts) >= 3:
            if dataset == "yahoo":
                email = parts[1]
                username = email.split("@")[0] if "@" in email else parts[1]
                password = parts[2]
            else:
                username = parts[0]
                password = parts[1]
            if username and password:
                return username, password
    return None


def load_pairs() -> List[Tuple[str, str, str]]:
    pairs: List[Tuple[str, str, str]] = []
    for dataset, path in SOURCES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                parsed = parse_line(raw, dataset)
                if parsed:
                    username, password = parsed
                    pairs.append((dataset, username, password))
    return pairs


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + cost,
                )
            )
        prev = curr
    return prev[-1]


def classify(username: str, password: str) -> Set[str]:
    categories: Set[str] = set()
    u = username
    p = password
    u_lower = u.lower()
    p_lower = p.lower()

    if not u or not p:
        categories.add("invalid")
        return categories

    if u == p:
        categories.add("exact_case_sensitive")
    if u_lower == p_lower:
        categories.add("exact_casefold")

    if p_lower.startswith(u_lower):
        suffix = p_lower[len(u_lower) :]
        if suffix.isdigit() and suffix:
            categories.add("suffix_digits")
        elif suffix:
            categories.add("suffix_append")
        else:
            categories.add("exact_casefold")

    if p_lower.endswith(u_lower) and len(p_lower) > len(u_lower):
        prefix = p_lower[: -len(u_lower)]
        if prefix.isdigit():
            categories.add("prefix_digits")
        elif prefix:
            categories.add("prefix_append")

    if u_lower in p_lower and len(p_lower) > len(u_lower):
        categories.add("contains_username")

    if p_lower == u_lower[::-1]:
        categories.add("reverse_username")

    if p_lower == u_lower.translate(LEET_MAP):
        categories.add("leet_substitution")

    if p_lower == u_lower * 2:
        categories.add("repeated_username")

    if p_lower.startswith(u_lower) and p_lower.endswith(u_lower) and len(p_lower) > 2 * len(u_lower):
        categories.add("wrap_username")

    dist = levenshtein(u_lower, p_lower)
    if dist <= 1:
        categories.add("edit_distance_1")
    elif dist == 2:
        categories.add("edit_distance_2")

    if not categories:
        categories.add("no_relation")
    return categories


def ensure_category_order(categories: Set[str]) -> List[str]:
    preferred = [
        "exact_case_sensitive",
        "exact_casefold",
        "suffix_digits",
        "suffix_append",
        "prefix_digits",
        "prefix_append",
        "contains_username",
        "reverse_username",
        "leet_substitution",
        "repeated_username",
        "wrap_username",
        "edit_distance_1",
        "edit_distance_2",
        "no_relation",
    ]
    ordered = [c for c in preferred if c in categories]
    for c in sorted(categories):
        if c not in preferred:
            ordered.append(c)
    return ordered


def main() -> None:
    pairs = load_pairs()
    if not pairs:
        raise SystemExit("未找到用户名/口令样本。")

    global_counter = Counter()
    dataset_counter: Dict[str, Counter] = defaultdict(Counter)
    examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for dataset, username, password in pairs:
        cats = classify(username.strip(), password.strip())
        for cat in cats:
            global_counter[cat] += 1
            dataset_counter[dataset][cat] += 1
            if len(examples[cat]) < 5:
                examples[cat].append({"dataset": dataset, "username": username, "password": password})

    matrix_categories = ensure_category_order(set(global_counter.keys()))
    datasets = [ds for ds, _ in SOURCES]
    heatmap_data = np.zeros((len(matrix_categories), len(datasets)), dtype=float)
    for row, cat in enumerate(matrix_categories):
        for col, dataset in enumerate(datasets):
            heatmap_data[row, col] = dataset_counter[dataset].get(cat, 0)

    # 生成 JSON 报告
    json_payload = {
        "total_pairs": sum(counter.get("pairs_total", 0) for counter in dataset_counter.values()) or len(pairs),
        "category_counts": global_counter,
        "dataset_breakdown": {dataset: dict(counter) for dataset, counter in dataset_counter.items()},
        "examples": examples,
    }
    json_path = RESULTS_DIR / "username_transform_stats.json"
    with json_path.open("w", encoding="utf-8") as fh:
        serializable = {
            "category_counts": dict(global_counter),
            "dataset_breakdown": {dataset: dict(counter) for dataset, counter in dataset_counter.items()},
            "examples": examples,
            "total_pairs": len(pairs),
        }
        json.dump(serializable, fh, ensure_ascii=False, indent=2)

    # 绘制热力图
    fig, ax = plt.subplots(figsize=(8, max(4, len(matrix_categories) * 0.4)))
    im = ax.imshow(heatmap_data, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(datasets)))
    ax.set_xticklabels(datasets)
    ax.set_yticks(range(len(matrix_categories)))
    ax.set_yticklabels(matrix_categories)
    ax.set_xlabel("数据集")
    ax.set_ylabel("变换类别")
    ax.set_title("用户名-口令变换热力图（计数）")

    for i in range(len(matrix_categories)):
        for j in range(len(datasets)):
            value = int(heatmap_data[i, j])
            ax.text(j, i, value, ha="center", va="center", color="black" if value < heatmap_data.max() * 0.7 else "white", fontsize=8)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="匹配次数")
    fig.tight_layout()
    heatmap_path = RESULTS_DIR / "username_transform_heatmap.png"
    fig.savefig(heatmap_path, dpi=200)
    plt.close(fig)

    print(f"写入统计：{json_path}")
    print(f"写入热力图：{heatmap_path}")


if __name__ == "__main__":
    main()
