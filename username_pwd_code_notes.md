# 用户名-口令与 PCFG 代码级改动说明

---

## 1. DataPreprocessing.py

**位置：** `DataPreprocessing.py`

- 将 Yahoo 与 CSDN 原始路径改为仓库相对路径，方便在任意环境运行，不再依赖本地绝对路径：
  - Yahoo：由 `./raw_data/plaintxt_yahoo/plaintxt_yahoo.txt` 调整为 `./raw_data/plaintxt_yahoo.txt`。
  - CSDN：由本地绝对路径 `D:\\MyStudy\\UCAS\\Web_Security\\raw_data\\plaintxt_csdn\\www.csdn.net_utf-8.txt` 调整为 `./raw_data/csdn.txt`。
- `main()` 函数中切换默认执行函数：
  - 之前默认只跑 `pinyin_corpus_processing()`；
  - 现在改为默认执行 `word_dataset_processing()`，并注释掉 `pinyin_corpus_processing()`。

**含义：** 保证项目中的 `data/csdn.txt` 和 `data/yahoo.txt` 始终来自统一的预处理逻辑，为后续所有用户名-口令分析脚本提供一致的输入格式。

---

## 2. 用户名-口令共享子串分析：analysis/username_overlap.py

**位置：** `analysis/username_overlap.py`

**主要职责：**
- 从 `data/csdn.txt` 和 `data/yahoo.txt` 读取用户名、口令、邮箱，统一解析成 `Record(dataset, username, password, email)`。
- 对用户名与口令进行 token 化，统计共享 token（精确匹配 / 大小写不敏感 / 编辑距离≤1）的覆盖情况和 Top token。
- 将高频用户名 token 输出为 PCFG 可直接使用的概率词表文件 `pcfg_advance/lib/username_tokens_<dataset>.txt`。

**关键代码点：**
- `analysis/username_overlap.py:22-27`：定义 `ROOT`、`DATA_DIR`、`RESULTS_DIR`、`TOKEN_OUTPUT_DIR`，统一了脚本的输入输出路径，使脚本在项目根目录外执行时也能正确定位文件。
- `analysis/username_overlap.py:32-37`：`Record` 数据类，封装 `dataset` / `username` / `password` / `email`，便于后续函数统一处理。
- `analysis/username_overlap.py:40-67`：`parse_record(raw, dataset)` 分别处理 CSDN（`#` 分隔）和 Yahoo（`:` 分隔）两种格式，是所有后续分析脚本的解析模板。
- `analysis/username_overlap.py:70-84`：`load_records()` 遍历 `data/csdn.txt`、`data/yahoo.txt`，将所有成功解析的样本收集到列表中，为整个用户名-口令分析提供“统一样本池”。
- `analysis/username_overlap.py:87-121`：
  - `tokenize(text)`：对任意字符串做基础 token 化（原字符串、按非字母/数字拆分的片段、正则匹配的字母/数字混合片段）。
  - `username_tokens(username, email)`：对用户名、邮箱本地部分、域名及其拆分形式执行 `tokenize`，尽可能捕获用户会在密码中复用的片段（如 `qq`、`520`、`2010` 等）。
  - `password_tokens(password)`：对密码执行同样的 token 化，保证比较一致性。
- `analysis/username_overlap.py:124-144`：`levenshtein(a, b)` 实现编辑距离计算，用于识别微小拼写差异导致的近似复用。
- `analysis/username_overlap.py:147-182`：`run_analysis(records)`：
  - 对每条记录生成 `u_tokens`、`p_tokens`，分别计算：
    - `exact`：大小写敏感的精确交集；
    - `lower`：大小写不敏感的精确交集；
    - `lev_match`：在无 `lower` 命中的情况下，寻找编辑距离≤1 的近似 token 对。
  - 用 `counts` 统计样本总数及三种复用形式的命中次数；
  - 用 `token_counter` 聚合所有共享 token，为后续生成频率表和 PCFG 词表提供依据。
- `analysis/username_overlap.py:185-195`：`write_csv(dataset, counts, token_counter)` 输出 `analysis/results/username_overlap_<dataset>.csv`，记录 token 频数和覆盖率。
- `analysis/username_overlap.py:198-244`：`write_html(dataset, ...)` 输出 HTML 报告 `analysis/results/username_overlap_<dataset>.html`，展示 Top-10 共享 token 及其覆盖情况。
- `analysis/username_overlap.py:247-275`：`write_token_file(dataset, ...)` 核心：
  - 根据覆盖率阈值和最大 token 数选出高频用户名 token；
  - 按相对频率归一化为概率；
  - 写入 `pcfg_advance/lib/username_tokens_<dataset>.txt`（例如 `username_tokens_csdn.txt`、`username_tokens_yahoo.txt`）。

**新增文件：**
- `analysis/results/username_overlap_csdn.csv` / `.html`
- `analysis/results/username_overlap_yahoo.csv` / `.html`
- `analysis/results/username_overlap.csv` / `.html`（全部样本汇总）
- `pcfg_advance/lib/username_tokens_csdn.txt`
- `pcfg_advance/lib/username_tokens_yahoo.txt`
- `pcfg_advance/lib/username_tokens.txt`（汇总或兜底版）

这些文件是 PCFG 利用“用户名中常见片段”的直接数据来源。

---

## 3. 用户名变换规则分析：analysis/username_transform_rules.py

**位置：** `analysis/username_transform_rules.py`

**主要职责：**
- 基于用户名与口令的字符串关系，识别各类“确定性变换”模式，例如：
  - 追加数字/后缀；
  - 前缀追加；
  - leet 替换；
  - 倒序；
  - 重复用户名；
  - 编辑距离较小的变体等。
- 输出每类变换的出现次数与示例，以及数据集维度的热力图，为 PCFG 中是否引入对应策略提供依据。

**关键代码点：**
- `analysis/username_transform_rules.py:23-45`：`parse_line(raw, dataset)` 与前面的解析逻辑保持一致，确保“用户名/口令”的含义统一。
- `analysis/username_transform_rules.py:48-67`：`load_pairs()` 返回 `(dataset, username, password)` 三元组列表。
- `analysis/username_transform_rules.py:70-92`：`levenshtein(a, b)` 作为编辑距离辅助函数。
- `analysis/username_transform_rules.py:95-145`：`classify(username, password)` 是核心：
  - 根据字符串关系打上多种类别标签，如：`suffix_digits`、`suffix_append`、`prefix_digits`、`prefix_append`、`reverse_username`、`leet_substitution`、`repeated_username`、`wrap_username`、`edit_distance_1/2` 等；
  - 若无任何明显关系，则标记为 `no_relation`。
- `analysis/username_transform_rules.py:148-171`：`ensure_category_order(categories)` 固定输出顺序，方便在 JSON 和热力图中按相同顺序展示各类变换。
- `analysis/username_transform_rules.py:174-235`：`main()` 中：
  - 对每个样本调用 `classify`，统计：
    - `global_counter`：全局类别计数；
    - `dataset_counter`：分数据集的类别计数；
    - `examples`：为每个类别收集最多 5 条典型示例。
- `analysis/username_transform_rules.py:237-258`：将上述统计写入 `analysis/results/username_transform_stats.json`，包含：
  - `category_counts`：每类变换的总体出现次数；
  - `dataset_breakdown`：各类变换在 CSDN/Yahoo 中的分布；
  - `examples`：示例用户名/口令对。
- `analysis/username_transform_rules.py:260-304`：构建热力图矩阵并写入 `analysis/results/username_transform_heatmap.png`，便于直观观察哪类变换具有利用价值。

**新增文件：**
- `analysis/results/username_transform_stats.json`
- `analysis/results/username_transform_heatmap.png`

这些结果文件为在 PCFG 中增加如“用户名后缀数字”、“leet 化用户名”等策略提供量化依据。

---

## 4. 长度与结构耦合分析：analysis/username_pattern_corr.py

**位置：** `analysis/username_pattern_corr.py`

**主要职责：**
- 分析用户名长度与口令长度之间的相关性；
- 构建用户名模式与口令模式（如 `L8`、`D8`、`L1D9` 等）的共现矩阵，为 PCFG 中模式排序提供先验知识。

**关键代码点：**
- `analysis/username_pattern_corr.py:25-44`：`parse_line(raw, dataset)` 与前述解析逻辑保持一致。
- `analysis/username_pattern_corr.py:49-62`：`load_pairs()` 返回 `(dataset, username, password)` 列表。
- `analysis/username_pattern_corr.py:65-92`：`to_pattern(text)` 将字符串压缩为模式串：
  - 字母段记为 `Lk`，数字段记为 `Dk`，其它字符记为 `Sk`，如密码 `abc123!!` 会被编码为 `L3D3S2`。
- `analysis/username_pattern_corr.py:95-155`：`pearson(xs, ys)` 与 `spearman(xs, ys)` 分别计算长度对的线性相关性和等级相关性。
- `analysis/username_pattern_corr.py:158-214`：`main()` 中：
  - 构建 `length_data`（用户名长度、口令长度对）与 `pattern_matrix`（用户名模式、口令模式计数）；
  - 对 CSDN 与 Yahoo 分别计算 Pearson/Spearman；
  - 绘制散点图 `analysis/results/username_pwd_length_corr.png`，并在图中标注各数据集的相关系数；
  - 写出模式共现表 `analysis/results/username_pattern_matrix.csv`，按频数降序排列。

**新增文件：**
- `analysis/results/username_pwd_length_corr.png`
- `analysis/results/username_pattern_matrix.csv`

这些结果文件为 PCFG 中“不同用户名长度/模式对应的密码长度/模式优先级”提供了定量依据。

---

## 5. PCFG 引入用户名 token：pcfg_advance/pcfg.advance.py

**位置：** `pcfg_advance/pcfg.advance.py`

**主要职责改动：**
- 引入以数据集为单位的用户名 token 词表；
- 通过环境变量控制是否启用用户名 token、使用哪个数据集或自定义词表；
- 在原有 PCFG 模式生成结果基础上，追加由用户名 token 与数字/字符规则组合生成的新候选。

**关键代码点：**

1. **数据集与环境变量控制**
   - `pcfg_advance/pcfg.advance.py:6-13`：
     - 从 `generate_rules` 导入默认 `FILE_NAME`（数据集名）；
     - 允许通过环境变量 `PCFG_DATASET` 覆盖，实现 `csdn` / `yahoo` 等数据集的切换；
     - 定义 `FILE_PATH = "./data/data_{FILE_NAME}.pkl"`，作为后续数据文件路径基准。

2. **构造函数中的用户名 token 开关与加载**
   - `pcfg_advance/pcfg.advance.py:26-57`：
     - 将 `data_dir` 统一为以 `pcfg_advance` 为基准的绝对路径；
     - 从环境变量 `ENABLE_USERNAME_TOKENS` 读取是否启用用户名 token，默认开启，设置为 `0/false/off/no` 则关闭，用于 A/B 测试；
     - 通过 `_resolve_username_token_path`（见第 4 点）计算用户名 token 文件路径；
     - 若启用用户名 token，则调用 `load_username_tokens`（见第 3 点）加载 token 及其概率，排序存入 `self.username_tokens`；
     - 设定多个限制参数：`username_token_limit`（最多使用多少个 token）、`username_numeric_limit`、`username_char_limit` 等，用于控制组合规模。

3. **用户名 token 文件解析**
   - `pcfg_advance/pcfg.advance.py:90-108`：`load_username_tokens(self, rel_path)`：
     - 支持相对路径（如 `lib/username_tokens_csdn.txt`）和绝对路径；
     - 按行解析 `token prob` 格式，忽略不符合格式的行，对概率字段做 `float` 转换；
     - 按概率从大到小排序，便于后续根据 `username_token_limit` 截断使用。

4. **用户名 token 文件路径选择逻辑**
   - `pcfg_advance/pcfg.advance.py:183-193`：`_resolve_username_token_path(self, override_path)`：
     - 优先级：
       1. 构造函数参数 `username_token_filename`；
       2. 环境变量 `USERNAME_TOKEN_FILE`；
       3. 数据集专用文件 `lib/username_tokens_{FILE_NAME}.txt`（如 `username_tokens_csdn.txt`）；
       4. 默认兜底文件 `lib/username_tokens.txt`。
     - 该设计使得 PCFG 在多数据集、多实验场景下都能灵活选择用户名 token 词表。

5. **用户名 token 候选生成逻辑**
   - `pcfg_advance/pcfg.advance.py:110-132`：在原有模式生成循环完成后：
     - 如果 `self.enable_username_tokens` 为真，则调用 `_generate_username_token_candidates` 生成基于用户名 token 的候选，并与原有候选合并；
     - 对最终候选集合按概率排序后返回。
   - `pcfg_advance/pcfg.advance.py:157-174`：`_generate_username_token_candidates(self)`：
     - 如无 `self.username_tokens`，直接返回空列表；
     - 截取前 `self.username_token_limit` 个 token；
     - 使用 `_get_top_rule_entries(self.rule_number, self.username_numeric_limit)` 和 `_get_top_rule_entries(self.rule_char, self.username_char_limit)` 选取高概率数字/字符规则；
     - 对每个用户名 token：
       - 保留 token 本身；
       - 与数字规则组合：`token + number`、`number + token`；
       - 与字符规则组合：`token + word`；
       - 组合概率统一采用 `token_prob * rule_prob`；
     - 返回所有组合得到的候选列表。
   - `pcfg_advance/pcfg.advance.py:176-181`：`_get_top_rule_entries(self, rule_dict, limit)` 展平规则字典中的所有 `(内容, 概率)`，按概率排序、截断后返回，是用户名 token 组合时的数字/字符“备件来源”。

6. **输出路径标准化**
   - `pcfg_advance/pcfg.advance.py:195-201`：
     - 使用 `pcfg.base_dir` 作为输出路径前缀，将生成的 `{FILE_NAME}_genpwds.txt` 文件固定写在 `pcfg_advance` 目录内；
     - 这样与测试脚本 `pcfg_advance/test.py` 的读取路径保持一致，避免工作目录不同导致找不到文件。

---

## 6. PCFG 测试脚本路径调整：pcfg_advance/test.py

**位置：** `pcfg_advance/test.py`

**主要职责改动：**
- 将数据与输出路径显式绑到 `pcfg_advance` 与上级 `data` 目录，增强脚本的可移植性；
- 与 `pcfg.advance.py` 的输出文件位置保持一致，方便进行 A/B 测试和结果对比。

**关键代码点：**
- `pcfg_advance/test.py:6-9`：定义：
  - `BASE_DIR`：`pcfg_advance` 目录的绝对路径；
  - `DATA_DIR`：`../data` 的绝对路径，用于加载 `data_{file_name}.pkl`。
- `pcfg_advance/test.py:12-19`：`test(file_name)` 中：
  - 通过 `DATA_DIR` 加载测试集：`data_path = os.path.join(DATA_DIR, f'data_{file_name}.pkl')`；
  - 通过 `BASE_DIR` 加载生成的口令：`guesses_path = os.path.join(BASE_DIR, f'{file_name}_genpwds.txt')`；
  - 对生成的口令列表和测试集进行匹配，计算命中率。
- `pcfg_advance/test.py:34-39`：将结果写回 `pcfg_advance` 目录：
  - `res.txt`：记录每次测试的准确率，便于统计比较；
  - `info.txt`：记录命中的口令样本，便于后续人工分析。

---

## 7. 小结：我对 PCFG 的整体影响

- 在 **analysis/** 目录下新增三个分析脚本和一批结果文件，从“共享子串”、“变换规则”、“长度与结构耦合”三个维度量化用户名-口令关系，为 PCFG 设计提供了数据基础。
- 在 **pcfg_advance/lib/** 中新增用户名 token 词表文件，把上述分析中抽取出的高频用户名片段转化为 PCFG 可消费的概率词表。
- 在 **pcfg_advance/pcfg.advance.py** 中：
  - 引入了数据集与环境变量控制机制（`PCFG_DATASET`、`ENABLE_USERNAME_TOKENS`、`USERNAME_TOKEN_FILE`）；
  - 增加了用户名 token 加载与组合逻辑，使 PCFG 可以在原有规则基础上，生成带有用户名片段的候选密码；
  - 标准化了生成结果的输出路径，与测试脚本对齐。
- 在 **pcfg_advance/test.py** 中调整了数据与结果的路径，使得整个流水线（生成 + 测试）可以在不同工作目录下稳定运行，便于对比“启用与关闭用户名 token”方案的效果。

这些改动总体上把“用户名-口令统计分析”与原始 PCFG 生成流程打通，使得 PCFG 不再只依赖密码本身的统计模式，还能够在一定程度上利用用户名信息来提升密码猜测的效率（尤其是在 CSDN 这类用户名与口令关系较强的数据集上）。


---

## 附录：与用户名-口令/PCFG 相关的新增与修改文件一览

**新增文件（分析脚本、结果与说明）**
- `analysis/username_overlap.py`
- `analysis/username_pattern_corr.py`
- `analysis/username_transform_rules.py`
- `analysis/results/username_overlap.csv`
- `analysis/results/username_overlap.html`
- `analysis/results/username_overlap_csdn.csv`
- `analysis/results/username_overlap_csdn.html`
- `analysis/results/username_overlap_pie.html`
- `analysis/results/username_overlap_yahoo.csv`
- `analysis/results/username_overlap_yahoo.html`
- `analysis/results/username_pattern_matrix.csv`
- `analysis/results/username_pwd_length_corr.png`
- `analysis/results/username_transform_heatmap.png`
- `analysis/results/username_transform_stats.json`
- `pcfg_advance/lib/username_tokens.txt`
- `pcfg_advance/lib/username_tokens_csdn.txt`
- `pcfg_advance/lib/username_tokens_yahoo.txt`
- `username_pwd_report.md`
- `username_pwd_code_notes.md`

**修改文件（对原有 PCFG 流水线的改动）**
- `DataPreprocessing.py`：调整原始数据路径与默认执行函数，为用户名-口令分析提供统一输入。
- `pcfg_advance/pcfg.advance.py`：引入用户名 token 加载与组合逻辑，增加环境变量控制和输出路径标准化。
- `pcfg_advance/test.py`：标准化数据与结果路径，支持在不同工作目录下稳定评测 PCFG。
- `pcfg_advance/info.txt`、`pcfg_advance/res.txt`：测试运行过程中持续追加的结果记录文件。
- `.gitignore`：根据需要更新忽略规则（与功能逻辑关系较小）。

