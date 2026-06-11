import re
import uuid
from flask import request, jsonify, make_response

from . import lcne_bp

true = True
false = False
null = None

"""
这是一个示例
@lcne_bp.route('/接口路径', methods=["GET"])
def abc():
    data = {
        …………
    }
    return jsonify(data)
"""


@lcne_bp.route('/test_api', methods=["GET"])
def abc():
    data = {
        'success': true,
    }
    return jsonify(data)


@lcne_bp.route("/<lcneId>/restconf/operational/ntp:ntp", methods=["PATCH"])
def patch_lcne_ntp_processors(lcneId):
    data = """<?xml version="1.0" encoding="utf-8"?><rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext"
    xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
    message-id="38"
    nc-ext:flow-id="129">
    <ok/></rpc-reply>"""
    return data


@lcne_bp.route("/<lcneId>/restconf/operational/config:config", methods=["PATCH"])
def process_lcne_init_cfg(lcneId):
    data = """<?xml version="1.0" encoding="utf-8"?><rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext"
    xmlns="urn:ietf:params:xml:ns:config:base:1.0"
    message-id="38"
    nc-ext:flow-id="129">
    <ok/></rpc-reply>"""
    return data


@lcne_bp.route("/<lcneId>/oc-telemetry:telemetry-system/", methods=["POST"])
def patch_lcne_telemetry_processors(lcneId):
    data = """<?xml version="1.0" encoding="utf-8"?><rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext"
    xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
    message-id="38"
    nc-ext:flow-id="129">
    <ok/></rpc-reply>"""
    return data


@lcne_bp.route("/<lcneId>/snmp:snmp/snmp:agent-flag", methods=["PATCH"])
def enable_lcne_snmp_agent(lcneId):
    reqData = request.data.decode('utf-8')
    if re.findall("message-id=\'(\d+)\'", reqData):
        data = """<?xml version="1.0" encoding="UTF-8"?>
        <rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext" message-id="msgId" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" nc-ext:flow-id="15575">
        <ok/>
        </rpc-reply>
        """.replace("msgId", re.findall("message-id=\'(\d+)\'", reqData)[0])
    else:
        return "error"
    return data


@lcne_bp.route("/<lcneId>/snmp:snmp/snmp:engine", methods=["PATCH"])
def enable_lcne_snmp_engine(lcneId):
    reqData = request.data.decode('utf-8')
    if re.findall("merge", reqData):
        if re.findall("message-id=\'(\d+)\'", reqData):
            data = """<?xml version="1.0" encoding="UTF-8"?>
            <rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext" message-id="msgId" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" nc-ext:flow-id="15575">
            <ok/>
            </rpc-reply>
            """.replace("msgId", re.findall("message-id=\'(\d+)\'", reqData)[0])
        else:
            return "error"
        return data
    elif re.findall("get", reqData):
        if re.findall("message-id=\"(\d+)\"", reqData):
            data = """<?xml version="1.0" encoding="UTF-8"?>
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="msgId">
            <data>
                <snmp xmlns="urn:huawei:yang:huawei-snmp">
                <engine>
                    <version>v3</version>
                    <id>80:00:07:DB:03:20:24:10:23:01:57</id>
                    <max-msg-size>12000</max-msg-size>
                </engine>
                </snmp>
            </data>
            </rpc-reply>
            """.replace("msgId", re.findall("message-id=\"(\d+)\"", reqData)[0])
        else:
            return "error"
        return data


@lcne_bp.route("/<lcneId>/snmp:snmp/snmp:target-hosts/snmp:target-host", methods=["PATCH"])
def enable_lcne_snmp_target_host(lcneId):
    reqData = request.data.decode('utf-8')
    if re.findall("message-id=\'(\d+)\'", reqData):
        data = """<?xml version="1.0" encoding="UTF-8"?>
        <rpc-reply xmlns:nc-ext="urn:huawei:yang:huawei-ietf-netconf-ext" message-id="msgId" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" nc-ext:flow-id="15575">
        <ok/>
        </rpc-reply>
        """.replace("msgId", re.findall("message-id=\'(\d+)\'", reqData)[0])
    else:
        return "error"
    return data


@lcne_bp.route("/lingqu-topology:topology/lingqu-topology:nodes", methods=["GET"])
def get_lcne_link_info():
    data = """<?xml version="1.0" encoding="UTF-8"?>
    <data>
      <nodes>
        <node>
          <slot-id>Node0</slot-id>
          <chip-id>0</chip-id>
          <card-id>0</card-id>
          <unit-id>0</unit-id>
          <chip-type>CPU</chip-type>
          <ports>
            <port>
                <port-id>0:36to1:36</port-id>
                <if-name>400GPU3/3/3</if-name>
                <port-role>rack-in</port-role>
                <remote-slot-id>Node1</remote-slot-id>
                <port-status>UP</port-status>
                <remote-chip-id>0</remote-chip-id>
                <remote-card-id>0</remote-card-id>
                <remote-port-id>0</remote-port-id>
                <remote-if-name>400GPU3/3/3</remote-if-name>
            </port>
          </ports>
        </node>
        <node>
          <slot-id>Node1</slot-id>
          <chip-id>0</chip-id>
          <card-id>0</card-id>
          <unit-id>0</unit-id>
          <chip-type>CPU</chip-type>
          <ports>
            <port>
                <port-id>1:36to0:36</port-id>
                <if-name>400GPU3/3/3</if-name>
                <port-role>rack-in</port-role>
                <remote-slot-id>Node0</remote-slot-id>
                <port-status>UP</port-status>
                <remote-chip-id>0</remote-chip-id>
                <remote-card-id>0</remote-card-id>
                <remote-port-id>0</remote-port-id>
                <remote-if-name>400GPU3/3/3</remote-if-name>
            </port>
          </ports>
        </node>
      </nodes>
    </data>
    """
    return data


@lcne_bp.route('/lingqu-inventory:lingqu-inventory/lingqu-inventory:logic-entity-mappings', methods=["GET"])
def logic_entity_mappings():
    data = """<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <filter type="subtree">
      <lingqu-inventory xmlns="urn:huawei:yang:huawei-lingqu-inventory">
        <logic-entity-mappings>
          <logic-entity-mapping>
            <logic-entity-bus-instance-eid>0x00412</logic-entity-bus-instance-eid>
            <logic-entity-guid>00e0fc-2-0-a001-0008-0000000002</logic-entity-guid>
            <physical-entity-mappings>
              <physical-entity-mapping>
                <index>1.Node0.1.36.1</index>
                <index>1.Node0.1.36.1</index>
              </physical-entity-mapping>
            </physical-entity-mappings>
          </logic-entity-mapping>
          <logic-entity-mapping>
            <logic-entity-bus-instance-eid>0x00411</logic-entity-bus-instance-eid>
            <logic-entity-guid>00e0fc-2-0-a001-0008-0000000001</logic-entity-guid>
            <physical-entity-mappings>
              <physical-entity-mapping>
                <index>1.Node1.1.36.1</index>
                <index>1.Node1.1.36.1</index>
              </physical-entity-mapping>
            </physical-entity-mappings>
          </logic-entity-mapping>
        </logic-entity-mappings>
      </lingqu-inventory>
    </filter>
  </data>
</rpc>
    """
    return data


@lcne_bp.route("/lingqu-topology:topology/lingqu-topology:addresses", methods=["GET"])
def get_lcne_cna_info():
    data = """
<?xml version="1.0" encoding="UTF-8"?>
  <data>
      <addresses>
        <address>
          <slot-id>Node0</slot-id>
          <chip-id>0</chip-id>
          <card-id>0</card-id>
          <unit-id>0</unit-id>
          <bus-node-cna>0.0.0.1</bus-node-cna>
          <ubc-node-cna>0.0.0.1</ubc-node-cna>
          <ubg-node-ip>-</ubg-node-ip>
          <ports>
            <port>
              <port-id>0</port-id>
              <if-name>400GHL1/1/9:1</if-name>
              <bus-port-cna>0.0.0.10</bus-port-cna>
              <ubc-port-cna>0.0.0.10</ubc-port-cna>
              <ubg-port-ip>-</ubg-port-ip>
              <port-group-id>-</port-group-id>
              <ubc-port-group-cna>-</ubc-port-group-cna>
              <ubg-port-group-ip>-</ubg-port-group-ip>
            </port>
          </ports>
          <ports>
            <port>
              <port-id>1</port-id>
              <if-name>400GHL1/1/9:1</if-name>
              <bus-port-cna>0.0.0.10</bus-port-cna>
              <ubc-port-cna>0.0.0.10</ubc-port-cna>
              <ubg-port-ip>-</ubg-port-ip>
              <port-group-id>-</port-group-id>
              <ubc-port-group-cna>-</ubc-port-group-cna>
              <ubg-port-group-ip>-</ubg-port-group-ip>
            </port>
          </ports>
        </address>
        <address>
          <slot-id>Node1</slot-id>
          <chip-id>0</chip-id>
          <card-id>0</card-id>
          <unit-id>0</unit-id>
          <bus-node-cna>0.0.0.2</bus-node-cna>
          <ubc-node-cna>0.0.0.1</ubc-node-cna>
          <ubg-node-ip>-</ubg-node-ip>
          <ports>
            <port>
              <port-id>0:940to0:60</port-id>
              <if-name>400GHL1/1/9:1</if-name>
              <bus-port-cna>0.0.0.10</bus-port-cna>
              <ubc-port-cna>cna2</ubc-port-cna>
              <ubg-port-ip>-</ubg-port-ip>
              <port-group-id>mar1</port-group-id>
              <ubc-port-group-cna>-</ubc-port-group-cna>
              <ubg-port-group-ip>-</ubg-port-group-ip>
            </port>
          </ports>
        </address>
    </addresses>
  </data>
    """
    return data


@lcne_bp.route('/<lcneId>/lingqu-service:lingqu-service/lingqu-service:guest-host-destroy', methods=["POST"])
def guest_host_destroy(lcneId):
    data = """<?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
    <result>Success</result>
    </rpc-reply>
    """
    return data


@lcne_bp.route('/<lcneId>/lingqu-service:lingqu-service/lingqu-service:guest-host-create', methods=["POST"])
def guest_host_create(lcneId):
    generated_guid = str(uuid.uuid4())
    data = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
    <guest-host-create-result>Success</guest-host-create-result>
    <guest-host-bus-instance-eid>0x00413</guest-host-bus-instance-eid>
    <guest-host-guid>{generated_guid}</guest-host-guid>
    </rpc-reply>
    """
    return data
