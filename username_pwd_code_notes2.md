# 用户名-口令与 PCFG 代码级改动说明2

---

## 1.split_data.py

**位置：** `pcfg_advance/split_data.py`
**主要职责：**

- 修复原始脚本中存在的多处严重 Bug，使其能够正确生成 PCFG A/B 测试所需的 data/data_csdn.pkl 和 data/data_yahoo.pkl 文件。

- 关键代码点（重写）：

- 编码与路径修复（init_data）

- 修复 UnicodeDecodeError： init_data 函数中，open() 默认使用 UTF-8，导致读取 GBK 编码的 csdn.txt 失败。

- 改动： 增加了 try-except 逻辑，优先尝试 gbk 编码，失败则回退到 latin-1，并设置 errors='ignore' 确保数据读取的鲁棒性。
- 改动： 重写 main 函数，使其不再依赖全局变量 FILE_NAME，而是循环遍历 ['csdn', 'yahoo'] 列表，在一次运行中同时生成两个数据集的 .pkl 文件，与 PCFG A/B 测试流程匹配。
- 修复 NameError: 'data_path' is not defined： init_data 中直接使用了未定义的 data_path 变量。

- 改动： 将 init_data 修改为 init_data(dataset_name: str)，使其接收数据集名称，并使用 pathlib 在函数内部动态构建 data_path 路径。


**含义：** 保证项目中的 `data/csdn.txt` 和 `data/yahoo.txt` 始终来自统一的预处理逻辑，为后续所有用户名-口令分析脚本提供一致的输入格式。

---

## 2. 功能与流程优化 username_overlap.py

**位置：** `analysis/username_overlap.py`

**主要职责：**

- 修复原始脚本的数据处理瓶颈。

- 实施原始 README 中针对 Yahoo 数据集提出的算法改进建议。

- 增加全新的 ECharts 可视化图表，使报告更专业。

- 
**关键代码点：**
### 2.1 稳定性修复（load_records）
- 修复 UnicodeDecodeError：load_records 原实现默认使用 UTF-8 编码，无法读取 GBK 编码数据。
  改动：增加 try-except 逻辑，按 ['utf-8', 'gbk', 'latin-1'] 顺序尝试打开文件，同时设置 errors='ignore' 确保鲁棒性。
- 修复 MemoryError：原实现试图将 687 万条记录一次性读入内存列表，导致内存溢出。
  改动：将 load_records 函数从返回 List[Record] 重构为生成器（Generator），通过 yield rec 逐条返回记录；main 函数相应修改为迭代该生成器，极大降低内存峰值。

---

### 2.2 算法增强（FloatCounter, run_analysis）
- 背景：原始报告指出 Yahoo 数据集命中率低，建议“降低 coverage 阈值”并探索更深层关系。
- 改动（1）- FloatCounter：新增 FloatCounter 类（继承自 defaultdict(float)），支持加权计数功能。
- 改动（2）- run_analysis：
  1. 将 token_counter 切换为 FloatCounter。
  2. 大小写不敏感匹配（lower_match）的 Token 权重设定为 1.0。
  3. 核心改进：不满足 lower_match 时，Levenshtein ≤ 1 匹配的用户名 Token 以 0.5 的权重计入 token_counter。
- 改动（3）- parse_args：新增 --yahoo-threshold 参数（默认值 0.005），允许 Yahoo 数据集使用更低的覆盖率阈值，捕获更多低频但可能相关的 Token。

---

### 2.3 可视化增强（write_html）
- 背景：原始 README 仅包含静态图片，分析报告缺乏生动性和交互性。
- 改动（1）- ECharts 注入：完全重构 write_html 函数，在生成的 HTML 文件 <head> 中引入 ECharts.js 的 CDN 资源。
- 改动（2）- 数据传递：使用 json.dumps() 将 Python 字典和列表（token_series_data、chart2_data）转换为 JavaScript 变量，实现数据互通。
- 改动（3）- 图表渲染：注入 <script> 代码块，页面加载时自动初始化 ECharts 实例，渲染两个动态图表：
  1. topTokensPieChart：Top-10 共享子串加权计数环形图。
  2. reuseTypeBarChart：复用类型覆盖率条形图，展示精确匹配、大小写不敏感、Levenshtein≤1 三种重叠场景的覆盖率百分比。

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

## 附录：与用户名-口令/PCFG 相关的修改文件一览

**修改文件（对原有 PCFG 流水线的改动）**
- `username_overlap.py`：调整修正、增强部分代码
- `pcfg_advance/split_data.py`：调整修正、增强部分代码

