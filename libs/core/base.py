"""Pytest-compatible base class for migrated legacy test cases.

This module provides a TestCase base class that mimics the behavior of
UniAutos.TestEngine.Case, allowing legacy test cases to be migrated to
pytest with minimal changes.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path


class TestCase:
    """Base class for migrated legacy test cases.
    
    CRITICAL: This class NO LONGER has __init__ method.
    pytest cannot collect test classes with __init__ (even with default args).
    
    Initialization is handled by:
    1. Class attributes (default values)
    2. Fixture injection (in child classes like CMBaseCase)
    3. Lazy initialization in methods (for logger)
    
    Legacy test cases should inherit from this class and implement:
        - procedure(): The main test logic (converted to test_xxx method)
        - preTestCase(): Setup logic (converted to setup_method)
        - postTestCase(): Cleanup logic (converted to teardown_method)
    
    Example:
        class TestVMMigration(TestCase):
            def setup_method(self):
                self.logStep("Prepare test environment")
                
            def test_vm_migration(self):
                self.logStep("Start VM migration test")
                self.assertTrue(condition, "VM migration failed")
                
            def teardown_method(self):
                self.logStep("Cleanup test environment")
    """
    
    failureException = AssertionError
    
    # Class attributes (initialized without __init__)
    name: str = ""
    description: str = ""
    _cleanup_stack: List[Callable] = []
    _test_steps: List[str] = []
    _logger: Optional[logging.Logger] = None
    
    # Resource placeholders (to be injected by fixtures)
    resource: Optional[Any] = None
    nodes: List[Any] = []
    node: Optional[Any] = None
    customParam: Dict[str, Any] = {}
    
    @property
    def logger(self) -> logging.Logger:
        """Lazy initialization of logger."""
        if self._logger is None:
            self._logger = logging.getLogger(self.__module__)
        return self._logger
    
    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        """Allow logger to be set by fixtures."""
        self._logger = value
    
    def logStep(self, step_message: str) -> None:
        """Log test step information."""
        self.logger.info(f"[STEP] {step_message}")
        self._test_steps.append(step_message)
    
    def tcStep(self, step_message: str) -> None:
        """Log test step information (legacy alias for logStep).
        
        Legacy method: self.tcStep("Step message")
        This is an alias for logStep() to maintain compatibility with legacy test cases.
        
        Args:
            step_message: Step description message
        """
        return self.logStep(step_message)
        
    def logSubStep(self, substep_message: str) -> None:
        """Log sub-step information.
        
        Args:
            substep_message: Sub-step description message
        """
        self.logger.info(f"[SUB-STEP] {substep_message}")
        
    def logInfo(self, info_message: str) -> None:
        """Log info message.
        
        Legacy method: self.logInfo("Info message")
        
        Args:
            info_message: Information message
        """
        self.logger.info(info_message)
        
    def logWarn(self, warn_message: str) -> None:
        """Log warning message.
        
        Legacy method: self.logWarn("Warning message")
        
        Args:
            warn_message: Warning message
        """
        self.logger.warning(warn_message)
        
    def logError(self, error_message: str, exception_msg: str = "") -> None:
        """Log error message.
        
        Legacy method: self.logError("Error message")
        
        Args:
            error_message: Error message
            exception_msg: Exception message (optional)
        """
        self.logger.error(f"{error_message} {exception_msg}")
        
    def logDebug(self, debug_message: str) -> None:
        """Log debug message.
        
        Args:
            debug_message: Debug message
        """
        self.logger.debug(debug_message)
        
    def assertTrue(self, condition: bool, message: str = "") -> None:
        """Assert condition is True.
        
        Legacy method: self.assertTrue(condition, "Message")
        Compatible with pytest: assert condition, message
        
        Args:
            condition: Condition to check
            message: Failure message
            
        Raises:
            AssertionError: If condition is False
        """
        if not condition:
            self.logError(f"Assertion failed: {message}")
            raise AssertionError(message)
        self.logInfo(f"Assertion passed")
        
    def assertFalse(self, condition: bool, message: str = "") -> None:
        """Assert condition is False.
        
        Args:
            condition: Condition to check
            message: Failure message
            
        Raises:
            AssertionError: If condition is True
        """
        if condition:
            self.logError(f"Assertion failed: {message}")
            raise AssertionError(message)
            
    def assertEqual(self, first: Any, second: Any, message: str = "") -> None:
        """Assert two values are equal.
        
        Legacy method: self.assertEqual(actual, expected, "Message")
        
        Args:
            first: First value
            second: Second value
            message: Failure message
            
        Raises:
            AssertionError: If values are not equal
        """
        if first != second:
            error_msg = f"{message}: {first} != {second}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: {first} == {second}")
        
    def assertNotEqual(self, first: Any, second: Any, message: str = "") -> None:
        """Assert two values are not equal.
        
        Args:
            first: First value
            second: Second value  
            message: Failure message
            
        Raises:
            AssertionError: If values are equal
        """
        if first == second:
            error_msg = f"{message}: {first} == {second}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
            
    def assertIn(self, member: Any, container: Any, message: str = "") -> None:
        """Assert member is in container.
        
        Args:
            member: Member to check
            container: Container to check
            message: Failure message
            
        Raises:
            AssertionError: If member is not in container
        """
        if member not in container:
            error_msg = f"{message}: {member} not in {container}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
            
    def assertNotIn(self, member: Any, container: Any, message: str = "") -> None:
        """Assert member is not in container.
        
        Args:
            member: Member to check
            container: Container to check
            message: Failure message
            
        Raises:
            AssertionError: If member is in container
        """
        if member in container:
            error_msg = f"{message}: {member} in {container}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
            
    def assertGreater(self, first: Any, second: Any, message: str = "") -> None:
        """Assert first > second.
        
        Args:
            first: First value
            second: Second value
            message: Failure message
            
        Raises:
            AssertionError: If first <= second
        """
        if first <= second:
            error_msg = f"{message}: {first} <= {second}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
            
    def assertLess(self, first: Any, second: Any, message: str = "") -> None:
        """Assert first < second.
        
        Args:
            first: First value
            second: Second value
            message: Failure message
            
        Raises:
            AssertionError: If first >= second
        """
        if first >= second:
            error_msg = f"{message}: {first} >= {second}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    # ========== Additional assertion methods for legacy compatibility ==========
    
    def assertIsNone(self, obj: Any, message: str = "") -> None:
        """Assert obj is None.
        
        Legacy method: self.assertIsNone(obj, "Message")
        
        Args:
            obj: Object to check
            message: Failure message
            
        Raises:
            AssertionError: If obj is not None
        """
        if obj is not None:
            error_msg = f"{message}: {obj} is not None"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: obj is None")
    
    def assertIsNotNone(self, obj: Any, message: str = "") -> None:
        """Assert obj is not None.
        
        Legacy method: self.assertIsNotNone(obj, "Message")
        
        Args:
            obj: Object to check
            message: Failure message
            
        Raises:
            AssertionError: If obj is None
        """
        if obj is None:
            error_msg = f"{message}: obj is None"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: obj is not None")
    
    def assertRegex(self, text: Union[str, bytes], pattern: Union[str, bytes], message: str = "") -> None:
        """Assert text matches regex pattern.
        
        Legacy method: self.assertRegex(text, pattern, "Message")
        
        Args:
            text: Text to match
            pattern: Regex pattern
            message: Failure message
            
        Raises:
            AssertionError: If pattern does not match text
        """
        if not re.search(pattern, text):
            error_msg = f"{message}: '{text}' does not match pattern '{pattern}'"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: '{text}' matches pattern '{pattern}'")
    
    def assertNotRegex(self, text: Union[str, bytes], pattern: Union[str, bytes], message: str = "") -> None:
        """Assert text does not match regex pattern.
        
        Args:
            text: Text to check
            pattern: Regex pattern
            message: Failure message
            
        Raises:
            AssertionError: If pattern matches text
        """
        if re.search(pattern, text):
            error_msg = f"{message}: '{text}' matches pattern '{pattern}'"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertAlmostEqual(self, first: float, second: float, places: int = 7, message: str = "") -> None:
        """Assert two values are almost equal within given decimal places.
        
        Legacy method: self.assertAlmostEqual(a, b, places=7, "Message")
        
        Args:
            first: First value
            second: Second value
            places: Number of decimal places to compare
            message: Failure message
            
        Raises:
            AssertionError: If values differ by more than places
        """
        if round(abs(first - second), places) != 0:
            error_msg = f"{message}: {first} != {second} within {places} places"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: {first} ~= {second} within {places} places")
    
    def assertNotAlmostEqual(self, first: float, second: float, places: int = 7, message: str = "") -> None:
        """Assert two values are not almost equal.
        
        Args:
            first: First value
            second: Second value
            places: Number of decimal places to compare
            message: Failure message
            
        Raises:
            AssertionError: If values are almost equal
        """
        if round(abs(first - second), places) == 0:
            error_msg = f"{message}: {first} ~= {second} within {places} places"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertRaises(self, expected_exception: type, func: Callable, *args, **kwargs) -> None:
        """Assert that callable raises expected exception.
        
        Legacy method: self.assertRaises(Exception, func, args)
        
        Args:
            expected_exception: Expected exception type
            func: Callable to test
            *args: Arguments to pass to callable
            **kwargs: Keyword arguments to pass to callable
            
        Raises:
            AssertionError: If expected exception is not raised
        """
        try:
            func(*args, **kwargs)
            error_msg = f"{expected_exception.__name__} not raised"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        except expected_exception as e:
            self.logInfo(f"Assertion passed: {expected_exception.__name__} raised: {e}")
        except Exception as e:
            error_msg = f"Unexpected exception: {type(e).__name__} instead of {expected_exception.__name__}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertListEqual(self, list1: List[Any], list2: List[Any], message: str = "") -> None:
        """Assert two lists are equal.
        
        Args:
            list1: First list
            list2: Second list
            message: Failure message
            
        Raises:
            AssertionError: If lists are not equal
        """
        if list1 != list2:
            error_msg = f"{message}: {list1} != {list2}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertDictEqual(self, dict1: Dict[Any, Any], dict2: Dict[Any, Any], message: str = "") -> None:
        """Assert two dicts are equal.
        
        Args:
            dict1: First dict
            dict2: Second dict
            message: Failure message
            
        Raises:
            AssertionError: If dicts are not equal
        """
        if dict1 != dict2:
            error_msg = f"{message}: {dict1} != {dict2}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertSetEqual(self, set1: set, set2: set, message: str = "") -> None:
        """Assert two sets are equal.
        
        Args:
            set1: First set
            set2: Second set
            message: Failure message
            
        Raises:
            AssertionError: If sets are not equal
        """
        if set1 != set2:
            error_msg = f"{message}: {set1} != {set2}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
    
    def assertMultiLineEqual(self, first: str, second: str, message: str = "") -> None:
        """Assert two multiline strings are equal.
        
        Args:
            first: First string
            second: Second string
            message: Failure message
            
        Raises:
            AssertionError: If strings are not equal
        """
        if first != second:
            error_msg = f"{message}: Multiline strings differ"
            self.logError(error_msg)
            # Show first difference
            first_lines = first.splitlines()
            second_lines = second.splitlines()
            for i, (line1, line2) in enumerate(zip(first_lines, second_lines)):
                if line1 != line2:
                    error_msg += f"\nLine {i+1}: '{line1}' != '{line2}'"
                    break
            raise AssertionError(error_msg)
            
    def addCleanUpStack(self, clean_actions: Any) -> None:
        """Add cleanup action to cleanup stack.
        
        Legacy method: self.addCleanUpStack(cleanAction)
        Cleanup actions are executed in LIFO order during teardown.
        
        Args:
            clean_actions: Cleanup action (function, lambda, or callable)
        """
        if isinstance(clean_actions, list):
            self._cleanup_stack.extend(clean_actions)
        else:
            self._cleanup_stack.append(clean_actions)
            
    def performCleanUp(self) -> None:
        """Execute all cleanup actions in the stack.
        
        Legacy method: self.performCleanUp()
        Actions are executed in reverse order (LIFO).
        
        Raises:
            Exception: If cleanup action fails
        """
        self.logInfo("Performing cleanup actions")
        while self._cleanup_stack:
            clean_action = self._cleanup_stack.pop()
            self.logInfo(f"Executing cleanup: {clean_action}")
            try:
                if callable(clean_action):
                    clean_action()
                elif isinstance(clean_action, str):
                    # Execute string command (legacy support)
                    exec(clean_action)
            except Exception as e:
                self.logError(f"Cleanup action failed: {e}")
                # Continue with remaining cleanup actions
                
    def getParameter(self, param_name: Optional[str] = None) -> Any:
        """Get parameter value from customParam.
        
        Legacy method: self.getParameter("param_name")
        
        Args:
            param_name: Parameter name (optional, returns all if None)
            
        Returns:
            Parameter value or dict of all parameters
        """
        if param_name is None:
            return self.customParam
        return self.customParam.get(param_name)
        
    def get_test_steps(self) -> List[str]:
        """Get all logged test steps.
        
        Returns:
            List of test step messages
        """
        return self._test_steps
        
    def clear_test_steps(self) -> None:
        """Clear test steps list."""
        self._test_steps.clear()
    
    # ========== High-frequency basecase methods ==========
    
    def get_node_number(self) -> int:
        """Get number of test nodes.
        
        Legacy method from KubernetesBaseCase.
        
        Returns:
            Number of nodes in self.nodes list
        """
        return len(self.nodes) if self.nodes else 0
    
    def get_pod_list_by_name(self, pod_name_pattern: str) -> list:
        """Get pod list by name pattern.
        
        Legacy method from KubernetesBaseCase.
        TODO: Implement Kubernetes pod query logic
        
        Args:
            pod_name_pattern: Pod name pattern to search
            
        Returns:
            List of pod resources matching pattern
        """
        self.logWarn(f"get_pod_list_by_name not implemented for {pod_name_pattern}")
        return []
    
    def delete_pod_by_name(self, pod_name: str, namespace: str = "default") -> None:
        """Delete pod by name.
        
        Legacy method from KubernetesBaseCase.
        TODO: Implement Kubernetes pod deletion
        
        Args:
            pod_name: Pod name to delete
            namespace: Kubernetes namespace
        """
        self.logWarn(f"delete_pod_by_name not implemented for {pod_name}")
    
    def change_hugepage(self, node_name: str, numa: str, size: int) -> None:
        """Change hugepage configuration.
        
        Legacy method from KubernetesBaseCase.
        TODO: Implement hugepage configuration
        
        Args:
            node_name: Node name
            numa: NUMA node identifier
            size: Hugepage size
        """
        self.logWarn(f"change_hugepage not implemented for {node_name}")
    
    def set_label_numa(self) -> None:
        """Set node NUMA labels.
        
        Legacy method from KubernetesBaseCase.
        TODO: Implement Kubernetes node labeling
        """
        self.logWarn("set_label_numa not implemented")
    
    def assertGreaterEqual(self, first: Any, second: Any, message: str = "") -> None:
        """Assert first >= second.
        
        Args:
            first: First value
            second: Second value
            message: Failure message
            
        Raises:
            AssertionError: If first < second
        """
        if first < second:
            error_msg = f"{message}: {first} < {second}"
            self.logError(error_msg)
            raise AssertionError(error_msg)
        self.logInfo(f"Assertion passed: {first} >= {second}")
    
    # ========== Node command execution interface ==========
    
    def run(self, command_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command on node (interface for legacy compatibility).
        
        Legacy method: node.run({"command": ["ls -la"], "timeout": 30})
        
        This method provides an interface for node command execution.
        Actual implementation is in NodeAdapter class.
        
        Args:
            command_dict: Dictionary containing:
                - "command": List of command strings or single string
                - "timeout": Optional timeout in seconds
                - "waitstr": Optional wait string pattern
                - "returnCode": Optional flag to return exit code
            
        Returns:
            Dictionary containing:
                - "stdout": Command stdout output
                - "stderr": Command stderr output  
                - "rc": Exit code
        
        Example:
            result = self.node.run({"command": ["ls -la"], "timeout": 30})
            stdout = result.get("stdout")
            
        Note:
            This is a placeholder method. Actual implementation requires
            NodeAdapter from libs/utils/node_adapter.py to be injected.
        """
        if self.node and hasattr(self.node, "run"):
            return self.node.run(command_dict)
        else:
            self.logWarn(f"Node adapter not available for command: {command_dict}")
            return {"stdout": "", "stderr": "Node adapter not configured", "rc": -1}
    
    def run_on_nodes(self, nodes: List[Any], command_dict: Dict[str, Any], parallel: bool = False) -> List[Dict[str, Any]]:
        """Execute command on multiple nodes.
        
        Legacy pattern: for node in self.nodes: node.run(...)
        
        Args:
            nodes: List of node objects
            command_dict: Command dictionary (same format as run())
            parallel: Execute commands in parallel (default False)
            
        Returns:
            List of result dictionaries from each node
        """
        results = []
        for node in nodes:
            if hasattr(node, "run"):
                results.append(node.run(command_dict))
            else:
                self.logWarn(f"Node {node} does not have run method")
                results.append({"stdout": "", "stderr": "Node adapter not configured", "rc": -1})
        return results