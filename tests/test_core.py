"""Unit tests for libs.core module."""

import pytest

from libs.core import TestCase, TestRunner


@pytest.mark.unit
class TestTestCase:
    """Test TestCase class."""

    def test_case_creation(self):
        """Test basic TestCase creation."""
        test_case = TestCase("test_example", "Example test case")
        assert test_case.name == "test_example"
        assert test_case.description == "Example test case"

    def test_setup_teardown_hooks(self):
        """Test setup and teardown hooks."""
        test_case = TestCase("test_hooks")
        setup_called = False
        teardown_called = False

        def setup_func():
            nonlocal setup_called
            setup_called = True

        def teardown_func():
            nonlocal teardown_called
            teardown_called = True

        test_case.add_setup_hook(setup_func)
        test_case.add_teardown_hook(teardown_func)

        test_case.setup()
        assert setup_called is True

        test_case.teardown()
        assert teardown_called is True

    def test_run_with_test_func(self):
        """Test running test case with test function."""
        test_case = TestCase("test_run")
        test_executed = False

        def test_func():
            nonlocal test_executed
            test_executed = True

        test_case.run(test_func)
        assert test_executed is True


@pytest.mark.unit
class TestTestRunner:
    """Test TestRunner class."""

    def test_runner_creation(self):
        """Test basic TestRunner creation."""
        runner = TestRunner()
        assert runner.test_cases == []
        assert runner.results == {}

    def test_add_test(self):
        """Test adding test cases to runner."""
        runner = TestRunner()
        test_case = TestCase("test_example")
        runner.add_test(test_case)
        assert len(runner.test_cases) == 1

    def test_run_all(self):
        """Test running all test cases."""
        runner = TestRunner()
        test_case1 = TestCase("test_1")
        test_case2 = TestCase("test_2")
        runner.add_test(test_case1)
        runner.add_test(test_case2)

        results = runner.run_all()
        assert len(results) == 2
        assert results["test_1"] is True
        assert results["test_2"] is True

    def test_get_summary(self):
        """Test getting test summary."""
        runner = TestRunner()
        test_case = TestCase("test_example")
        runner.add_test(test_case)
        runner.run_all()

        summary = runner.get_summary()
        assert summary["total"] == 1
        assert summary["passed"] == 1
        assert summary["failed"] == 0
