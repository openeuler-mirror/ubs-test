"""Result verify AW migrated from legency/testcase/ubscomm/hcom/lib/common/result_verify_aw.py"""

import re
import logging

logger = logging.getLogger(__name__)


def update_if_not_fail(result, key, status):
    if result.get(key) != "fail":
        result[key] = status


def check_latency_output(text: str, size_str: str) -> bool:
    """
    Checks if the string matches the output structure of the Latency Test.

    Args:
        text: The string to be checked.
        size_str: The expected data size (e.g., 2048, etc.).

    Returns:
        True if the string contains the expected structure, False otherwise.
    """
    sep_line = r"(?:-{10,}\s+)?"

    pattern = re.compile(
        rf"{sep_line}\s+"
        r"Latency Test\s+"
        r"Cpu id\s+:\s+\S+\s+"
        rf"Datasize\s+:\s+{size_str},\s+Iterations\s+:\s+1000\s+"
        rf"{sep_line}\s+"
        r"#bytes\s+#iterations\s+t_min\[usec\]\s+t_max\[usec\]\s+t_typical\[usec\]\s+t_avg\[usec\]\s+t_stdev\[usec\]\s+99% percentile\[usec\]\s+99\.9% percentile\[usec\]\s+"
        rf"{size_str}\s+1000\s+(?:\S+\s+){{7}}\S+"
        rf"{sep_line}\s+",
        re.DOTALL | re.IGNORECASE
    )

    return pattern.search(text) is not None


def verify(result, expects=None, texts=None):
    """Verify expected strings appear in result."""
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


def verify_repeat(result, expects, repeat_time=1, texts=None):
    """Verify expected string appears specified number of times."""
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


def verify_repeat_list(result, expects, repeat_times, texts=None):
    """Verify multiple expected strings appear specified number of times."""
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


def verify_not(result, expects=None, texts=None):
    """Verify expected strings do NOT appear in result."""
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