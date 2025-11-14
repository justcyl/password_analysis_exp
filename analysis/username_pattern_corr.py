#!/usr/bin/env python3
"""
用户名-口令长度与结构耦合分析。

输出：
1. analysis/results/username_pwd_length_corr.png
2. analysis/results/username_pattern_matrix.csv
3. 控制台打印 Pearson/Spearman 相关系数。
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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


def to_pattern(text: str) -> str:
    if not text:
        return "EMPTY"
    def classify(ch: str) -> str:
        if ch.isalpha():
            return "L"
        if ch.isdigit():
            return "D"
        return "S"

    pattern_parts: List[str] = []
    current_type = classify(text[0])
    count = 1
    for ch in text[1:]:
        t = classify(ch)
        if t == current_type:
            count += 1
        else:
            pattern_parts.append(f"{current_type}{count}")
            current_type = t
            count = 1
    pattern_parts.append(f"{current_type}{count}")
    return "".join(pattern_parts)


def pearson(xs: Sequence[int], ys: Sequence[int]) -> float:
    n = len(xs)
    if n == 0:
        return float("nan")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mean_x) ** 2 for x in xs)) * math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den == 0:
        return float("nan")
    return num / den


def rank(values: Sequence[int]) -> List[float]:
    sorted_pairs = sorted((value, idx) for idx, value in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(sorted_pairs):
        j = i
        total_rank = 0.0
        while j < len(sorted_pairs) and sorted_pairs[j][0] == sorted_pairs[i][0]:
            total_rank += j + 1
            j += 1
        avg_rank = total_rank / (j - i)
        for k in range(i, j):
            ranks[sorted_pairs[k][1]] = avg_rank
        i = j
    return ranks


def spearman(xs: Sequence[int], ys: Sequence[int]) -> float:
    if len(xs) != len(ys) or not xs:
        return float("nan")
    rx = rank(xs)
    ry = rank(ys)
    return pearson(rx, ry)


def main() -> None:
    pairs = load_pairs()
    if not pairs:
        raise SystemExit("未找到用户名/口令样本。")

    length_data: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    pattern_matrix: Dict[Tuple[str, str], int] = defaultdict(int)

    for dataset, username, password in pairs:
        lu = len(username)
        lp = len(password)
        length_data[dataset].append((lu, lp))

        up = to_pattern(username)
        pp = to_pattern(password)
        pattern_matrix[(up, pp)] += 1

    # 相关系数输出
    stats = {}
    for dataset, values in length_data.items():
        if not values:
            stats[dataset] = {"pearson": float("nan"), "spearman": float("nan"), "count": 0}
            continue
        arr = np.array(values, dtype=int)
        xs = arr[:, 0]
        ys = arr[:, 1]
        stats[dataset] = {
            "pearson": pearson(xs.tolist(), ys.tolist()),
            "spearman": spearman(xs.tolist(), ys.tolist()),
            "count": arr.shape[0],
        }

    # 绘制散点图
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = {"csdn": "#1f77b4", "yahoo": "#ff7f0e"}
    for dataset, values in length_data.items():
        arr = np.array(values, dtype=int)
        if arr.size == 0:
            continue
        xs = arr[:, 0]
        ys = arr[:, 1]
        n = arr.shape[0]
        ax.scatter(xs, ys, s=12, alpha=0.4, label=f"{dataset} (n={n})", color=colors.get(dataset, None))
        ax.text(
            xs.max(),
            ys.max(),
            f"{dataset} Pearson={stats[dataset]['pearson']:.2f}, Spearman={stats[dataset]['spearman']:.2f}",
            fontsize=8,
            color=colors.get(dataset, "black"),
        )

    ax.set_xlabel("用户名长度")
    ax.set_ylabel("口令长度")
    ax.set_title("用户名-口令长度耦合散点图")
    ax.legend()
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    fig.tight_layout()
    scatter_path = RESULTS_DIR / "username_pwd_length_corr.png"
    fig.savefig(scatter_path, dpi=200)
    plt.close(fig)

    # 写入模式矩阵
    matrix_path = RESULTS_DIR / "username_pattern_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["username_pattern", "password_pattern", "count"])
        for (up, pp), cnt in sorted(pattern_matrix.items(), key=lambda item: item[1], reverse=True):
            writer.writerow([up, pp, cnt])

    print("=== 长度相关性 ===")
    for dataset, values in stats.items():
        print(
            f"{dataset}: n={values['count']} Pearson={values['pearson']:.3f} Spearman={values['spearman']:.3f}"
        )
    print(f"散点图输出：{scatter_path}")
    print(f"模式矩阵输出：{matrix_path}")


if __name__ == "__main__":
    main()
