---
name: review-guide
description: ubs-test 代码检视深度参考。定义 10 个检视维度的触发条件/后果/修复示例、问题分级、检视流程与风险评级，含 7 个真实案例。浓缩检查表见 SKILL.md §5。
---

# ubs-test 代码检视规范

对 ubs-test 项目全量或指定的 Python 代码进行检视，识别潜在缺陷与风险。本规范基于 atomgit-bot 在 PR #14/#15/#16 中的检视意见提炼而成，聚焦检视维度本身，不规定意见的输出格式。

> **与 SKILL 的关系**：`../SKILL.md` §5 提供浓缩版检查表（§5.1 风格/模板符合性 + §5.2 缺陷/风险维度一句话清单），本文件为各维度的**深度详解**（触发条件、后果、修复代码示例）与真实案例。日常检视先查 SKILL §5，需深入时查本文件对应小节。

## 1. 适用场景

- **全量检视**：对 `libs/`、`testcases/`、`tools/` 等目录下的存量代码做整体扫描
- **指定检视**：对指定文件、模块、类或函数做针对性审查
- **增量检视**：对 PR/diff 的变更代码做增量审查（维度同样适用）

检视时按 §2 的维度逐项排查，按 §3 分级，按 §4 流程推进，按 §5 评级。风格/模板符合性另见 `../SKILL.md` §5.1。

---

## 2. 检视维度（核心）

### 2.1 安全性 - 凭证硬编码

**检查点**：
- 源码中是否硬编码密码、密钥、token、私钥（如 `'huawei12#$'`、`"BeiMing@123"`）
- 即便是测试框架也不可硬编码——凭证会永久留存于版本历史，任何有仓库读权限者均可见
- 是否通过 `echo {password} | cmd` 管道传递密码（`ps aux` 可见进程参数）
- 是否在日志/异常信息中输出敏感数据

**正确做法**：
```python
password = os.environ.get("UBSE_CERT_PASSWORD", "")
# 或要求调用者必须传入，不给默认值
```
更安全的密码传递方式：写入临时文件或经 stdin 传递，避免出现在命令行参数中。

---

### 2.2 真值判断 vs None 判断

**检查点**：
- `if not value:` 会将 `""`、`0`、`[]`、`{}` 视为 falsy，是否与意图一致
- 当语义需要区分"未提供"与"空值"时，必须用 `if value is None:` / `if value is not None:`
- 典型误用：
  - 删除配置项：`if not value:` 会把空字符串 `""` 也当作删除信号 → 应 `if value is None:`
  - 备份成功判定：`bool(res.get("stdout"))` 对空文件返回 `False` → 应 `res.get("stdout") is not None`
  - 文件计数：`if not file_name: return 0` 把未传参误判为目录空 → 应区分"未传参"与"目录空"

**判断口诀**：默认值为 `None` 的参数用 `is None` 判断；只有确认空值等价于"无"时才用 truthiness。

---

### 2.3 递归与重试安全

**检查点**：
- 异常处理分支中是否存在递归调用自身（`except: ... self(...)`)
- 递归参数是否与原调用相同（无变化则必然再次失败 → 无限递归 → `RecursionError` 栈溢出）
- 错误源是否为持久性（如日志格式永久不可解析、网络持续不可达），持久性错误下递归必死

**正确做法**：
```python
def get_latest_journal_date(node, keyword, _retry=0):
    try:
        ...
    except ValueError:
        if _retry >= 3:
            logger.error(f"Failed to parse journal date after {_retry} retries")
            return "0"
        return get_latest_journal_date(node, keyword, _retry + 1)
```
或直接返回安全默认值，不重试。

---

### 2.4 字典与属性访问安全

**检查点（字典）**：
- `node.run(...)` 返回结果的链式访问是否提供默认值：`.get("stdout", "")` 而非 `.get("stdout").xxx`
- `.get("key")` 无默认值时返回 `None`，后续 `.xxx` / `.method()` 会触发 `AttributeError`
- 多处调用同一返回结构时，检查是否存在遗漏默认值的调用点

**检查点（实例属性）**：
- 方法引用 `self.xxx` 时，确认对应 fixture / `__init__` / 类属性已初始化该属性
- 跨继承层级尤其危险：
  - 属性由父类 A 的 fixture 设置，但当前类 B 不继承 A 且自身 fixture 也未设置 → `AttributeError`
  - 例：`backup_rack_log` 引用 `self.rackmanager_log`，该属性由 `UB_Pooling_BaseCase` 的 fixture 设置，而 `MEM_Pooling_BaseCase` 不继承它

**正确做法**：
```python
# fixture 中补齐属性
instance.rackmanager_log = f"{instance.LOG_PATH}/rackmanager.log"
# 或方法内回退
log_path = getattr(self, "rackmanager_log", self.LOG_PATH)
```

---

### 2.5 Shell 命令组合安全

**检查点**：
- 传入 `systemctl stop {name} || pkill -9 {name}` 等封装的进程名是否含 shell 元字符（`&`、`|`、`;`、`>`、`` ` ``）
- `&` 会使命令后台化并立即返回成功，导致 `||` 回退分支永不执行
- 例：`stop_process(node, "ubse & disown")` 展开为 `systemctl stop ubse & disown || pkill -9 ubse & disown`，`|| pkill` 回退完全失效
- f-string 拼接的命令参数是否做过转义/校验，能否注入 shell

**正确做法**：
- 含元字符的命令直接 `node.run({"command": [raw_cmd]})`，绕过带 `||` 回退的封装
- 或为封装增加参数控制是否启用回退逻辑
- 对外部输入参数做 `shlex.quote()` 转义

---

### 2.6 静默失败

**检查点**：
- 参数缺失/异常时是否静默返回 `0` / `None` / `[]`，使调用者无法区分"无数据"与"出错"
- 旧逻辑抛异常的，是否被降级为静默返回（掩盖了真实错误）
- `try/except` 是否吞掉了异常既不记录也不上抛

**正确做法**：
- 对"未传参"走合理默认逻辑（如 `get_file_nums` 不传 `file_name` 时统计目录全部条目）
- 必须显式区分时抛 `ValueError` / `RuntimeError`
- `except` 分支至少 `logger.error(...)` 记录上下文

---

### 2.7 数据完整性

**检查点**：
- `str.replace('-', '')`、`str.replace(' ', '')` 等粗暴清洗是否破坏含该字符的合法数据（UUID、hostname、时间戳 `2026-07-06`）
- 字符串切片/分割的索引假设是否在输出格式变化时越界
- 解析表格/键值对时是否丢失含特殊字符的字段值

**正确做法**：用正则精准匹配目标字段，而非全局 replace；解析前校验输入格式。

---

### 2.8 文档准确性

**检查点**：
- docstring Example 中的函数名/模块名是否与实际一致（重命名后易遗漏）
- `Args` / `Returns` / `Raises` 章节是否完整、缩进是否规范（Google 风格）
- 返回值描述与实际返回类型是否一致（如声称返回 `bool` 实际返回 `str`）
- `__all__` 列表是否与模块实际导出的公开函数同步

---

### 2.9 死代码与跨文件一致性

**检查点**：
- 是否存在未被任何调用方引用的函数/方法（死代码），尤其是含缺陷的——一旦被调用即崩溃
- 同一 fixture / setup 钩子在不同文件中是否一致（如 `setup_hook` 在部分测试文件中被删、部分保留）
- `__all__` 与实际导出是否一致
- 重命名/删除函数后，全库是否仍有旧名引用

**验证手段**：全库搜索函数名，确认引用点与定义点匹配。

---

### 2.10 代码模式正确性

**检查点**：
- 多行布尔返回是否已简化且语义等价：
  ```python
  # 应简化为
  return "successfully" in res
  # 而非
  # if "successfully" in res:
  #     return True
  # return False
  ```
- 可选参数类型标注是否正确：`Optional[str] = None` 而非 `str = ''` 或 `str = None`
- 默认参数是否使用可变对象（`def f(x=[])` 是反模式）
- 类型标注是否完整（所有参数与返回值）
- 布尔返回类型是否误标为 `str`（如 `def import_cert(...) -> str:` 实际应 `-> bool`）

---

## 3. 问题分级标准

| 级别 | 含义 | 示例 |
|------|------|------|
| **P0** | 严重缺陷，必然触发 | - |
| **P1** | 阻塞，高概率触发且后果严重 | 硬编码密码、无限递归、空字符串语义错误 |
| **P2** | 建议修复，特定边界条件触发 | 空文件误报失败、shell 命令组合异常、属性未初始化 |
| **P3** | 轻微，低置信度或死代码 | docstring 示例错误、死代码、跨文件不一致 |

---

## 4. 检视流程

1. **明确范围**：确认检视是全量、指定目录/文件，还是指定函数
2. **逐文件审查**：对范围内每个文件按 §2 维度逐项排查
3. **定位问题**：记录 `file:line`、问题代码、触发条件与后果
4. **分级**：按 §3 标准定级
5. **汇总**：统计各级问题数，按 §5 给出风险评级
6. **优先级排序**：P1 优先修复，P2 视触发概率，P3 可批量处理

---

## 5. 风险评级标准

- **低风险**：无 P1，P2/P3 为文档/死代码，触发概率低
- **中等风险**：存在 P1，或 P2 在常见边界条件触发
- **高风险**：多个 P1，或问题影响核心功能路径

---

## 6. 检视原则

- **failure mode 导向**：每个问题说明"什么条件下触发、什么后果"，而非单纯风格挑剔
- **跨文件追踪**：重命名/删除函数需全库验证引用；fixture/属性改动需检查所有继承类与调用方
- **基于代码现状**：不依赖历史 diff，直接审查当前代码的正确性与安全性
- **不臆断**：低置信度问题标注为 P3 并说明置信度
- **可执行**：给出具体修复方向，必要时给出修复代码

---

## 7. 真实案例参考

### 案例 A：硬编码密码（PR #14，P1）

`import_cert` 第140行 `password = 'huawei12#$'`，经 `echo {password} | ubsectl ...` 传递。
→ 凭证永久留存版本库，且 `ps aux` 可见。应改 `os.environ.get('UBSE_CERT_PASSWORD', '')`。

### 案例 B：空字符串语义错误（PR #16，P1）

`if not value:` 取代 `if value is None:`，导致 `modify_conf_value(node, "KEY", "")` 期望设空值却执行了删除（`sed -i '/KEY=/d'`）。
→ 应 `if value is None:`，仅当显式为 None 时才删除。

### 案例 C：无限递归（PR #16，P1）

`get_latest_journal_date` 在 `except ValueError` 中递归调用自身，传入完全相同的 `node`/`keyword` → 栈溢出。
→ 增加重试计数或返回 `"0"`。

### 案例 D：属性未初始化（PR #15，P2）

`backup_rack_log` 引用 `self.rackmanager_log`，该属性由 `UB_Pooling_BaseCase` 的 fixture 设置，而 `MEM_Pooling_BaseCase` 未继承且自身 fixture 也未设置 → `AttributeError`。
→ 在 `inject_mem_pooling_dependencies` 补充 `instance.rackmanager_log = f"{instance.LOG_PATH}/rackmanager.log"`。

### 案例 E：shell 命令组合异常（PR #16，P2）

`stop_process(node, "ubse & disown")` 展开为 `systemctl stop ubse & disown || pkill -9 ubse & disown`，`&` 后台化使 `||` 回退失效。
→ 含 `& disown` 的命令直接 `node.run`，不经 `stop_process`。

### 案例 F：空文件误报失败（PR #16，P2）

`return bool(res.get("stdout"))` 对空文件返回 `False`（`bool("")` 为 False），但备份实际成功。
→ 应 `return res.get("stdout") is not None`。

### 案例 G：docstring 示例函数名错误（PR #15，P3）

`display_topo_cpu` 的 docstring Example 写成 `cli_api.display_topo(node)`，模块无此函数 → 复制示例即 `AttributeError`。
→ 应 `cli_api.display_topo_cpu(node)`。

### 案例 H：用户组重复创建报错（libs/core/user_ops.py L49-54，P2）

`create_user` 直接执行 `groupadd {group}` 而不检查用户组是否已存在 → 用户组已存在时报错 `groupadd: group 'mygroup' already exists`。
→ 应先用 `getent group {group}` 检查，不存在时才创建：
```python
res = node.run({"command": [f"getent group {safe_group}"]}, returnCode=True)
if res.get("returnCode", 1) != 0:
    node.run({"command": [f"groupadd {safe_group}"]})
```

### 案例 I：usermod 验证缺失（libs/core/user_ops.py L55-65，P2）

`create_user` 执行 `usermod -aG {group} {name}` 后无验证 → usermod 失败时静默返回，调用者无法区分"已加入组"与"未加入组"。
→ 应双重验证（命令执行 + 实际生效）：
```python
res = node.run({"command": [f"usermod -aG {safe_group} {safe_name}"]}, returnCode=True)
if res.get("returnCode", 1) != 0:
    logger.error(f"Failed to add user {name} to group {group}")
    return False

groups_res = node.run({"command": [f"id -Gn {safe_name}"]}).get("stdout", "")
groups_list = groups_res.split()
if group not in groups_list:
    logger.error(f"User {name} not in group {group}. Groups: {groups_res}")
    return False
```

### 案例 J：数据完整性 - 日志包含实际数据（libs/core/user_ops.py L63，P2）

日志仅输出 `User {name} not in group {group}` 而不含实际 groups_res → 调试时无法判断是用户组验证失败还是用户组名称含特殊字符。
→ 日志应包含实际输出：`logger.error(f"User {name} not in group {group}. Groups: {groups_res}")`。
→ 便于定位问题根源（如用户组名称含空格、输出格式异常等）。

---

## 配合使用

- **`../SKILL.md` §5**：浓缩版检查表（日常检视入口）
- **`../style/common-style.md`**：通用风格基准（"该写成什么样"）
- **`../style/cli-api-style.md`** / **`../style/basecase-style.md`**：分层风格基准
- **`../reference/pyguide.md`**：判断是否符合 Google Python Style Guide

---

## 更新日志

| 日期 | 版本 | 说明 |
|-----|------|------|
| 2026-07-06 | v1.0 | 基于 PR #14/#15/#16 的 atomgit-bot 检视意见提炼而成 |
| 2026-07-06 | v1.1 | 重构为全量/指定代码检视，删除输出格式章节，聚焦检视维度 |
| 2026-07-06 | v1.2 | 迁入 review/ 子目录，更新交叉引用，明确与 SKILL §5 的浓缩/深度关系 |
| 2026-07-06 | v1.3 | 补充案例 H/I/J：用户组重复创建、usermod 验证缺失、数据完整性日志改进 |
