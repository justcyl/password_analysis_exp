#!/usr/bin/env python3
"""
用户名与口令共享子串/词汇复用分析。

输出（按数据集命名）：
1. analysis/results/username_overlap_<dataset>.csv - 子串出现次数与覆盖率
2. analysis/results/username_overlap_<dataset>.html - Top-N 共享子串占比
3. pcfg_advance/lib/username_tokens_<dataset>.txt - PCFG 可直接引用的 token 概率表
"""

from __future__ import annotations

import argparse
import csv
import html
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "analysis" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_OUTPUT_DIR = ROOT / "pcfg_advance" / "lib"
TOKEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    csv_path = RESULTS_DIR / f"username_overlap{suffix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["token", "count", "coverage_percent"])
        total_pairs = counts["pairs_total"] or 1
        for token, cnt in token_counter.most_common():
            coverage = cnt / total_pairs * 100
            writer.writerow([token, cnt, f"{coverage:.2f}"])
    return csv_path


def write_html(dataset: str, counts: Counter, token_counter: Counter) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    html_path = RESULTS_DIR / f"username_overlap{suffix}.html"
    top_tokens = token_counter.most_common(10)
    total_top = sum(cnt for _, cnt in top_tokens)
    pie_segments = [
        {
            "label": token,
            "value": cnt,
            "percent": f"{(cnt / total_top * 100):.2f}" if total_top else "0.00",
        }
        for token, cnt in top_tokens
    ]

    with html_path.open("w", encoding="utf-8") as fh:
        fh.write("<!doctype html><html><head><meta charset='utf-8'><title>用户名子串复用占比</title>")
        fh.write("<style>body{font-family:Arial;padding:1.5rem;}table{border-collapse:collapse;}th,td{border:1px solid #ccc;padding:0.4rem 0.8rem;}th{background:#f0f0f0;}</style>")
        fh.write("</head><body>")
        fh.write(f"<h1>用户名子串复用 Top-10（{html.escape(dataset)}）</h1>")
        fh.write("<p>总样本数：{}</p>".format(counts["pairs_total"]))
        fh.write("<table><tr><th>排名</th><th>子串</th><th>命中次数</th><th>占比（%）</th></tr>")
        for idx, seg in enumerate(pie_segments, start=1):
            fh.write(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    idx, html.escape(seg["label"]), seg["value"], seg["percent"]
                )
            )
        fh.write("</table>")
        fh.write("<h2>总体覆盖率</h2>")
        fh.write("<ul>")
        fh.write(
            "<li>大小写不敏感子串复用：{:.2f}% ({}/{})</li>".format(
                counts["lower_match"] / counts["pairs_total"] * 100 if counts["pairs_total"] else 0,
                counts["lower_match"],
                counts["pairs_total"],
            )
        )
        fh.write(
            "<li>Levenshtein≤1 复用：{:.2f}% ({}/{})</li>".format(
                counts["lev1_match"] / counts["pairs_total"] * 100 if counts["pairs_total"] else 0,
                counts["lev1_match"],
                counts["pairs_total"],
            )
        )
        fh.write("</ul>")
        fh.write("</body></html>")
    return html_path


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
        write_html(dataset, counts, token_counter)
        write_token_file(dataset, counts, token_counter, args.coverage_threshold, args.max_token_count)
        print_summary(dataset, counts)
        processed = True

    if not processed:
        raise SystemExit("没有生成任何分析结果。")


if __name__ == "__main__":
    main()
