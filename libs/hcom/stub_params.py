"""Stub params migrated from legency/testcase/ubscomm/hcom/lib/model/StubParams.py"""

import copy
import logging

logger = logging.getLogger(__name__)


class ConfigAttrs:
    """Configuration attributes for stub parameters."""
    
    def __init__(self, option, data_type, server_type, value, description):
        self.option = option
        self.data_type = data_type
        self.server_type = server_type
        self.value = value
        self.description = description

    @classmethod
    def from_dict(cls, data: dict):
        return cls(data["option"], data["data_type"], data["server_type"], data["value"], data["description"])

    def get_cmd(self, server_type):
        if server_type in self.server_type:
            if type(self.value) is dict:
                return self.match_data_type(self.data_type, self.value[server_type])
            else:
                return self.match_data_type(self.data_type, self.value)
        else:
            return ""

    def match_data_type(self, data_type, value):
        if not value:
            return ""
        elif data_type == 2:
            return f"{self.option} "
        else:
            return f"{self.option} {value} "


class Params:
    """Test parameters with config list and argv values."""
    
    def __init__(self, config_list: dict, argv: dict):
        for k, v in argv.items():
            config_list[k].value = v
        for k, v in config_list.items():
            setattr(self, k, copy.deepcopy(v))

    def to_print(self):
        string = ""
        for key, item in vars(self).items():
            string += f"{key} = {item.value}\r\n"
        logger.info(string)

    def set_attr_value(self, key, value):
        param = getattr(self, key)
        param.value = value

    def get_run_cmd(self, server_type, ip, server_name="c_hcom_server", client_name="c_hcom_client"):
        result = ""
        self.set_attr_value("ip_eid", ip)
        for key, value in vars(self).items():
            if key == "command":
                pass
            else:
                result = result + value.get_cmd(server_type)

        if server_type == "server":
            stub_name = server_name
        else:
            stub_name = client_name
        result = f"./{stub_name} " + result

        self.to_print()
        logger.info(f"{server_type} params: {result}")
        return result