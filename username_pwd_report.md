# 用户名-口令关联分析与代码实现报告

## 流程介绍

### 分析流程
**命令**
- `uv run python DataPreprocessing.py`：从 `raw_data/` 生成标准化的 `data/csdn.txt`、`data/yahoo.txt`。
- `uv run python analysis/username_overlap.py --dataset csdn --dataset yahoo --dataset all`
- `uv run python analysis/username_transform_rules.py`
- `uv run python analysis/username_pattern_corr.py`

**方法**
- `analysis/username_overlap.py` 将 CSDN（`username # password # email`）与 Yahoo（`id:email:password`）样本解析为统一结构，拆分用户名、本地邮箱段、域名和数字后缀，与口令进行大小写敏感/不敏感及 Levenshtein≤1 的 token 匹配。
- `analysis/username_transform_rules.py` 逐对计算用户名与口令的编辑关系，标注精确复用、前后缀追加、倒序、leet 替换、重复等确定性变换，并统计每类出现频次与示例。
- `analysis/username_pattern_corr.py` 记录用户名/口令长度、字符类别模式，计算 Pearson/Spearman 相关性，并生成长度散点与模式共现矩阵。

**结果 / 可视化**
- 数据规模：CSDN 6,427,769 条、Yahoo 442,837 条；全部分析脚本的 CSV/JSON 写入 `mid/analysis/...`，配套图表位于 `analysis/report_assets/...`。
- 共享子串：整体 18.21% 样本在口令中复用用户名 token（CSDN 19.23%，Yahoo 3.37%），Levenshtein≤1 覆盖率 2.37%。Top-10 token 如 `a`、`qq`、`123`、`520`（CSDN）与两位数字年份（Yahoo），可视化见 `analysis/report_assets/username_overlap/username_overlap_<dataset>_{pie,bar}.png`。

  ![用户名-口令共享子串饼图（CSDN）](analysis/report_assets/username_overlap/username_overlap_csdn_pie.png)
  ![用户名-口令共享子串条形图（CSDN）](analysis/report_assets/username_overlap/username_overlap_csdn_bar.png)
  ![用户名-口令共享子串饼图（Yahoo）](analysis/report_assets/username_overlap/username_overlap_yahoo_pie.png)
  ![用户名-口令共享子串条形图（Yahoo）](analysis/report_assets/username_overlap/username_overlap_yahoo_bar.png)
- 确定性变换：`edit_distance_1`、`exact_casefold`、`exact_case_sensitive` 分别占 5.79%/4.51%/4.29%，`suffix_digits` 1.23%，`leet_substitution` 0.74%。热力图位于 `analysis/report_assets/username_transform/username_transform_heatmap.png`。

  ![用户名-口令变换热力图](analysis/report_assets/username_transform/username_transform_heatmap.png)
- 长度耦合：CSDN Pearson 0.161 / Spearman 0.148，Yahoo 0.042 / 0.073，显示弱正相关；模式矩阵显示“字母用户名 + 8 位数字口令”最常见。散点图 `analysis/report_assets/username_pattern_corr/username_pwd_length_corr.png`，矩阵 `mid/analysis/username_pattern_corr/username_pattern_matrix.csv`。

  ![用户名-口令长度耦合散点图](analysis/report_assets/username_pattern_corr/username_pwd_length_corr.png)
- PCFG 词表：`analysis/username_overlap.py` 会依据阈值刷新 `mid/pcfg_advance/lib/username_tokens_<dataset>.txt` 与汇总版 `username_tokens.txt`，供 PCFG 引擎直接加载。

### 测试流程
**命令**
- `cd pcfg_advance && uv run python split_data.py`：清洗样本并生成 `data/data_<dataset>.pkl` 的训练/测试切分。
- `uv run python analysis/username_overlap.py --dataset csdn --dataset yahoo`：确保最新的用户名 token 词表。
- `PCFG_DATASET=csdn uv run python pcfg_advance/pcfg.advance.py`
- `ENABLE_USERNAME_TOKENS=0 PCFG_DATASET=csdn uv run python pcfg_advance/pcfg.advance.py`
- `PCFG_DATASET=yahoo uv run python pcfg_advance/pcfg.advance.py`
- `ENABLE_USERNAME_TOKENS=0 PCFG_DATASET=yahoo uv run python pcfg_advance/pcfg.advance.py`
- 每次 `pcfg.advance.py` 执行完毕后自动调用 `uv run python pcfg_advance/test.py`。

**方法**
- `pcfg_advance/pcfg.advance.py` 根据 `PCFG_DATASET` 从 `mid/pcfg_advance/lib/username_tokens_{dataset}.txt`（不存在时回退到 `pcfg_advance/lib/username_tokens.txt` 或 `USERNAME_TOKEN_FILE`）加载按概率排序的用户名 token，并与数字/字符规则组合生成 20 万条候选，输出到 `pcfg_advance/<dataset>_genpwds.txt`。
- `pcfg_advance/test.py` 从 `../data/data_<dataset>.pkl` 提取测试集，对生成列表做撞库评估，将命中条数写入 `pcfg_advance/res.txt`，命中样本追加到 `pcfg_advance/info.txt`。
- `ENABLE_USERNAME_TOKENS` 环境变量控制是否启用基于用户名的候选节点，从而完成 A/B 测试；`USERNAME_TOKEN_FILE` 可指向自定义词表以复现实验。

**结果 / 可视化**
- 200k guesses 的 A/B 测试记录于 `pcfg_advance/res.txt`：

| 数据集 | Token 状态 | 命中条数 | 测试集规模 | 命中率 |
| --- | --- | --- | --- | --- |
| csdn | 启用 | 11,940 | 50,000 | 0.23880 |
| csdn | 关闭 | 11,854 | 50,000 | 0.23708 |
| yahoo | 启用 | 10,988 | 50,000 | 0.21976 |
| yahoo | 关闭 | 11,011 | 50,000 | 0.22022 |

- 结论：CSDN 在启用用户名 token 后提升 0.17 个百分点，证明 `mid/pcfg_advance/lib/username_tokens_csdn.txt` 带来稳定收益；Yahoo 因高频 token 多为短数字，当前策略略逊于基线（-0.046 个百分点），需结合域名/地域标签或降低阈值进一步调优。

## 代码介绍

### DataPreprocessing.py
- 将 Yahoo 与 CSDN 原始路径切换为仓库相对路径（`./raw_data/plaintxt_yahoo.txt`、`./raw_data/csdn.txt`），`main()` 默认执行 `word_dataset_processing()`，统一生成 `data/csdn.txt` 与 `data/yahoo.txt`。

### analysis/username_overlap.py
- 定义 `Record` 抽象与 `load_records()` 统一解析数据集；`tokenize()`、`username_tokens()`、`password_tokens()` 提供一致的 token 化逻辑。
- `run_analysis()` 同时统计大小写敏感/不敏感交集与 Levenshtein≤1 近似，`write_csv()`、`write_figures()`、`write_token_file()` 负责输出 CSV、饼图/柱状图以及 PCFG 词表。

### analysis/username_transform_rules.py
- 复用与 `username_overlap` 一致的解析流程并实现 `levenshtein()`。
- `classify()` 标注文档中所有变换类别，`main()` 汇总 `global_counter`、`dataset_counter` 与示例，写入 `mid/analysis/username_transform/username_transform_stats.json` 并绘制热力图。

### analysis/username_pattern_corr.py
- `load_pairs()` 与 `to_pattern()` 将样本映射为长度和模式；自实现 `pearson()`、`spearman()` 计算相关系数。
- `main()` 构建 `length_data` 与 `pattern_matrix`，生成散点图 `analysis/report_assets/username_pattern_corr/username_pwd_length_corr.png` 与矩阵 CSV。

### pcfg_advance/pcfg.advance.py
- 通过 `PCFG_DATASET`、`ENABLE_USERNAME_TOKENS`、`USERNAME_TOKEN_FILE` 控制数据集和用户名 token 开关，`FILE_PATH = "./data/data_{FILE_NAME}.pkl"` 与标准化输出路径保持一致。
- `_resolve_username_token_path()` 按“构造参数 → 环境变量 → 数据集专属词表 → 默认兜底”探测词表，`load_username_tokens()` 解析 `token prob` 格式后按概率排序。
- `_generate_username_token_candidates()` 将 token 与数字/字符规则组合，返回概率乘积结果；`_get_top_rule_entries()` 暴露高频数字/字符片段供组合使用。
- 生成的 `{FILE_NAME}_genpwds.txt` 与 `pcfg_advance/test.py` 共享目录，方便自动评测。

### pcfg_advance/test.py
- `BASE_DIR` 固定为 `pcfg_advance`，`DATA_DIR` 固定为 `../data`，在任意工作目录下都能定位 `data_<file_name>.pkl` 与 `<file_name>_genpwds.txt`。
- `test(file_name)` 计算命中率并更新 `res.txt`（统计）与 `info.txt`（命中样本），形成完整的评估闭环。

## 附录：文件清单

### 新增代码 / 文档
- `analysis/username_overlap.py`
- `analysis/username_pattern_corr.py`
- `analysis/username_transform_rules.py`
- `username_pwd_report.md`

### 新增中间结果与可视化
- `mid/analysis/username_overlap/username_overlap.csv`
- `mid/analysis/username_overlap/username_overlap_csdn.csv`
- `mid/analysis/username_overlap/username_overlap_yahoo.csv`
- `analysis/report_assets/username_overlap/username_overlap_pie.png`
- `analysis/report_assets/username_overlap/username_overlap_bar.png`
- `analysis/report_assets/username_overlap/username_overlap_csdn_pie.png`
- `analysis/report_assets/username_overlap/username_overlap_csdn_bar.png`
- `analysis/report_assets/username_overlap/username_overlap_yahoo_pie.png`
- `analysis/report_assets/username_overlap/username_overlap_yahoo_bar.png`
- `mid/analysis/username_pattern_corr/username_pattern_matrix.csv`
- `analysis/report_assets/username_pattern_corr/username_pwd_length_corr.png`
- `mid/analysis/username_transform/username_transform_stats.json`
- `analysis/report_assets/username_transform/username_transform_heatmap.png`
- `mid/pcfg_advance/lib/username_tokens.txt`
- `mid/pcfg_advance/lib/username_tokens_csdn.txt`
- `mid/pcfg_advance/lib/username_tokens_yahoo.txt`

### 修改的既有代码文件
- `DataPreprocessing.py`
- `pcfg_advance/pcfg.advance.py`
- `pcfg_advance/test.py`
- `mid/pcfg_advance/info.txt`
- `mid/pcfg_advance/res.txt`
- `.gitignore`
