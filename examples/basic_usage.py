"""Basic usage example of UBS Test framework."""

from libs import TestCase, TestRunner
from libs.utils import setup_test_env, cleanup_test_env, create_test_file, get_test_config


def example_basic_test():
    """Demonstrate basic test case usage."""
    test_case = TestCase("example_test", "Example test case")

    def setup_func():
        setup_test_env({"log_level": "INFO"})

    test_case.add_setup_hook(setup_func)
    test_case.add_teardown_hook(lambda: cleanup_test_env())

    def test_function():
        config = get_test_config()
        assert config["test_mode"] is True
        print("Test passed!")

    test_case.run(test_function)


def example_test_runner():
    """Demonstrate test runner usage."""
    runner = TestRunner()

    for i in range(3):
        test_case = TestCase(f"test_{i}", f"Test case {i}")
        runner.add_test(test_case)

    results = runner.run_all()
    summary = runner.get_summary()

    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")


def example_test_file_creation():
    """Demonstrate test file creation."""
    setup_test_env()

    try:
        test_file = create_test_file("Hello, World!", "test.txt")
        content = test_file.read_text()
        print(f"File content: {content}")
        assert content == "Hello, World!"
    finally:
        cleanup_test_env()


if __name__ == "__main__":
    print("Running basic test example...")
    example_basic_test()

    print("\nRunning test runner example...")
    example_test_runner()

    print("\nRunning test file creation example...")
    example_test_file_creation()

    print("\nAll examples completed successfully!")
