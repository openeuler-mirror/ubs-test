# UBS Test

This project provides feature and integration testing for multiple components of UB ServiceCore.

## Project Overview

UBS Test is a professional testing framework for comprehensive feature and integration testing across multiple components of UB ServiceCore. This project provides reusable test tools, a core testing framework, and test cases covering features related to virtualization and containers.

## Functions

- **Testing framework**: core testing components such as TestCase and TestRunner
- **Environment management**: automated test environment setup and cleanup
- **Virtualization testing**: integration testing for UB ServiceCore virtualization features
- **Container testing**: integration testing for UB ServiceCore container features
- **Tool functions**: various test supporting tools and configuration management

## Quick Start

### Installation

```bash
# Clone a repository.
git clone https://github.com/example/ubs-test.git
cd ubs-test

# Install dependencies.
pip install -e .
```

### Test Running

```bash
# Run all tests.
pytest

# Run unit tests.
pytest -m unit

# Run integration tests.
pytest -m integration

# Run virtualization tests.
pytest -m virt

# Run container tests.
pytest -m container

# Skip slow tests.
pytest -m "not slow"
```

### Code Formatting

```bash
# Format code.
black .
isort .

# Check types.
mypy libs/
```

## Examples

### Basic Test Cases

```python
from libs import TestCase, TestRunner
from libs.utils import setup_test_env, cleanup_test_env

# Create a test case.
test_case = TestCase("my_test", "My test description")

# Add setup and teardown hooks.
test_case.add_setup_hook(lambda: setup_test_env())
test_case.add_teardown_hook(lambda: cleanup_test_env())

# Run the test.
def my_test_func():
    assert True

test_case.run(my_test_func)
```

### Using a Test Runner

```python
from libs import TestCase, TestRunner

runner = TestRunner()
runner.add_test(TestCase("test1"))
runner.add_test(TestCase("test2"))

results = runner.run_all()
summary = runner.get_summary()
print(f"Total: {summary['total']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
```

## Features

- **Modular design**: clear directory structure for easy expansion and maintenance
- **Type annotations**: full support for Python type hints
- **Code standards**: strict compliance with PEP 8, Black, and isort standards
- **Test coverage**: comprehensive unit and integration testing
- **CI/CD support**: automated code check and testing processes
- **Open source compliance**: licensed under Mulan PSL v2 with complete open-source documentation

## Development Environment

- Python 3.9+
- pytest 7.4.0+
- Black 23.7.0+
- isort 5.12.0+
- mypy 1.5.0+

## Contributing

We welcome contributions in all forms! For detailed contribution guidelines, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

### Contribution Process

1. Fork this repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Enable Pull Request.

## Version History

For detailed version history, refer to [CHANGELOG.md](CHANGELOG.md).

## License

This project uses the Mulan PSL v2 license. For details, see the [LICENSE](LICENSE) file.

## Code of Conduct

Please adhere to the code of conduct in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

If you discover a security issue, refer to [SECURITY.md](SECURITY.md) for the reporting process.

## Contact

- Author: Jinhui Tong
- [Project homepage](https://github.com/example/ubs-test)
- [Issue reporting](https://github.com/example/ubs-test/issues)

## Acknowledgments

Thank you to all the developers who have contributed to this project!
