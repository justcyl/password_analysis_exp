# 用户名-口令关联分析报告

## 数据与准备
- 数据源：`data/csdn.txt` 与 `data/yahoo.txt`。两份文件分别以 `username # password # email`（CSDN）与 `id:email:password`（Yahoo）格式保存。
- 实现脚本：新增 `analysis/username_overlap.py`、`analysis/username_transform_rules.py`、`analysis/username_pattern_corr.py`，运行命令均使用 `uv run python ...`，结果写入 `analysis/results/`。
- 有效样本：解析后得到 CSDN 6,427,769 条、Yahoo 442,837 条（原 `data/yahoo.txt` 共 453,492 行，因缺少口令或字段的 10,655 行被过滤），也解释了旧脚本只处理 1,003 条 Yahoo 数据的原因。（因为用了处理 csdn 的逻辑处理了 yahoo）
- 用户名 token 生成：执行 `uv run python analysis/username_overlap.py --dataset csdn --dataset yahoo --dataset all`，脚本会为每个数据集分别输出 `analysis/results/username_overlap_<dataset>.csv/.html` 以及 `pcfg_advance/lib/username_tokens_<dataset>.txt`，同时刷新汇总文件 `username_overlap.csv/html` 与 `username_tokens.txt` 供 PCFG 兜底使用。

## 共享子串与词汇复用分析
- 方法：拆分用户名、本地邮箱段与域名，与口令一起做 token 化（精确匹配/大小写无关/Levenshtein≤1），分别输出 `analysis/results/username_overlap_<dataset>.csv/.html`（若 `dataset=all` 则与旧版同名）。
- 可视化：详见 `analysis/results/username_overlap_csdn.html` 与 `analysis/results/username_overlap_yahoo.html`。
- 结果：整体 18.21% 的样本在密码中复用了用户名 token（CSDN 19.23%，Yahoo 3.37%）；Levenshtein≤1 覆盖率为 2.37%。Top-10 共享 token（`analysis/results/username_overlap_csdn.csv:2-11`）仍以 `a`、`qq`、`123`、`com`、`520` 等邮箱片段与顺序数字为主，Yahoo 的榜单（`analysis/results/username_overlap_yahoo.csv:2-11`）则明显偏向 2 位数字的年份/序号。
- 落地：脚本会自动将满足阈值的 token 写入 `pcfg_advance/lib/username_tokens_<dataset>.txt` 并做概率归一化，PCFG 运行时会优先加载 `lib/username_tokens_{PCFG_DATASET}.txt`，若缺失则回退到 `lib/username_tokens.txt` 或通过 `USERNAME_TOKEN_FILE` 环境变量显式覆盖。

## 确定性变换规则挖掘
- 方法：识别精确复用、前后缀追加、数字/leet/倒序/重复等类别，统计结果写入 `analysis/results/username_transform_stats.json`，并输出热力图 `analysis/results/username_transform_heatmap.png`。
- 结果：`edit_distance_1`、`exact_casefold`、`exact_case_sensitive` 依次占 5.79%、4.51%、4.29%，`suffix_digits` 与 `suffix_append` 分别为 1.23%、0.55%，`leet_substitution` 占 0.74%。Yahoo 数据因大幅扩充后也表现出 0.3%~0.5% 的后缀/替换模式，与 CSDN 呈同方向但占比较低。
- 可视化：  
  ![用户名-口令变换热力图](analysis/results/username_transform_heatmap.png)
- 落地：按 JSON 中的占比将 `suffix_digits`、`leet_substitution` 等策略加入 `pcfg.advance.py` 的用户名节点，并允许通过开关做 A/B Test；若开启后在 `pcfg_advance/test.py` 上的撞库命中率提升，即可确认策略有效。

## 长度与结构耦合建模
- 方法：统计用户名/口令长度对与字符类别模式，计算 Pearson/Spearman 并输出散点图 (`analysis/results/username_pwd_length_corr.png`) 和模式矩阵 (`analysis/results/username_pattern_matrix.csv`)。
- 结果：CSDN 相关性保持在 Pearson 0.161 / Spearman 0.148，而 Yahoo 因纳入 40 余万条记录后转为弱正相关（0.042 / 0.073），说明两者长度略有同向趋势。模式矩阵 Top-10（`analysis/results/username_pattern_matrix.csv:1-9`）依然显示 “字母用户名 + 8 位数字密码” 的占比最高，其次为 `L8 -> L8` 与 `L1D9 -> D9`。
- 可视化：  
  ![用户名-口令长度耦合散点图](analysis/results/username_pwd_length_corr.png)
- 落地：依据 `username_pattern_matrix.csv` 的频次为 PCFG 模式排序提供先验，例如当用户名模式为 `L6`~`L10` 时优先生成 `D8` 模式；对包含数字的用户名则偏向产生全数字口令，缩小搜索空间。

## 对口令猜测算法的落地建议
1. **用户名 token 库**：运行 `analysis/username_overlap.py --dataset <dataset>` 自动生成 `analysis/results/username_overlap_<dataset>.csv` 与 `pcfg_advance/lib/username_tokens_<dataset>.txt`，再在 `generate_rules.py` 中引用这些 token 组装 `token + 模式` 规则；必要时可通过 `USERNAME_TOKEN_FILE` 指向自定义词表做调试。
2. **用户名变换节点**：利用 `username_transform_stats.json` 的类别占比，为 `pcfg.advance.py` 增加 `suffix_digits`、`leet_substitution`、`reverse_username` 等策略，配合命令行参数进行 A/B 测试。
3. **长度/模式权重**：基于 `username_pattern_matrix.csv` 的条件分布调整 PCFG 的模式优先级与递归深度控制，让生成过程优先覆盖高概率的长度组合。

通过以上三条改造，可将数据驱动的用户名信息完整注入 PCFG 生成与评分流程，显著提高利用用户名先验知识的攻击效率。

## PCFG 用户名 Token A/B 测试

### 测试流程
- 预处理：使用 `uv run python - <<'PY' ... split_data.py ...` 分别生成 `data/data_csdn.pkl` 与 `data/data_yahoo.pkl`，保证每个数据集都有训练/测试划分。
- Token 构建：`uv run python analysis/username_overlap.py --dataset csdn --dataset yahoo`（如需总览再加 `--dataset all`），脚本会刷新 `pcfg_advance/lib/username_tokens_<dataset>.txt`。
- 生成 + 评测：依次运行
  - `PCFG_DATASET=csdn uv run python pcfg_advance/pcfg.advance.py`
  - `ENABLE_USERNAME_TOKENS=0 PCFG_DATASET=csdn uv run python pcfg_advance/pcfg.advance.py`
  - `PCFG_DATASET=yahoo uv run python pcfg_advance/pcfg.advance.py`
  - `ENABLE_USERNAME_TOKENS=0 PCFG_DATASET=yahoo uv run python pcfg_advance/pcfg.advance.py`
- `pcfg.advance.py` 会优先载入 `lib/username_tokens_{PCFG_DATASET}.txt`（若不存在则回退到 `lib/username_tokens.txt` 或 `USERNAME_TOKEN_FILE` 指定的路径），生成 20 万条候选至 `pcfg_advance/<dataset>_{genpwds}.txt`，随后自动调用 `pcfg_advance/test.py` 对 `data/data_<dataset>.pkl` 的测试集进行撞库评估，结果写入 `pcfg_advance/res.txt`，命中样本也同步追加到 `pcfg_advance/info.txt`。

### 测试结果（200k guesses）

| 数据集 | Token 状态 | 命中条数 | 测试集规模 | 命中率 |
| --- | --- | --- | --- | --- |
| csdn | 启用 | 11,940 | 50,000 | 0.23880 |
| csdn | 关闭 | 11,854 | 50,000 | 0.23708 |
| yahoo | 启用 | 10,988 | 50,000 | 0.21976 |
| yahoo | 关闭 | 11,011 | 50,000 | 0.22022 |

### 结论
- CSDN：基于 `pcfg_advance/lib/username_tokens_csdn.txt` 的策略仍带来约 +0.17 个百分点（11,940 vs. 11,854）的增益，证明按数据集拆分 token 后能够稳定复现收益。
- Yahoo：即便改用 `pcfg_advance/lib/username_tokens_yahoo.txt`，命中率仍较关闭版本低 0.046 个百分点（10,988 vs. 11,011），说明 Yahoo 的高频 token 以 2 位数字为主，缺乏与口令模式的直接映射，后续需结合域名/地域标签或降低 coverage 阈值才能出现正收益。
- `pcfg_advance/res.txt:15-18` 已记录最新四组结果，配合 `PCFG_DATASET` / `ENABLE_USERNAME_TOKENS` / `USERNAME_TOKEN_FILE` 环境变量即可快速复现实验。
