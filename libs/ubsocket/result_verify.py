"""Result verify functions migrated from legency/testcase/ubscomm/ubsocket/lib/common/result_verify_aw.py"""

import re
import logging

logger = logging.getLogger(__name__)


def verify(result: str, expects=None, texts=None) -> bool:
    """Verify expected strings appear in result.
    
    Args:
        result: The result string to verify
        expects: List of expected strings to find
        texts: List of regex patterns to match
        
    Returns:
        bool: True if all expectations are met, False otherwise
    """
    if expects is not None:
        for expect in expects:
            if result.find(expect) == -1:
                logger.error(f'{expect} not found in output!')
                return False
    if texts is not None:
        for text in texts:
            if re.search(text, result) is None:
                logger.error(f'{text} not found in output!')
                return False
    return True


def verify_repeat(result: str, expects: str, repeat_time: int = 1, texts=None) -> bool:
    """Verify expected string appears specified number of times.
    
    Args:
        result: The result string to verify
        expects: Expected string to count
        repeat_time: Expected number of occurrences
        texts: List of regex patterns to match
        
    Returns:
        bool: True if all expectations are met, False otherwise
    """
    count = result.count(expects)
    if count != repeat_time:
        logger.error(f"{expects} expected {repeat_time} times, found {count} times")
        return False
    if texts is not None:
        for text in texts:
            if re.search(text, result) is None:
                logger.error(f'{text} not found in output!')
                return False
    return True


def verify_repeat_list(result: str, expects: list, repeat_times: list, texts=None) -> bool:
    """Verify multiple expected strings appear specified number of times.
    
    Args:
        result: The result string to verify
        expects: List of expected strings
        repeat_times: List of expected occurrence counts
        texts: List of regex patterns to match
        
    Returns:
        bool: True if all expectations are met, False otherwise
    """
    if expects is not None:
        for idx in range(len(expects)):
            count = result.count(expects[idx])
            if count != repeat_times[idx]:
                logger.error(f"{expects[idx]} expected {repeat_times[idx]} times, found {count} times")
                return False
    if texts is not None:
        for text in texts:
            if re.search(text, result) is None:
                logger.error(f'{text} not found in output!')
                return False
    return True


def verify_not(result: str, expects=None, texts=None) -> bool:
    """Verify expected strings do NOT appear in result.
    
    Args:
        result: The result string to verify
        expects: List of strings that should NOT appear
        texts: List of regex patterns that should NOT match
        
    Returns:
        bool: True if none of the expectations appear, False otherwise
    """
    if expects is not None:
        for expect in expects:
            if result.find(expect) != -1:
                logger.error(f'{expect} unexpectedly found!')
                return False
    if texts is not None:
        count = 0
        for text in texts:
            if re.search(text, result) is None:
                count = count + 1
        if count != len(texts):
            logger.error(f'{texts} unexpectedly found!')
            return False
    return True