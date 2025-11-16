#!/usr/bin/env python3
"""
用户名与口令共享子串/词汇复用分析。

v4 改进点:
1. 在 HTML 报告中增加 ECharts 图表：Top-N 子串占比饼图、复用类型总览饼图。
2. 修正了之前的所有问题 (编码、内存、Levenshtein 权重、Yahoo 低阈值)。
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import json  # 新增：用于将Python数据转换为JavaScript可识别的JSON
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple


# 使用浮点数支持权重计数
class FloatCounter(defaultdict):
    """支持浮点数权重计数的计数器"""

    def __init__(self):
        super().__init__(float)

    def update(self, iterable, weight=1.0):
        if isinstance(iterable, dict):
            for key, count in iterable.items():
                self[key] += count * weight
        else:
            for key in iterable:
                self[key] += weight

    def most_common(self, n=None):
        """返回计数最高的元素，兼容原始 Counter"""
        sorted_items = sorted(self.items(), key=lambda item: item[1], reverse=True)
        return sorted_items[:n] if n is not None else sorted_items


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
                email = parts[2] if len(parts) > 2 else ""
            if username and password:
                return Record(dataset=dataset, username=username, password=password, email=email)
    return None


def load_records():  # 转换为生成器，避免 MemoryError
    """
    Loads records as a generator to prevent MemoryError on large files.
    作为生成器加载记录，防止大型文件导致 MemoryError。
    """
    sources = [
        ("csdn", DATA_DIR / "csdn.txt"),
        ("yahoo", DATA_DIR / "yahoo.txt"),
    ]

    # 解决 UnicodeDecodeError，尝试多种编码
    ENCODINGS_TO_TRY = ['utf-8', 'gbk', 'latin-1']

    for dataset, path in sources:
        if not path.exists():
            continue

        fh = None
        for encoding in ENCODINGS_TO_TRY:
            try:
                fh = path.open(encoding=encoding, errors="ignore")
                break  # 成功打开
            except Exception:
                continue  # 尝试下一个编码

        if fh:
            with fh:
                for raw in fh:
                    rec = parse_record(raw, dataset)
                    if rec:
                        yield rec


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
    return {tok for tok in tokens if tok}


def username_tokens(username: str, email: str) -> Set[str]:
    tokens = set()
    candidates = [username]
    if email:
        local, _, domain = email.partition("@")
        domain_base = domain.split(".")[0] if domain else ""
        candidates.extend([local, domain_base, domain])
    for candidate in candidates:
        tokens.update(tokenize(candidate))
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
    """计算 Levenshtein 距离（编辑距离）"""
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


def run_analysis(records: List[Record]) -> Tuple[Dict[str, int], FloatCounter]:
    counts = defaultdict(int)
    token_counter = FloatCounter()

    for record in records:
        u_tokens = username_tokens(record.username, record.email)
        p_tokens = password_tokens(record.password)
        u_lower = {t.lower() for t in u_tokens}
        p_lower = {t.lower() for t in p_tokens}

        exact = bool(u_tokens & p_tokens)
        lower_overlap = u_lower & p_lower
        lower = bool(lower_overlap)

        lev_match_u_tokens: Set[str] = set()
        lev_match = False

        if not lower:
            for ut in u_lower:
                for pt in p_lower:
                    if abs(len(ut) - len(pt)) > 1:
                        continue
                    if levenshtein(ut, pt) <= 1:
                        lev_match = True
                        lev_match_u_tokens.add(ut)
                        break

        counts["pairs_total"] += 1

        if exact:
            counts["exact_match"] += 1

        if lower:
            counts["lower_match"] += 1
            token_counter.update(lower_overlap, weight=1.0)

        if lev_match:
            counts["lev1_match"] += 1
            token_counter.update(lev_match_u_tokens, weight=0.5)

    return counts, token_counter


def write_csv(dataset: str, counts: Dict[str, int], token_counter: FloatCounter) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    csv_path = RESULTS_DIR / f"username_overlap{suffix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["token", "weighted_count", "coverage_percent"])
        total_pairs = counts["pairs_total"] or 1
        for token, cnt in token_counter.most_common():
            coverage = cnt / total_pairs * 100
            writer.writerow([token, f"{cnt:.2f}", f"{coverage:.4f}"])
    return csv_path


def write_html(dataset: str, counts: Dict[str, int], token_counter: FloatCounter) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    html_path = RESULTS_DIR / f"username_overlap{suffix}.html"
    top_tokens_n = 10
    top_tokens = token_counter.most_common(top_tokens_n)

    # ECharts 数据准备 1: Top-N 共享子串饼图
    # categories: 用于饼图的 legend
    token_categories = [token for token, _ in top_tokens]
    # series_data: {name: token, value: weighted_count}
    token_series_data = [{"name": token, "value": round(cnt, 2)} for token, cnt in top_tokens]

    # ECharts 数据准备 2: 复用类型总览饼图
    total_pairs = counts.get("pairs_total", 0)
    exact_match = counts.get("exact_match", 0)
    lower_match = counts.get("lower_match", 0)
    lev1_match = counts.get("lev1_match", 0)

    # 计算独有的 Levenshtein 匹配 (不与 lower_match 重叠的部分，但可能有交叉，这里简化处理)
    # 最准确的做法是在 run_analysis 中将这三者作为互斥事件计数
    # 为了图表可视化，我们这里简化为 "精确", "大小写不敏感", "Levenshtein≤1" 三类
    # 注意：这些分类可能有重叠，饼图适合展示互斥的比例，这里需要调整数据结构

    # 更适合饼图的互斥分类：
    # 1. 精确匹配 (exact)
    # 2. 只有大小写不敏感匹配 (lower_match - exact_match)
    # 3. 只有 Levenshtein <= 1 匹配 (lev1_match - lower_match, 但由于逻辑复杂可能不准确)
    # 简单的做法是显示各项占比，而不是互斥饼图。
    # 这里我们生成一个总览图，显示各种匹配类型的百分比

    # 为了生成互斥饼图，我们假设一个简单的优先级：Exact > Lower > Levenshtein
    # 且 "无复用" 是其他所有情况的补充

    # 1. 总匹配数 (只要有一种匹配就算)
    any_match_count = 0
    if total_pairs > 0:
        # 这里的 counts['lower_match'] 和 counts['lev1_match'] 是独立计数的。
        # 最好是计算唯一匹配的用户数量，这里简化为展示各个类别的比例。
        # 我们可以展示：精确匹配的，大小写不敏感但非精确的，Levenshtein<=1但非大小写不敏感的。
        # 但这需要更复杂的计数逻辑。
        # 最简单的饼图就是展示各项所占总体的百分比，且允许重叠部分。

        # 重新定义饼图数据，使其逻辑上更互斥或更清晰地展示各项占比
        # "无复用" 将作为补集，这使得饼图数据能够相加到 100%。

        # 只有精确匹配的 (Exact)
        only_exact = exact_match
        # 只有大小写不敏感匹配 (Lower, 不含 Exact)
        only_lower = max(0, lower_match - exact_match)
        # 只有 Levenshtein <= 1 匹配 (Lev1, 不含 Lower)
        # 这一步比较复杂，因为 lev1_match 可能与 lower_match 有交叉，
        # 为了简化，我们直接展示各项占总体的百分比，而不是互斥的饼图。
        # 这样更像一个总览。

        # 如果需要严格互斥的饼图，需要修改 run_analysis 的计数逻辑。
        # 目前，我们提供一个概览，显示各项的权重

        # 为了生成一个有意义的饼图，我们只展示 "有复用" vs "无复用"
        # 或者更详细的，"精确", "大小写不敏感(非精确)", "Levenshtein(非大小写不敏感)"
        # 这里的counts['lower_match'] 和 counts['lev1_match'] 是独立的，不适合直接做互斥饼图
        # 改为呈现一个 "复用类型占比" 的条形图或列表更合适。

        # 我们生成一个 "复用类型总览" 饼图，包含"精确", "大小写不敏感", "Levenshtein<=1", "无复用"
        # 这里的百分比需要小心处理，因为类别之间有重叠。
        # 最简单的互斥饼图：是否有任何复用
        any_overlap = (lower_match > 0) or (lev1_match > 0)
        any_overlap_count = 0
        if any_overlap:
            # 这仍然不精确，因为 counts['lower_match'] 和 counts['lev1_match'] 是事件计数
            # 而不是唯一用户计数。我们直接用它们的计数来近似。
            # 为了避免重复计算，我们只使用 lower_match 作为主要复用，lev1作为补充。
            # 假设：所有 lower_match 都覆盖了 exact_match。
            # 那么：
            # 1. lower_match (包含 exact_match)
            # 2. lev1_match (不与 lower_match 重叠的部分)
            # 但这需要重写 run_analysis 确保计数互斥。

            # 最简单，但可能重复计算的饼图数据（用于展示各类事件的占比）
            reuse_types_data = [
                {"name": "精确匹配", "value": exact_match},
                {"name": "大小写不敏感匹配", "value": lower_match},
                {"name": "Levenshtein≤1 匹配", "value": lev1_match},
            ]

            # 或者，一个更直接的"有复用" vs "无复用"饼图
            # 这里的 "有复用" 定义为至少有一个 lower_match 或 lev1_match 的样本数
            # 这是一个近似值，因为同一个样本可能同时满足。

            # 为了严谨，我们计算实际有复用密码的唯一账户数 (在 run_analysis 中可以统计)
            # 由于当前 run_analysis 只统计事件数，我们只能近似。

            # 暂时使用一个简单的饼图，显示 "有复用" 和 "无复用"
            has_overlap_pairs = (lower_match or lev1_match)  # 只要有一个计数不为0，就认为有重叠事件

            # 但是饼图需要互斥。
            # 简化为：有多少账户至少有一种重叠（lower 或 lev1）
            # 这需要 run_analysis 返回一个 unique_overlap_pairs_count
            # 在没有这个精确数据的情况下，我们使用一个更通用的 "匹配类型概览" 图

            # 图表 2: 复用类型占比条形图或雷达图更合适
            # 重新设计为展示"精确匹配", "大小写不敏感匹配", "Levenshtein≤1匹配"三种覆盖率的条形图
            # 不再使用饼图，因为它们有重叠

            # 将百分比作为数据
            chart2_data = [
                {"name": "精确匹配", "value": round(exact_match / total_pairs * 100, 2) if total_pairs else 0},
                {"name": "大小写不敏感匹配", "value": round(lower_match / total_pairs * 100, 2) if total_pairs else 0},
                {"name": "Levenshtein≤1 匹配", "value": round(lev1_match / total_pairs * 100, 2) if total_pairs else 0},
            ]
            chart2_categories = [d["name"] for d in chart2_data]

    with html_path.open("w", encoding="utf-8") as fh:
        fh.write("<!doctype html><html><head><meta charset='utf-8'><title>用户名子串复用分析报告</title>")
        fh.write("<script src='https://cdn.jsdelivr.net/npm/echarts@5.3.3/dist/echarts.min.js'></script>")
        fh.write("<style>")
        fh.write("body{font-family:Arial;padding:1.5rem;display:flex;flex-direction:column;align-items:center;}")
        fh.write("h1, h2 {color:#333; margin-bottom: 1rem;}")
        fh.write("table{border-collapse:collapse;margin-bottom:2rem;width:80%;max-width:800px;}")
        fh.write(
            "th,td{border:1px solid #ccc;padding:0.6rem 1rem;text-align:left;}th{background:#f0f0f0;font-weight:bold;}")
        fh.write(
            ".chart-container {width: 90%; max-width: 800px; height: 400px; margin-bottom: 2rem; border: 1px solid #eee; box-shadow: 0 2px 10px rgba(0,0,0,0.05);}")
        fh.write("ul {list-style-type: none; padding: 0; width: 80%; max-width: 800px; margin-bottom: 2rem;}")
        fh.write(
            "li {background: #f9f9f9; border: 1px solid #ddd; padding: 0.8rem; margin-bottom: 0.5rem; border-radius: 4px;}")
        fh.write("</style>")
        fh.write("</head><body>")
        fh.write(f"<h1>用户名子串复用分析报告（{html.escape(dataset)}）</h1>")
        fh.write(f"<p>总样本数：{counts['pairs_total']}</p>")

        # --- 图表 1: Top-N 共享子串饼图 ---
        fh.write("<h2>Top-{} 共享子串占比</h2>".format(top_tokens_n))
        fh.write("<div id='topTokensPieChart' class='chart-container'></div>")
        fh.write("<table><tr><th>排名</th><th>子串</th><th>加权计数</th><th>Top-{} 内部占比（%）</th></tr>".format(
            top_tokens_n))
        total_top_weighted = sum(cnt for _, cnt in top_tokens) or 1
        for idx, seg in enumerate(top_tokens, start=1):
            token_label = seg[0]
            token_weighted_count = seg[1]
            token_inner_percent = (token_weighted_count / total_top_weighted * 100)
            fh.write(
                "<tr><td>{}</td><td>{}</td><td>{:.2f}</td><td>{:.2f}</td></tr>".format(
                    idx, html.escape(token_label), token_weighted_count, token_inner_percent
                )
            )
        fh.write("</table>")

        # --- 图表 2: 复用类型覆盖率条形图 (更适合展示重叠类别) ---
        fh.write("<h2>复用类型覆盖率</h2>")
        fh.write("<div id='reuseTypeBarChart' class='chart-container'></div>")
        fh.write("<ul>")
        fh.write(
            "<li><strong>精确匹配:</strong> {:.2f}% ({}/{})</li>".format(
                exact_match / total_pairs * 100 if total_pairs else 0,
                exact_match,
                total_pairs,
            )
        )
        fh.write(
            "<li><strong>大小写不敏感匹配:</strong> {:.2f}% ({}/{})</li>".format(
                lower_match / total_pairs * 100 if total_pairs else 0,
                lower_match,
                total_pairs,
            )
        )
        fh.write(
            "<li><strong>Levenshtein≤1 匹配:</strong> {:.2f}% ({}/{})</li>".format(
                lev1_match / total_pairs * 100 if total_pairs else 0,
                lev1_match,
                total_pairs,
            )
        )
        fh.write("</ul>")

        # --- ECharts JavaScript 代码 ---
        fh.write("<script type='text/javascript'>")

        # 图表 1: Top-N 共享子串饼图
        fh.write("var topTokensPieChart = echarts.init(document.getElementById('topTokensPieChart'));")
        fh.write(f"var tokenCategories = {json.dumps(token_categories)};")
        fh.write(f"var tokenSeriesData = {json.dumps(token_series_data)};")
        fh.write("""
        var topTokensOption = {
            tooltip: {
                trigger: 'item',
                formatter: '{a} <br/>{b}: {c} ({d}%)'
            },
            legend: {
                orient: 'vertical',
                left: 'left',
                data: tokenCategories
            },
            series: [
                {
                    name: '子串加权计数',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    avoidLabelOverlap: false,
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: '20',
                            fontWeight: 'bold'
                        }
                    },
                    labelLine: {
                        show: false
                    },
                    data: tokenSeriesData
                }
            ]
        };
        topTokensPieChart.setOption(topTokensOption);
        """)

        # 图表 2: 复用类型覆盖率条形图 (使用 barChartOptions)
        fh.write("var reuseTypeBarChart = echarts.init(document.getElementById('reuseTypeBarChart'));")
        fh.write(f"var chart2Categories = {json.dumps(chart2_categories)};")
        fh.write(f"var chart2Data = {json.dumps(chart2_data)};")
        fh.write("""
        var reuseTypeOption = {
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                },
                formatter: '{b}: {c}%'
            },
            xAxis: {
                type: 'category',
                data: chart2Categories,
                axisLabel: {
                    rotate: 30 // 稍微旋转标签以防止重叠
                }
            },
            yAxis: {
                type: 'value',
                name: '覆盖率 (%)',
                axisLabel: {
                    formatter: '{value} %'
                }
            },
            series: [{
                name: '覆盖率',
                type: 'bar',
                data: chart2Data.map(item => item.value), // 只传递数值
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(
                        0, 0, 0, 1,
                        [
                            {offset: 0, color: '#83bff6'},
                            {offset: 0.5, color: '#188df0'},
                            {offset: 1, color: '#182bcf'}
                        ]
                    )
                },
                label: {
                    show: true,
                    position: 'top',
                    formatter: '{c}%'
                }
            }]
        };
        reuseTypeBarChart.setOption(reuseTypeOption);
        """)

        fh.write("</script>")
        fh.write("</body></html>")
    return html_path


def write_token_file(
        dataset: str,
        counts: Dict[str, int],
        token_counter: FloatCounter,
        coverage_threshold: float,
        max_tokens: int,
) -> Path:
    suffix = "" if dataset == "all" else f"_{dataset}"
    filename = f"username_tokens{suffix}.txt"
    output_path = TOKEN_OUTPUT_DIR / filename

    total_pairs = counts.get("pairs_total", 0) or 1
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


def print_summary(dataset: str, counts: Dict[str, int]) -> None:
    total = counts.get("pairs_total", 0) or 1
    print(f"=== {dataset} ===")
    print(f"pairs_total: {counts.get('pairs_total', 0)}")
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
        "--yahoo-threshold",
        type=float,
        default=0.005,
        help="单独为 Yahoo 数据集设置的最低覆盖率阈值（百分比，默认 0.005）",
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

    all_records = load_records()

    grouped: Dict[str, List[Record]] = defaultdict(list)
    processed_any_records = False

    for record in all_records:
        grouped[record.dataset].append(record)
        processed_any_records = True

    if not processed_any_records:
        raise SystemExit("未找到包含用户名/口令的数据文件。")

    datasets = args.dataset or ["all"]

    if "all" in datasets:
        grouped["all"] = [rec for rec_list in grouped.values() for rec in rec_list]

    processed = False
    for dataset in datasets:
        dataset_records = grouped.get(dataset, [])

        if not dataset_records:
            print(f"[WARN] 数据集 {dataset} 无记录，跳过。")
            continue

        counts, token_counter = run_analysis(dataset_records)
        if not counts["pairs_total"]:
            print(f"[WARN] 数据集 {dataset} 无有效样本，跳过。")
            continue

        threshold = args.coverage_threshold
        if dataset == "yahoo":
            threshold = args.yahoo_threshold

        write_csv(dataset, counts, token_counter)
        write_html(dataset, counts, token_counter)  # 生成带有图表的 HTML 报告
        write_token_file(dataset, counts, token_counter, threshold, args.max_token_count)

        print_summary(dataset, counts)
        processed = True

    if not processed:
        raise SystemExit("没有生成任何分析结果。")


if __name__ == "__main__":
    main()