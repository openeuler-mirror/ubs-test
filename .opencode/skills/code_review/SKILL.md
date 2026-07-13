---
name: ubs-code
description: 在 ubs-test 项目中创建、编辑或检视 Python 代码（libs/、testcases/、tools/）时使用。提供代码生成路由与可复制模板、分层风格规则、防御性编程防错清单，以及代码检视维度与分级。涵盖 CLI API、BaseCase、测试用例、Hook 各层。
---

# ubs-test 代码生成与检视 SKILL

本 SKILL 是 ubs-test 项目 Python 代码的**双用途辅助入口**：

- **生成**：新增/编辑代码时，按 §1 路由到对应分层，套用模板与必守规则，并避开 §4 防错清单。
- **检视**：审查现有代码时，按 §5 维度逐项排查，按 §6 分级与评级。

详细规则见同目录参考文档（§7 索引）。本文件为路由 + 精要 + 模板，AI 生成代码时应**先读本文件的对应分层模板与防错清单**，需要深入时再查参考文档。

---

## 0. 先决判断：你在做什么？

```
用户意图
  ├─ 创建/编辑 Python 代码 ──→ §1 分层路由 → §2 通用必守 → §3 模板 → §4 防错清单（别生成这些）
  └─ 检视现有代码        ──→ §5.1 风格/模板符合性 → §5.2 缺陷/风险维度 → §6 分级/评级
```

无论哪条路径，**§2 通用必守、§3 分层模板、§4 防错清单都适用**：
- 生成时：按 §2/§3 写、按 §4 避开
- 检视时：按 §5.1 核对是否符合 §2/§3 模板、按 §5.2 核对是否触发 §4 反模式

---

## 1. 生成路径：分层路由

先确定要写的代码属于哪一层，套用对应规则与模板：

| 代码类型          | 目标目录                          | 规则权威文档                          | 本文件模板  |
| --------------- | ------------------------------- | --------------------------------- | ------- |
| CLI API wrapper | `libs/modules/ubse/api/`        | `style/cli-api-style.md` + `style/common-style.md` + `reference/cli-return-types.md` + `reference/cli-user-guide.md` | §3.1    |
| BaseCase        | `libs/modules/ubse/basecase/`   | `style/basecase-style.md` + `style/common-style.md` | §3.2    |
| 测试用例           | `testcases/<pkg>/test_*.py`     | `style/common-style.md` + §3.3   | §3.3    |
| Hook            | `libs/modules/<pkg>/hook/`      | `reference/framework-structure.md` §7 | §3.4    |
| 通用工具/框架        | `libs/` 其他                      | `style/common-style.md` + `reference/pyguide.md` | §3.5    |

**判断要写哪一层？** 看用户要做什么：
- 封装一条 `ubsectl` 命令为可复用函数 → **CLI API**
- 为一组用例提供共享 setup/teardown 与业务方法 → **BaseCase**
- 验证某个被测行为（含 CaseNumber/TestStep/ExpectedResult）→ **测试用例**
- 在用例执行前后做环境准备/清理（装包、改配置、起服务）→ **Hook**
- 通用辅助函数、解析器、节点操作 → **通用工具**

---

## 2. 通用必守规则（全层适用）

### 2.1 模块结构
顺序：模块文档字符串 → 标准库导入 → `typing` 导入 → 项目内部导入 → 模块常量（全大写下划线）→ 公共函数 → 私有函数（`_` 前缀）→ `__all__`。模块顶部 `logger = logging.getLogger(__name__)`。

### 2.2 导入
标准库在前（字母序），`typing` 单独一行，项目内部在后；**禁用相对导入**，用全限定路径 `from libs.xxx import yyy`。

### 2.3 命名
- 函数/变量 `snake_case`，动词+名词（`display_cluster`、`create_fd_memory`）
- 私有 `_` 前缀；类 `PascalCase`；常量 `UPPER_SNAKE_CASE`
- 测试类 `Test*`，测试函数 `test_*`，测试文件 `test_*.py`
- **例外**：legacy API（`logStep`/`assertTrue`/`addCleanUpStack` 等 camelCase）保留原名；`libs/host/linux.py` 已豁免 `N802/N815`

### 2.4 函数签名与类型注解
```python
def func(
    node: Any,
    required: str,
    optional: Optional[str] = None,   # ✅ 禁用 str = '' / str = None
    flag: bool = False,
) -> ReturnType:                      # ✅ 返回类型必填
```
- **所有参数与返回值必须有类型注解**
- 参数顺序：`node` → 必需 → 可选 → 标志
- **禁用可变默认参数**（`def f(x=[])`），用 `Optional[...] = None` + 内部初始化

### 2.5 文档字符串（Google 风格 + 中文简短描述）
```python
def func(...) -> ReturnType:
    """通过ubsectl xxx命令xxx。

    Args:
        node: Node object with run() method
        required: 参数描述
        optional: 可选参数（optional，默认行为）

    Returns:
        详细描述；复杂返回列出字段（- 'field': 描述）；失败返回空列表/字典。

    Example:
        result = cli_api.func(node, "value")
        if result:
            print("Success")
    """
```
**必需章节**：`Args`、`Returns`、`Example`。生成器函数用 `Yields:`。

### 2.6 代码格式（由 black/isort/ruff 自动化，勿手工争论）
行宽 100；4 空格禁 tab；函数间 2 空行、逻辑块间 1 空行；f-string 与字典键用双引号；多行参数每参数一行、右括号独占一行；用括号隐式续行**禁用反斜杠**。

### 2.7 注释
**不用行内注释**（代码自解释）；仅复杂逻辑前用块注释；中文注释允许用于 legacy 保留。**禁用 `assert` 替代条件判断**（测试用例中的 `assert`/`assertTrue` 例外）。

---

## 3. 分层生成模板

### 3.1 CLI API（`libs/modules/ubse/api/`）

函数式模块，**无类**；不向调用者抛异常，失败返回空结构。新增函数前先查 `reference/cli-return-types.md` 确定命令返回类型；层特定规则见 `style/cli-api-style.md`，通用规则见 `style/common-style.md`。

**返回值类型选择**：

| 类型 | 适用命令       | 成功返回                      | 失败返回         | 解析方法                |
| -- | ---------- | ------------------------- | ------------ | ------------------- |
| A  | display/check 查询 | `List[Dict[str, str]]`    | `[]`         | `AweTableParser`     |
| B  | create/attach 创建 | `Tuple[bool, Dict[str, str]]` | `(False, {})` | `parse_mem_res_dynamic` |
| C  | delete/detach/import 操作 | `bool`                    | `False`      | `"successfully" in res` |
| D  | 特定查询       | `str` / `Optional[str]`   | `""`/`None`  | 正则提取                |

**查询函数模板（类型 A）**：
```python
def display_numa_status_info(node: Any, options: str = "numa_status") -> List[Dict[str, str]]:
    """通过ubsectl display memory命令查询NUMA状态信息。

    Args:
        node: Node object with run() method
        options: Query options type (default: 'numa_status')

    Returns:
        List of NUMA status info dictionaries. Empty list if failed.

    Example:
        numa_info = cli_api.display_numa_status_info(node)
        for numa in numa_info:
            print(f"NUMA {numa['numa']}, Used: {numa['used']}MB")
    """
    result = node.run({"command": [f"ubsectl display memory -t {options}"]})
    stdout = result.get("stdout", "")
    if not stdout:
        return []
    stdout = stdout.rstrip('\r\nroot@#>')
    try:
        parser = AweTableParser(stdout)
        return parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse NUMA status: {stdout[:200]}")
        return []
```

**操作函数模板（类型 C）**：
```python
def delete_memory(node: Any, name: str, mem_type: Optional[str] = None,
                  is_use_long_option: bool = False) -> bool:
    """通过ubsectl delete memory命令删除内存借用。

    Args:
        node: Node object with run() method
        name: Memory name to delete
        mem_type: Memory type filter (optional, e.g., 'fd', 'numa')
        is_use_long_option: Use long option format

    Returns:
        True if delete succeeded (contains 'successfully')

    Example:
        if cli_api.delete_memory(node, "test_mem"):
            print("Deleted successfully")
    """
    if is_use_long_option:
        base_cmd, type_flag = f"ubsectl delete memory --name {name}", "--type"
    else:
        base_cmd, type_flag = f"ubsectl delete memory -n {name}", "-t"
    command = f"{base_cmd} {type_flag} {mem_type}" if mem_type else base_cmd
    res = node.run({"command": [command]}).get("stdout", "").rstrip('\r\n')
    return "successfully" in res
```

**命令执行标准模式**：合并 stdout+stderr → `rstrip('\r\nroot@#>')` → 解析。短选项用 `is_use_long_option` 分支。

### 3.2 BaseCase（`libs/modules/ubse/basecase/`）

类继承 `TestCase`，**无 `__init__`**（pytest 不收集带 `__init__` 的类）；依赖通过**类外** `@pytest.fixture(autouse=True)` 注入。层特定规则见 `style/basecase-style.md`，通用规则见 `style/common-style.md`，机制详解见 `reference/framework-structure.md` §5。

```python
import pytest
from typing import Any, Dict, List
from libs.core.base import TestCase

@pytest.fixture(autouse=True)
def inject_xxx_dependencies(request: Any, nodes: List[Any], resource: Dict[str, Any],
                            custom_params: Dict[str, Any]) -> None:
    """仅对 XxxBaseCase 及其子类注入依赖。"""
    instance = request.instance
    if not isinstance(instance, XxxBaseCase):
        return
    instance.nodes = nodes
    instance.resource = resource
    instance.custom_params = custom_params
    # 从 custom_params 提取业务参数，覆盖类属性默认值
    instance.install_path = custom_params.get("install_path", XxxBaseCase.INSTALL_PATH)
    # 运行时对象、状态变量初始化...

class XxxBaseCase(TestCase):
    """XXX 测试基类。无 __init__，属性由 fixture 注入。"""
    INSTALL_PATH = "/home/ci/xxx"   # 类属性默认值

    def setup_method(self):
        self.logStep("环境检查")
        # 公共前置...

    def teardown_method(self):
        # 公共后置...
        pass
```

> **关键**：`inject_*_dependencies` 必须在 `testcases/conftest.py` 显式导入才会被 pytest 发现。跨继承层级的 `self.xxx` 属性必须在 fixture 中补齐，否则子类 `AttributeError`。

### 3.3 测试用例（`testcases/<pkg>/test_*.py`）

**禁止**使用"Migrated from legacy"等无意义注释，发现后直接删除。

```python
import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase

@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemFdCreateSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber: test_tc_mem_fd_create_sdk_001
    RunLevel: Level T
    EnvType:

    CaseName: 验证sdk接口创建fd形态的远端内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_fd_create接口创建fd内存
        S2.查看内存账本信息
        S3.删除创建的内存
        S4.查看账本确认已清空
    ExpectedResult:
        E1.内存创建成功
        E2.查到创建的内存信息
        E3.内存删除成功
        E4.账本不包含S1的内存
    """

    def setup_method(self):
        self.logStep("P1.ubse进程已启动")

    def test_tc_mem_fd_create_sdk_001(self):
        self.logStep("S1.调用接口创建fd内存")
        res = self.mem_fd_borrow(node=self.nodes[0], name="mem_fd_001")
        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

    def teardown_method(self):
        pass
```

- **禁止**"Migrated from legacy"等无意义注释，发现后直接删除
- 类文档含结构化字段：`CaseNumber/RunLevel/EnvType/CaseName/PreCondition/TestStep/ExpectedResult`（无Author字段）
- TestStep 编号**连续**（S1→S2→S3，不允许跳跃）
- ExpectedResult 编号与 TestStep 对应（E1对应S1）

**检视规则：文档与代码一致性**

| 文档字段 | 对应代码位置 | 检视要点 |
|---------|-------------|----------|
| **PreCondition** | `setup_method()` | P1/P2/... 对应 `self.logStep("P1...")` + 前置动作代码 |
| **TestStep** | `test_xxx()` | S1/S2/... 对应 `self.logStep("S1...")` + 测试动作代码 |
| **ExpectedResult** | `test_xxx()` | E1/E2/... 对应 `self.logStep("E1...")` + 断言代码 |

**常见不一致问题**：
- TestStep S4 描述"映射"但代码调用 `shm_detach`（应为"解除映射"）
- logStep 编号错误：代码写 `S1` 但实际是第二个步骤（应为 `S2`）
- logStep 接口名错误：代码调用 `shm_list` 但 logStep 写 `numa_list`
- ExpectedResult 编号跳跃：有 E2/E3 但缺 E1

### 3.4 Hook（`libs/modules/<pkg>/hook/`）

```python
from libs.core.base import TestCase

class XxxHook(TestCase):
    """无 __init__；属性在 _init_from_fixture 设置。三方法缺一不可。"""

    def _init_from_fixture(self, nodes: list, custom_params: dict) -> None:
        """fixture 注入入口：接收 SSH 节点列表与 --test-params 字典。"""
        self.nodes = nodes
        self.install_path = custom_params.get("install_path", "/home/ci/xxx")

    def beforePreTestSet(self, **kwargs):
        """前置：装包/改配置/起服务。"""
        ...

    def afterPostTestSet(self, **kwargs):
        """后置：清理。"""
        ...
```

触发方式二选一：标记驱动（`@pytest.mark.hook`，参考 `reference/framework-structure.md` §7.2）或 CLI 驱动（`--test-hook`，§7.3）。复杂 Hook 可继承 `MemHookBase`（提供 `self.logger`/`self.sleep()`），非强制。

### 3.5 通用工具（`libs/utils/`、`libs/host/` 等）

遵循 `pyguide.md`；函数式模块 + `__all__`；仅模块级 `logger` 与常量，**无全局可变状态**；`node.run` 返回链式访问每层带默认值。

---

## 4. 防错清单（生成时避开 / 检视时排查，源自真实检视案例）

生成代码时**逐条自检**不要写出以下模式；检视代码时**逐条核对**是否存在以下模式：

| # | 反模式                                  | 正确做法                                        | 后果            |
| - | ------------------------------------- | --------------------------------------------- | ------------- |
| 1 | `password = 'huawei12#$'`             | `os.environ.get("UBSE_CERT_PASSWORD", "")`    | 凭证永久留存版本库（P1） |
| 2 | `if not value: delete()` 区分"未提供"与"空值" | `if value is None: delete()`                  | 空值被误删（P1）    |
| 3 | `except: self(...)` 递归参数不变            | 带重试计数 `_retry` 或返回安全默认                         | 无限递归栈溢出（P1）  |
| 4 | `result.get("stdout").strip()`        | `result.get("stdout", "").strip()`            | AttributeError（P2） |
| 5 | `self.xxx` 跨继承层级未初始化                  | fixture 中补齐或 `getattr(self, "xxx", default)` | AttributeError（P2） |
| 6 | `stop_process(node, "ubse & disown")` | 含元字符直接 `node.run`，或 `shlex.quote()`            | `\|\|` 回退失效（P2） |
| 7 | `except: pass` 静默吞异常                  | `logger.error(...)` 记录上下文                     | 错误被掩盖（P2）    |
| 8 | `str.replace('-', '')` 粗暴清洗           | 正则精准匹配目标字段                                    | 破坏合法数据（P2）  |
| 9 | `if "success" in res: return True; return False` | `return "success" in res`             | 冗余（P3）       |
| 10 | `def func(param: str = ''):`          | `def func(param: Optional[str] = None):`       | 类型语义错误（P3）  |
| 11 | `def f(x=[]):`                         | `def f(x: Optional[List] = None):`             | 可变默认共享（P3）  |
| 12 | `def import_cert(...) -> str:`        | `-> bool`（类型 C）                              | 返回类型错标（P3）  |
| 13 | docstring Example 函数名与实际不一致            | 与实现同步                                         | 复制即 AttributeError（P3） |
| 14 | `assertTrue(api_returning_tuple())`   | 解包 `(success, info)` 后断言 `success`            | 元组恒 truthy，断言失效（P1） |
| 15 | `if res and ...:` 判命令成功，命令失败空输出       | 检查 `returnCode`/`stderr` 区分"目标不存在"与"命令失败"  | 假成功（P2）    |
| 16 | 循环外 `acc={}`，循环内条件更新                 | 每轮循环体内部重置 `acc`；未取值显式失败                    | 跨迭代数据污染（P2） |

**核心口诀**：
- 默认 `None` 的参数用 `is None` 判断；确认空值等价"无"才用 truthiness
- `node.run` 返回的链式访问**每层**带默认值；判命令成功要看 `returnCode` 而非 stdout 非空
- API 层不抛异常返回空结构；用例层用断言主动失败——**别混用**
- `Tuple`/复合返回值**先解包再断言布尔分量**，别 `assertTrue(tuple)`；循环累加变量**每轮重置**

---

## 5. 检视路径：维度（逐项排查）

审查现有代码时分两步：**先查是否符合模板/风格规则（§5.1），再查是否触发缺陷/风险模式（§5.2）**。前者对应 §2/§3 的"该写成什么样"，后者对应 §4 的"不该写成什么样"。各维度的**深度详解（触发条件/后果/修复代码）与真实案例**见 `review/review-guide.md`。

### 5.1 风格与模板符合性（对照 §2 通用必守 + §3 分层模板）

#### A. 通用符合性（所有层，对照 §2）

| # | 检查项                                  | 不符合的表现                        | 级别 |
| - | ------------------------------------ | ------------------------------ | -- |
| A1 | 模块结构顺序（§2.1）                         | 导入在常量后、`__all__` 缺失或与导出不一致、缺 `logger` | P3 |
| A2 | 导入规范（§2.2）                           | 用了相对导入、`typing` 未单独一行、顺序错乱    | P3 |
| A3 | 命名（§2.3）                             | 非 snake_case、私有函数无 `_` 前缀、测试类非 `Test*` | P3 |
| A4 | 类型注解完整性（§2.4）                        | 参数或返回值缺类型注解                    | P2 |
| A5 | 可选参数默认值（§2.4）                        | `str = ''` / `str = None` / 可变默认 `x=[]` | P2 |
| A6 | docstring 三章节（§2.5）                  | 缺 `Args`/`Returns`/`Example`   | P3 |
| A7 | docstring 准确性                        | Example 函数名/返回类型与实际不一致、`__all__` 与导出不同步 | P3 |
| A8 | 格式（§2.6）                             | 行宽超 100、tab 缩进、反斜杠续行           | P3 |

> 格式类（A1/A2/A3/A8）多由 black/isort/ruff 自动化，检视时若工具已配置可降为 P3 或提示"交给工具"。

#### B. 分层模板符合性（按代码所属层，对照 §3）

**B1. CLI API 层（`libs/modules/ubse/api/`，对照 §3.1）**

| # | 检查项                        | 不符合的表现                       | 级别 |
| - | -------------------------- | ---------------------------- | -- |
| B1a | 模块为函数式、无类                 | 定义了不必要的类                     | P3 |
| B1b | 返回值类型符合命令分类（查 `reference/cli-return-types.md`） | 查询类不返回 `List[Dict]`、操作类不返回 `bool` | P2 |
| B1c | 不向调用者抛异常，失败返回空结构          | `raise` 上抛、失败返回 `None` 但签名是 `List` | P2 |
| B1d | 命令执行标准模式                   | 未合并 stdout+stderr、未 `rstrip('\r\nroot@#>')` | P3 |
| B1e | 短选项用 `is_use_long_option` 分支 | 硬编码长/短选项、无切换能力              | P3 |

**B2. BaseCase 层（`libs/modules/ubse/basecase/`，对照 §3.2）**

| # | 检查项                          | 不符合的表现                      | 级别 |
| - | ---------------------------- | --------------------------- | -- |
| B2a | 类无 `__init__`                | 定义了 `__init__`（pytest 不收集）  | P1 |
| B2b | 依赖经类外 `@pytest.fixture(autouse=True)` 注入 | fixture 定义在类内部、依赖手动构造       | P2 |
| B2c | `inject_*` 在 `testcases/conftest.py` 导入 | 未导入 → fixture 不生效          | P2 |
| B2d | 类属性默认值 + fixture 覆盖        | 硬编码在 `__init__`、fixture 未从 custom_params 取值 | P3 |

**B3. 测试用例层（`testcases/`，对照 §3.3）**

| # | 检查项                       | 不符合的表现                      | 级别 |
| - | ------------------------- | --------------------------- | -- |
| B3a | 类文档含结构化字段                 | 缺 `CaseNumber/PreCondition/TestStep/ExpectedResult/Author` | P3 |
| B3b | `logStep` 记录步骤(Sx)与预期(Ex) | 用 `print`/裸注释代替            | P3 |
| B3c | 用 `assertTrue`/`assertEqual` 主动失败 | API 层"返回空结构"风格误用到用例层      | P2 |
| B3d | `setup/teardown_method` 调 `super()` | 未调父类钩子，公共前后置被跳过          | P2 |

**B4. Hook 层（对照 §3.4）**

| # | 检查项                       | 不符合的表现                   | 级别 |
| - | ------------------------- | ----------------------- | -- |
| B4a | 三方法齐备（`_init_from_fixture`/`beforePreTestSet`/`afterPostTestSet`） | 缺方法、属性写在 `__init__` 而非 `_init_from_fixture` | P1 |
| B4b | 触发方式与 conftest 一致         | 声明标记驱动但包 conftest 未实现收集逻辑 | P2 |

> 模板符合性问题多为 P3（风格偏差），但其中"会导致功能失效"的（B1c 抛异常、B2a 带 `__init__`、B4a 缺方法）升至 P1/P2。

### 5.2 缺陷与风险维度（对照 §4 防错清单，说明"触发条件→后果"）

> 以下为浓缩清单；各维度的触发条件、后果与修复代码示例详见 `review/review-guide.md` §2，真实案例见其 §7。

1. **凭证硬编码**：密码/密钥/token/私钥是否入源码、是否经 `echo | cmd` 传递（P1）
2. **真值 vs None**：`if not value:` 是否将空值误判为删除/失败（P1）
3. **递归与重试**：异常分支递归参数是否变化、是否带重试上限（P1）
4. **字典与属性访问**：`.get()` 是否带默认值、`self.xxx` 跨继承层级是否初始化（P2）
5. **Shell 命令组合**：封装的进程名是否含 `&|;>` 元字符、`||` 回退是否失效（P2）
6. **静默失败**：是否静默返回 0/None/[]、`except` 是否吞异常（P2）
7. **数据完整性**：粗暴 `replace` 是否破坏合法数据、切片索引是否越界（P2）
8. **死代码与跨文件一致**：未被引用的函数、重命名后旧名残留、fixture 跨文件不一致（P3）
9. **代码模式正确性**：多行布尔未简化、`Optional` 误用、可变默认参数、类型错标（P2/P3）
10. **元组/复合返回值断言**：`assertTrue(api_returning_tuple())` 恒真——`bool((False,{}))==True`，验证步骤失效（P1）
11. **命令失败空输出误判成功**：`if res and ...:` 把 `node.run` 执行失败(空 stdout)误判为目标不存在/操作成功（P2）
12. **循环状态污染**：循环外初始化的累加变量未每轮重置，跨迭代沿用旧值导致误比较（P2）

---

## 6. 检视路径：分级与评级

| 级别 | 含义          | 示例                          |
| -- | ----------- | --------------------------- |
| P0 | 严重缺陷，必然触发   | -                           |
| P1 | 阻塞，高概率触发且后果严重 | 硬编码密码、无限递归、空字符串语义错误         |
| P2 | 建议修复，特定边界触发 | 空文件误报失败、shell 组合异常、属性未初始化   |
| P3 | 轻微，低置信度或死代码 | docstring 错误、死代码、跨文件不一致     |

**风险评级**：
- 低风险：无 P1，P2/P3 为文档/死代码
- 中等风险：存在 P1，或 P2 在常见边界触发
- 高风险：多个 P1，或影响核心功能路径

**检视原则**：failure mode 导向（说明触发条件与后果）、跨文件追踪、基于代码现状、不臆断、可执行（给修复方向）。

---

## 7. 参考文档索引

```
code_review/
├── SKILL.md                 ← 入口（本文件）
├── style/                   代码风格规则
│   ├── common-style.md      通用风格详细版（含正反例）
│   ├── cli-api-style.md     CLI API 层特定规则
│   └── basecase-style.md    BaseCase 层特定规则
├── review/
│   └── review-guide.md      检视深度参考（10维度详解+10真实案例+分级）
└── reference/               参考材料（按需查）
    ├── framework-structure.md  框架架构/fixture/Hook机制/执行流程
    ├── cli-return-types.md     各 CLI 命令返回值类型与字段
    ├── cli-user-guide.md       ubsectl 命令用法/参数/输出格式
    └── pyguide.md              Google Python Style Guide（外部地基）
```

| 文档                           | 用途                          | 何时查                          |
| ---------------------------- | --------------------------- | ---------------------------- |
| `style/common-style.md`      | 通用风格详细版（含正反例）               | 写任何代码时查通用规则细节                |
| `style/cli-api-style.md`     | CLI API 层特定规则               | 写/改 `libs/modules/ubse/api/` |
| `style/basecase-style.md`    | BaseCase 层特定规则              | 写/改 `libs/modules/ubse/basecase/` |
| `review/review-guide.md`     | 检视深度参考（10维度详解+7真实案例+分级）     | 深入检视、查 failure mode 真实案例      |
| `reference/framework-structure.md` | 框架架构、fixture/Hook 机制、执行流程   | 不确定代码放哪、Hook/fixture 怎么写     |
| `reference/cli-return-types.md` | 各 CLI 命令返回值类型与字段            | 新增 CLI 函数确定返回类型              |
| `reference/cli-user-guide.md` | ubsectl 命令用法、参数、输出格式        | 不确定命令的参数与输出                  |
| `reference/pyguide.md`       | Google Python Style Guide 地基 | 判断通用 Python 风格争议             |

---

## 8. 工作流（AI 执行步骤）

### 8.1 生成代码工作流

1. **识别意图**：生成 or 检视？（§0）
2. **定位分层**：用户要写 CLI API / BaseCase / 用例 / Hook / 通用？（§1）
3. **套模板**：复制 §3 对应模板，填充业务逻辑。
4. **守通用规则**：对照 §2 逐条（类型注解、docstring 三章节、命名、格式）。
5. **过防错清单**：对照 §4 13 条反模式自检。
6. **查参考文档**：需要命令参数/返回字段/Hook 机制细节时查 §7 对应文档。
7. **自检输出**：确认 `__all__` 与导出一致、docstring Example 函数名与实现一致、无硬编码凭证。

### 8.2 检视代码工作流

1. **识别意图**：生成 or 检视？（§0）
2. **定位分层**：被检代码属于 CLI API / BaseCase / 用例 / Hook / 通用？（§1）——决定套用哪套模板核对表。
3. **查模板符合性（§5.1）**：
   - 先过通用符合性 A1–A8（§2）
   - 再过对应分层 B1/B2/B3/B4（§3），记录不符合项与级别
4. **查缺陷/风险（§5.2）**：对照 §4 防错清单 13 条 + §5.2 维度，记录触发条件与后果。
5. **分级（§6）**：每条问题按 P0–P3 定级。
6. **汇总评级**：统计各级数量，给出低/中/高风险。
7. **可执行输出**：每条问题给出 `file:line`、问题代码、触发条件、后果、修复方向（必要时给修复代码）；P1 优先。

---

## 更新日志

| 日期         | 版本   | 说明                                          |
| ---------- | ---- | ------------------------------------------- |
| 2026-07-06 | v1.0 | 合并 code_review 目录下各文档为双用途 SKILL（生成+检视），提供路由、模板、防错清单 |
| 2026-07-06 | v1.1 | 检视路径增加 §5.1 风格/模板符合性核对（通用 A1–A8 + 分层 B1–B4），§4 改为生成/检视共用，§8 增加检视工作流 |
| 2026-07-06 | v1.2 | 目录分层重组：style/（common + cli-api + basecase）、review/（review-guide）、reference/（4 份）；删除冗余 code-style.md，抽公共件去重，更新全部交叉引用 |
| 2026-07-06 | v1.3 | 基于 PR #17 atomgit-bot 意见补充：§4 防错清单 +14/15/16、§5.2 维度 +10/11/12（元组断言恒真、命令失败空输出误判成功、循环状态污染） |
