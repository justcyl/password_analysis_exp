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
