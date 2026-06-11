"""UBSVirt common utilities."""

from libs.modules.ubsvirt.common.string_util import generate_random_string
from libs.modules.ubsvirt.common.node_manager import get_new_sshconnect

__all__ = [
    "generate_random_string",
    "get_new_sshconnect",
]