# 贡献指南

感谢您对 UBS Test 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请：

1. 检查 [Issues](https://github.com/example/ubs-test/issues) 确认问题未被报告
2. 创建新的 Issue，使用合适的模板
3. 提供清晰的问题描述和重现步骤

### 提交代码

#### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/example/ubs-test.git
cd ubs-test

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install
```

#### 代码规范

本项目严格遵循以下代码规范：

- **PEP8**: Python 代码风格指南
- **Black**: 代码格式化工具
- **isort**: 导入语句排序
- **mypy**: 类型检查

在提交代码前，请确保：

```bash
# 格式化代码
black .
isort .

# 类型检查
mypy libs/

# 运行测试
pytest

# 运行 pre-commit 检查
pre-commit run --all-files
```

#### 提交流程

1. **Fork 仓库**: 点击 GitHub 页面上的 Fork 按钮
2. **创建分支**: 从 `main` 分支创建您的特性分支

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **编写代码**: 实现您的功能或修复
4. **添加测试**: 为您的代码添加相应的测试用例
5. **运行检查**: 确保所有测试通过且代码符合规范

   ```bash
   pytest
   black .
   isort .
   mypy libs/
   ```

6. **提交更改**: 使用清晰的提交信息

   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

7. **推送到您的 Fork**:

   ```bash
   git push origin feature/your-feature-name
   ```

8. **创建 Pull Request**: 在 GitHub 上创建 PR

#### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 添加或修改测试
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat: add container networking tests
fix: resolve test environment cleanup issue
docs: update README with new examples
```

#### Pull Request 检查清单

在提交 PR 前，请确保：

- [ ] 代码通过所有测试 (`pytest`)
- [ ] 代码通过类型检查 (`mypy libs/`)
- [ ] 代码通过格式化检查 (`black .`, `isort .`)
- [ ] 添加了相应的测试用例
- [ ] 更新了相关文档
- [ ] PR 描述清晰说明了更改内容
- [ ] 提交信息符合规范

## 测试指南

### 编写测试

- 单元测试放在 `tests/` 目录
- 集成测试放在 `testcases/` 目录
- 使用 pytest 桮架
- 测试文件以 `test_*.py` 或 `*test.py` 命名
- 测试函数以 `test_` 开头

### 测试标记

使用 pytest 标记来分类测试：

```python
@pytest.mark.unit
def test_example():
    pass

@pytest.mark.integration
@pytest.mark.virt
def test_vm_feature():
    pass
```

### 运行特定测试

```bash
# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 运行虚拟化测试
pytest -m virt

# 跳过慢速测试
pytest -m "not slow"
```

## 文档指南

### 文档位置

- 项目文档: `docs/` 目录
- API 文档: 使用 Sphinx 生成
- 示例代码: `examples/` 目录

### 文档风格

- 使用清晰简洁的语言
- 提供代码示例
- 保持文档与代码同步更新

## 代码审查

所有 PR 都需要经过代码审查。审查者会检查：

- 代码质量和风格
- 测试覆盖率
- 文档完整性
- 功能正确性
- 潜在的安全问题

请及时响应审查意见，进行必要的修改。

## 发布流程

版本发布由维护者负责，遵循语义化版本：

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

## 获取帮助

如果您在贡献过程中遇到问题：

- 查看 [README.md](README.md) 了解项目信息
- 查看 [Issues](https://github.com/example/ubs-test/issues) 寻找类似问题
- 创建新的 Issue 寻求帮助

## 许可证

通过贡献代码，您同意您的贡献将根据项目的 [MulanPSL2](LICENSE) 许可证进行授权。

## 致谢

感谢所有贡献者的努力！您的贡献让这个项目变得更好。
