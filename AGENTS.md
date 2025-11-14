# Repository Guidelines

## 项目结构与模块组织
原始口令数据保存在未追踪的 `raw_data/` 中，`DataPreprocessing.py` 会输出清洗后的语料至 `data/`。分析脚本集中在 `analysis/`，`analysis_task_*.py` 负责元素、长度、模式及 PCFG 前置处理，公共词典位于 `analysis/lib/`，图表与中间结果写入 `analysis/results/`。口令生成与评测位于 `pcfg_advance/`，流水线包含 `split_data.py`、`generate_rules.py`、`pcfg.advance.py`、`test.py`，并在 `pcfg_advance/csdn` 与 `pcfg_advance/yahoo` 下缓存各自数据集。

## 构建、测试与开发命令
- `uv run python DataPreprocessing.py`：从原始库提取并生成 `data/*.txt`。
- `uv run python analysis/analysis_task_2.py`：重算组成、长度与模式统计供后续使用。
- `uv run python analysis/task_3_pictures.py`：刷新 `analysis/results/` 中的 HTML 可视化。
- `cd pcfg_advance && uv run python split_data.py`：清洗原始数据并生成训练/测试切分。
- `cd pcfg_advance && uv run python generate_rules.py && uv run python pcfg.advance.py && uv run python test.py`：按顺序生成 PCFG 规则、产出口令字典并对测试集评估命中率。

## 代码风格与命名规范
统一使用 Python 3、四空格缩进与 `snake_case` 变量命名，数据集常量保持小写（如 `csdn`、`yahoo`）。配置项（`FILE_NAME`、`limit`、语料路径等）集中在脚本顶部，新增参数需写注释或文档。公共函数应包含 docstring，辅助模块（如 `pcfg_advance/utils.py`）尽量补全类型注解，输出文件沿用既有命名模式（`*_genpwds.txt`、`*_rules.pkl`）。

## 测试指南
测试以脚本回放为主：修改任一分析或规则生成逻辑后，重跑对应 `analysis_task_*` 或 PCFG 阶段，检查更新后的产物。调整规则算法后务必对两个数据集执行 `uv run python pcfg_advance/test.py`，并在 PR 中记录命中率变化。若需复现极端场景，可在 `data/` 下创建最小样本（如 `data/sample_csdn.txt`），确保整条流水线无异常终止。

## 提交与拉取请求规范
项目历史偏好短句式命令体（例：`Update readme`），提交信息需言简意赅，必要时在正文说明动机与影响的数据集。PR 应概述修改范围、关联 issue 或实验记录，注明未入库的敏感原始文件，并附上关键命令、指标或新生成 HTML 的截图/链接，方便复核。

## 安全与配置提示
勿将敏感原始数据提交到仓库，`raw_data/` 仅在本地保存，生成图表前请脱敏。体积较大的口令字典仍保存在 `pcfg_advance/*_genpwds.txt`，若文件需外部存储，应在文档中标明并避免向仓库写入敏感内容。

## 用户名-口令关联分析计划
本节挑选三种对后续口令猜测算法最具利用价值的分析策略，均以现有 Python 工具链与 `analysis/results/` 目录为落地目标。

### 1. 共享子串与词汇复用分析
- **原理**：大量用户会直接在密码中复用邮箱名、昵称或数字后缀，若能量化子串复用率，即可在 PCFG 中注入高概率的用户名 token，让生成策略贴近真实分布。
- **分析任务**：编写 `analysis/username_overlap.py`，拆分用户名（邮箱本地部分、域名、数字后缀）并复用 `analysis_task_3.py` 的拼音/单词分词逻辑，对密码执行相同处理，统计 Exact/Lowercase/Levenshtein≤1 的共享 token 及其频次，输出 Top-N 表与占比。
- **有效性验证**：在 `analysis/results/username_overlap.csv` 中记录总对数、复用对数与占比；若某 token 占比显著（如 >5%），说明其对猜测策略有价值。可在小规模数据集上将这些 token 注入 PCFG 词库后重跑 `pcfg_advance/test.py`，比较命中率的提升以验证有效性。
- **产物**：`analysis/results/username_overlap.csv`（详细计数）、`analysis/results/username_overlap_pie.html`（Top-N 共享词可视化）。
- **用途**：将高频用户名子串写入新的 PCFG 词库 `pcfg_advance/lib/username_tokens.txt`，并在 `generate_rules.py` 中引入 “用户名子串 + 模式规则” 的候选，优先级按复用率衰减。

### 2. 确定性变换规则挖掘
- **原理**：即使密码不是用户名原文，用户仍会做简单变换（追加年份、倒序、leet 化等）；识别这些规则可为攻击算法提供定制化转移。
- **分析任务**：实现 `analysis/username_transform_rules.py`，计算用户名与密码的编辑距离，并结合模式匹配标注变换类别（前/后缀追加、倒序、字符替换、重复次数等），统计每类的出现频次与示例。
- **有效性验证**：输出 `analysis/results/username_transform_stats.json`，其中包含样本总量与每类占比。若某类占比超过阈值（如 3%），可在 PCFG 中实现对应策略后对比 `pcfg_advance/test.py` 的命中率，或建立命令行开关以 A/B 测试有无该策略时的猜测成功数。
- **产物**：`analysis/results/username_transform_stats.json`（各变换类型出现次数与示例）、`analysis/results/username_transform_heatmap.png`（类别 vs. 频率热力图）。
- **用途**：在 `pcfg_advance/pcfg.advance.py` 中新增基于用户名的策略节点，例如 `username_token + 常见后缀`、`rev(username_token)`、`leet(username_token)`，并按统计概率调整递归限制 `self.limit`。

### 3. 长度与结构耦合建模
- **原理**：用户名长度、字符类别与密码往往存在耦合（同长、加一位数字等）；量化这种关联可帮助 PCFG 在生成阶段优先考虑更可能的长度/模式组合，减少盲目枚举。
- **分析任务**：创建 `analysis/username_pattern_corr.py`，统计用户名与密码的长度对、字符类别模式（数字/字母/特殊），计算 Pearson/Spearman 相关系数及条件分布 `P(len_pwd | len_user)`，并按域名或业务标签分组输出散点与交叉矩阵。
- **有效性验证**：若散点图显示强线性趋势或相关系数显著（|r|>0.3），则说明长度耦合具有利用价值；可将对应分布嵌入 `generate_rules.py` 中的模式排序逻辑，再通过 `pcfg_advance/test.py` 对比启用/禁用耦合权重时的猜测成功数，确认收益。
- **产物**：`analysis/results/username_pwd_length_corr.png`（长度散点）、`analysis/results/username_pattern_matrix.csv`（模式共现表）。
- **用途**：依据相关性为 PCFG 模式排序提供先验，例如若大部分 `len_user=8` 的密码集中在 `len_pwd∈[8,10]` 且模式偏 `LxDx`，则在 `generate_rules.py` 中对相应模式提升权重或缩小枚举范围，降低搜索空间并提高命中率。
