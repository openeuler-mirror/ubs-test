"""HCOM (TurboComm HCOM module) utilities and constants.

This module provides HCOM-specific test utilities migrated from:
- legency/testcase/ubscomm/hcom/lib/common/
"""

from libs.hcom.constants import (
    quit_waitstr,
    client_input_expect_server_v1,
    client_input_expect_server_v2,
    client_input_expect_transport,
    server_input,
    server_waitstr,
    server_error_expect,
    client_error_expect,
    CODE_PATCH_PATH,
    RESOURCE_PATH,
    TEST_DATA_PATH,
)

from libs.hcom.node_run import (
    node_run,
    create_ssh,
    close_ssh,
    send_cmd,
    send_cmd_list,
    node_ssh,
)

from libs.hcom.result_verify import (
    verify,
    verify_not,
    verify_repeat,
    verify_repeat_list,
)

from libs.hcom.env_check import (
    check_network_between_nodes,
    get_rdma_ip,
    get_rdma_ip_list,
    get_ub_ip,
    check_python_fixed_version,
    env_check_between_hccs_nodes,
    prepare_hccs_testing_tools,
    create_consolidated_device,
    check_pip,
    get_eid,
)

from libs.hcom.stub_params import ConfigAttrs, Params