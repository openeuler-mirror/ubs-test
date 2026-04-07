"""Core test framework components."""

from typing import Any, Callable, Dict, List, Optional


class TestCase:
    """Base class for test cases with common setup/teardown."""

    def __init__(self, name: str, description: Optional[str] = None) -> None:
        self.name = name
        self.description = description or name
        self._setup_hooks: List[Callable[[], None]] = []
        self._teardown_hooks: List[Callable[[], None]] = []

    def add_setup_hook(self, hook: Callable[[], None]) -> None:
        self._setup_hooks.append(hook)

    def add_teardown_hook(self, hook: Callable[[], None]) -> None:
        self._teardown_hooks.append(hook)

    def setup(self) -> None:
        for hook in self._setup_hooks:
            hook()

    def teardown(self) -> None:
        for hook in reversed(self._teardown_hooks):
            hook()

    def run(self, test_func: Callable[[], Any]) -> Any:
        self.setup()
        try:
            return test_func()
        finally:
            self.teardown()


class TestRunner:
    """Test runner for executing and managing test cases."""

    def __init__(self) -> None:
        self.test_cases: List[TestCase] = []
        self.results: Dict[str, bool] = {}

    def add_test(self, test_case: TestCase) -> None:
        self.test_cases.append(test_case)

    def run_all(self) -> Dict[str, bool]:
        for test_case in self.test_cases:
            try:
                test_case.run(lambda: None)
                self.results[test_case.name] = True
            except Exception:
                self.results[test_case.name] = False
        return self.results

    def get_summary(self) -> Dict[str, int]:
        total = len(self.results)
        passed = sum(1 for v in self.results.values() if v)
        failed = total - passed
        return {"total": total, "passed": passed, "failed": failed}
