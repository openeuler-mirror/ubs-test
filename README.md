# UBS Test

针对UB ServiceCore进行多组件的特性测试和集成测试

## 项目介绍

UBS Test 是一个专业的测试框架，用于对 UB ServiceCore 进行全面的多组件特性测试和集成测试。该项目提供了可复用的测试工具、核心测试框架以及针对虚拟化和容器特性的测试用例。

## 主要功能

- **测试框架**: 提供 TestCase 和 TestRunner 等核心测试组件
- **环境管理**: 自动化的测试环境设置和清理
- **虚拟化测试**: 针对 UB ServiceCore 虚拟化特性的集成测试
- **容器测试**: 针对 UB ServiceCore 容器特性的集成测试
- **工具函数**: 丰富的测试辅助工具和配置管理

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/example/ubs-test.git
cd ubs-test

# 安装依赖
pip install -e .
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 运行虚拟化测试
pytest -m virt

# 运行容器测试
pytest -m container

# 跳过慢速测试
pytest -m "not slow"
```

### 代码格式化

```bash
# 格格式化代码
black .
isort .

# 类型检查
mypy libs/
```

## 使用示例

### 基本测试用例

```python
from libs import TestCase, TestRunner
from libs.utils import setup_test_env, cleanup_test_env

# 创建测试用例
test_case = TestCase("my_test", "My test description")

# 添加设置和清理钩子
test_case.add_setup_hook(lambda: setup_test_env())
test_case.add_teardown_hook(lambda: cleanup_test_env())

# 运行测试
def my_test_func():
    assert True

test_case.run(my_test_func)
```

### 使用测试运行器

```python
from libs import TestCase, TestRunner

runner = TestRunner()
runner.add_test(TestCase("test1"))
runner.add_test(TestCase("test2"))

results = runner.run_all()
summary = runner.get_summary()
print(f"Total: {summary['total']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
```

## 特性

- **模块化设计**: 清晰的目录结构，易于扩展和维护
- **类型注解**: 全量 Python Type Hint 支持
- **代码规范**: 严格遵循 PEP8、Black 和 isort 标准
- **测试覆盖**: 完整的单元测试和集成测试
- **CI/CD 支持**: 自动化的代码检查和测试流程
- **开源合规**: MulanPSL2 许可证，完整的开源文档

## 开发环境

- Python 3.9+
- pytest 7.4.0+
- Black 23.7.0+
- isort 5.12.0+
- mypy 1.5.0+

## 贡献

我们欢迎所有形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献指南。

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 版本历史

请查看 [CHANGELOG.md](CHANGELOG.md) 了解详细的版本更新历史。

## 许可证

本项目采用 MulanPSL2 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 行为准则

请遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 中的行为准则。

## 安全

如果您发现安全问题，请查看 [SECURITY.md](SECURITY.md) 了解报告流程。

## 联系方式

- 作者: Jinhui Tong
- 项目主页: https://github.com/example/ubs-test
- 问题反馈: https://github.com/example/ubs-test/issues

## 致谢

感谢所有为本项目做出贡献的开发者！
