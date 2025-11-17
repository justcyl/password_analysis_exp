#!/usr/bin/env python3
"""
用户名与口令共享子串/词汇复用分析。

输出（按数据集命名）：
1. mid/analysis/username_overlap/username_overlap_<dataset>.csv - 子串出现次数与覆盖率
2. analysis/report_assets/username_overlap/username_overlap_<dataset>_{pie,bar}.png - Top-N 共享子串占比
3. mid/pcfg_advance/lib/username_tokens_<dataset>.txt - PCFG 可直接引用的 token 概率表
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from project_paths import DATA_DIR, analysis_mid_dir, pcfg_mid_dir, report_assets_dir

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

CSV_OUTPUT_DIR = analysis_mid_dir("username_overlap")
TOKEN_OUTPUT_DIR = pcfg_mid_dir("lib")
CHART_OUTPUT_DIR = report_assets_dir("username_overlap")
CHART_MID_DIR = analysis_mid_dir("username_overlap_charts")

TOKEN_PATTERN = re.compile(r"[A-Za-z]+|\d{2,}|[A-Za-z]\d+|\d+[A-Za-z]+")


@dataclass
class Record:
    dataset: str
    username: str
    password: str
    email: str


def parse_record(raw: str, dataset: str) -> Record | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None

    if "#" in line:
        parts = [p.strip() for p in line.split("#")]
        if len(parts) >= 2:
            username = parts[0]
            password = parts[1]
            email = parts[2] if len(parts) > 2 else ""
            if username and password:
                return Record(dataset=dataset, username=username, password=password, email=email)

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
                email = parts[2]
            if username and password:
                return Record(dataset=dataset, username=username, password=password, email=email)
    return None


def load_records() -> List[Record]:
    records: List[Record] = []
    sources = [
        ("csdn", DATA_DIR / "csdn.txt"),
        ("yahoo", DATA_DIR / "yahoo.txt"),
    ]
    for dataset, path in sources:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                rec = parse_record(raw, dataset)
                if rec:
                    records.append(rec)
    return records


def tokenize(text: str) -> Set[str]:
    tokens: Set[str] = set()
    cleaned = text.strip()
    if not cleaned:
        return tokens
    tokens.add(cleaned)
    for chunk in re.split(r"[\W_]+", cleaned):
        if chunk:
            tokens.add(chunk)
    for match in TOKEN_PATTERN.finditer(cleaned):
        tokens.add(match.group(0))
    return tokens


def username_tokens(username: str, email: str) -> Set[str]:
    tokens = set()
    candidates = [username]
    if email:
        local, _, domain = email.partition("@")
        domain_base = domain.split(".")[0] if domain else ""
        candidates.extend([local, domain_base, domain])
    for candidate in candidates:
        tokens.update(tokenize(candidate))
    # 对邮箱 local 的拆分（如 john.doe -> john, doe）
    split_candidates: List[str] = []
    for candidate in candidates:
        split_candidates.extend(candidate.replace("@", ".").split("."))
    for candidate in split_candidates:
        if candidate:
            tokens.update(tokenize(candidate))
    return {tok for tok in tokens if tok}


def password_tokens(password: str) -> Set[str]:
    return tokenize(password)


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
                    prev[j] + 1,  # deletion
                    curr[j - 1] + 1,  # insertion
                    prev[j - 1] + cost,  # substitution
                )
            )
        prev = curr
    return prev[-1]


def run_analysis(records: List[Record]) -> Tuple[Counter, Counter]:
    counts = Counter()
    token_counter = Counter()

    for record in records:
        u_tokens = username_tokens(record.username, record.email)
        p_tokens = password_tokens(record.password)
        u_lower = {t.lower() for t in u_tokens}
        p_lower = {t.lower() for t in p_tokens}

        exact = bool(u_tokens & p_tokens)
        lower = bool(u_lower & p_lower)

        lev_match = False
        if not lower:
            for ut in u_lower:
                for pt in p_lower:
                    if abs(len(ut) - len(pt)) > 1:
                        continue
                    if levenshtein(ut, pt) <= 1:
                        lev_match = True
                        break
                if lev_match:
                    break

        counts["pairs_total"] += 1

        if exact:
            counts["exact_match"] += 1
        if lower:
            counts["lower_match"] += 1
            token_counter.update(u_lower & p_lower)
        if lev_match:
            counts["lev1_match"] += 1

    return counts, token_counter


def write_csv(dataset: str, counts: Counter, token_counter: Counter) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    csv_path = CSV_OUTPUT_DIR / f"username_overlap{suffix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["token", "count", "coverage_percent"])
        total_pairs = counts["pairs_total"] or 1
        for token, cnt in token_counter.most_common():
            coverage = cnt / total_pairs * 100
            writer.writerow([token, cnt, f"{coverage:.2f}"])
    return csv_path


def _chart_dir(dataset: str) -> Path:
    return CHART_MID_DIR if dataset == "all" else CHART_OUTPUT_DIR


def write_figures(dataset: str, counts: Counter, token_counter: Counter) -> Tuple[Path, Path]:
    suffix = "" if dataset == "all" else f"_{dataset}"
    top_tokens = token_counter.most_common(10)

    labels = [t for t, _ in top_tokens]
    values = [cnt for _, cnt in top_tokens]
    total_top = sum(values) or 1
    percents = [v / total_top * 100 for v in values]

    # 饼状图
    fig_pie, ax_pie = plt.subplots(figsize=(6, 6))
    ax_pie.pie(
        percents,
        labels=labels,
        autopct="%.1f%%",
        startangle=90,
        counterclock=False,
    )
    ax_pie.set_title(f"用户名子串复用 Top-10（{dataset}）")
    output_dir = _chart_dir(dataset)
    pie_path = output_dir / f"username_overlap{suffix}_pie.png"
    fig_pie.tight_layout()
    fig_pie.savefig(pie_path, dpi=200)
    plt.close(fig_pie)

    # 条形图
    fig_bar, ax_bar = plt.subplots(figsize=(8, 5))
    x_pos = range(len(labels))
    ax_bar.bar(x_pos, percents, color="#1f77b4")
    ax_bar.set_xticks(list(x_pos))
    ax_bar.set_xticklabels(labels, rotation=30, ha="right")
    ax_bar.set_ylabel("占比（%）")
    ax_bar.set_title(f"用户名子串复用 Top-10（{dataset}）")
    ax_bar.grid(True, axis="y", linestyle="--", alpha=0.4)
    bar_path = output_dir / f"username_overlap{suffix}_bar.png"
    fig_bar.tight_layout()
    fig_bar.savefig(bar_path, dpi=200)
    plt.close(fig_bar)

    return pie_path, bar_path


def write_token_file(
    dataset: str,
    counts: Counter,
    token_counter: Counter,
    coverage_threshold: float,
    max_tokens: int,
) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    filename = f"username_tokens{suffix}.txt"
    output_path = TOKEN_OUTPUT_DIR / filename

    total_pairs = counts["pairs_total"] or 1
    filtered = []
    for token, cnt in token_counter.most_common():
        coverage = cnt / total_pairs * 100
        if coverage >= coverage_threshold:
            filtered.append((token, cnt))
        if len(filtered) >= max_tokens:
            break

    if not filtered:
        filtered = token_counter.most_common(max_tokens)

    total_selected = sum(cnt for _, cnt in filtered) or 1
    with output_path.open("w", encoding="utf-8") as fh:
        for token, cnt in filtered:
            prob = cnt / total_selected
            fh.write(f"{token} {prob:.6f}\n")
    return output_path


def print_summary(dataset: str, counts: Counter) -> None:
    total = counts.get("pairs_total", 0) or 1
    print(f"=== {dataset} ===")
    print(f"pairs_total: {counts.get('pairs_total',0)}")
    for key in ("exact_match", "lower_match", "lev1_match"):
        value = counts.get(key, 0)
        pct = value / total * 100 if total else 0
        print(f"{key}: {value} ({pct:.2f}%)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用户名与口令共享子串分析")
    parser.add_argument(
        "--dataset",
        "-d",
        action="append",
        choices=["csdn", "yahoo", "all"],
        help="指定需要分析的数据集，可多次传入（默认：all）",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=0.01,
        help="写入 token 文件时的最低覆盖率阈值（百分比，默认 0.01）",
    )
    parser.add_argument(
        "--max-token-count",
        type=int,
        default=200,
        help="写入 token 文件的最大条数",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records()
    if not records:
        raise SystemExit("未找到包含用户名/口令的数据文件。")

    grouped: Dict[str, List[Record]] = defaultdict(list)
    for record in records:
        grouped[record.dataset].append(record)

    datasets = args.dataset or ["all"]
    processed = False
    for dataset in datasets:
        if dataset == "all":
            dataset_records = [rec for rec in records]
        else:
            dataset_records = grouped.get(dataset, [])
            if not dataset_records:
                print(f"[WARN] 数据集 {dataset} 无记录，跳过。")
                continue
        counts, token_counter = run_analysis(dataset_records)
        if not counts["pairs_total"]:
            print(f"[WARN] 数据集 {dataset} 无有效样本，跳过。")
            continue
        write_csv(dataset, counts, token_counter)
        write_figures(dataset, counts, token_counter)
        write_token_file(dataset, counts, token_counter, args.coverage_threshold, args.max_token_count)
        print_summary(dataset, counts)
        processed = True

    if not processed:
        raise SystemExit("没有生成任何分析结果。")


if __name__ == "__main__":
    main()
