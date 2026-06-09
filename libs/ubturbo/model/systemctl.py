# -*- coding: utf-8 -*-
"""Systemd service management via systemctl."""

from libs.ubturbo.common import basic


class Service:
    """Wrapper for managing a systemd service on a remote node."""

    def __init__(self, node, service_name: str) -> None:
        self.node = node
        self.service_name = service_name

    def start(self) -> None:
        basic.run(self.node, f'systemctl start {self.service_name}')

    def stop(self) -> None:
        basic.run(self.node, f'systemctl stop {self.service_name}')

    def restart(self) -> None:
        basic.run(self.node, f'systemctl restart {self.service_name}')

    def status(self) -> str:
        return basic.run(self.node, f'systemctl status {self.service_name} --no-pager').output
