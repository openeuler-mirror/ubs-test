"""HCOM constants migrated from legency/testcase/ubscomm/hcom/lib/common/HCOM_Constant.py"""

import os
from pathlib import Path

CODE_PATCH_PATH = str(Path(__file__).resolve().parents[2])
RESOURCE_PATH = os.path.join(CODE_PATCH_PATH, "resource")
HCOM_RESOURCE_PATH = os.path.join(RESOURCE_PATH, "hcom")
TEST_DATA_PATH = os.path.join(HCOM_RESOURCE_PATH, "test_data")

quit_waitstr = "q mean quit"

client_input_expect_server_v1 = {
    "0": "Type:		send",
    "1": "Type:		send raw",
    "2": "Type:		send raw sgl",
    "3": "Type:		sync call",
    "4": "Type:		sync call raw",
    "5": "Type:		sync call raw sgl",
    "6": "Type:		read",
    "7": "Type:		read sgl",
    "8": "Type:		write",
    "9": "Type:		write sgl",
    "a": "Type:		async call",
    "b": "Type:		async call raw",
    "c": "Type:		async call raw sgl",
    "d": "Type:		async send",
    "e": "Type:		async send raw",
    "f": "Type:		async send raw sgl",
    "10": "Type:		async read",
    "11": "Type:		async read sgl",
    "12": "Type:		async write",
    "13": "Type:		async write sgl",
    "14": "Type:		sync rndv call",
    "15": "Type:		sync rndv sgl call",
    "16": "Type:		async rndv call",
    "17": "Type:		async rndv sgl call",
    "q": "working thread exit"
}

client_input_expect_server_v2 = {
    "0": "Type:		send",
    "1": "Type:		call",
    "2": "Type:		read",
    "3": "Type:		write",
    "4": "Type:		async send",
    "5": "Type:		async call",
    "6": "Type:		async read",
    "7": "Type:		async write",
    "8": "Type:		rndv send",
    "9": "Type:		rndv call",
    "a": "Type:		async rndv send",
    "b": "Type:		async rndv call",
    "c": "Type:		read sgl",
    "d": "Type:		write sgl",
    "e": "Type:		async read sgl",
    "f": "Type:		async write sgl",
    "q": "working thread exit"
}

client_input_expect_transport = {
    "0": "Type:		send",
    "1": "Type:		send raw",
    "2": "Type:		send raw sgl",
    "3": "Type:		write",
    "4": "Type:		write sgl",
    "5": "Type:		read",
    "6": "Type:		read sgl",
    "q": "working thread exit"
}

server_input = ["q", "@#>"]
server_waitstr = "Destroy endpoint"

server_error_expect = {
    "tls_wait": "Failed to initialize TLS context for new connection"
}

client_error_expect = {
    "connect_fail": "Failed to connect server via oob, result 128"
}