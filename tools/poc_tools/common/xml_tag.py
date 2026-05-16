# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from pydantic import BaseModel


class Uuid(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<uuid>{self.value}</uuid>'


class Name(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<name>{self.value}</name>'


class Memory(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<memory>{self.value}</memory>'


class Page(BaseModel):
    size: str
    nodeset: str
    unit: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<page size="{self.size}" nodeset="{self.nodeset}" unit="{self.unit}" />'


class HugePages(BaseModel):
    page: Page

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<hugepages>'
        end_tag = f'{spaces}</hugepages>'

        child_xml = self.page.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml}\n{end_tag}'


class MemoryBacking(BaseModel):
    huge_pages: HugePages

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<memoryBacking>'
        end_tag = f'{spaces}</memoryBacking>'
        child_xml = self.huge_pages.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml}\n{end_tag}'


class MemNode(BaseModel):
    cell_id: str
    mode: str
    proportion: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<memnode cellid="{self.cell_id}" mode="{self.mode}" proportion="{self.proportion}" />'


class NumaTune(BaseModel):
    mem_node: MemNode

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<numatune>'
        end_tag = f'{spaces}</numatune>'
        child_xml = self.mem_node.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml}\n{end_tag}'


class Vcpu(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<vcpu>{self.value}</vcpu>'


class Type(BaseModel):
    arch: str
    machine: str
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<type arch="{self.arch}" machine="{self.machine}">{self.value}</type>'


class Loader(BaseModel):
    readonly: str
    type: str
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<loader readonly="{self.readonly}" type="{self.type}">{self.value}</loader>'


class Boot(BaseModel):
    dev: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<boot dev="{self.dev}" />'


class OS(BaseModel):
    type: Type
    loader: Loader
    boot: Boot

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<os>'
        end_tag = f'{spaces}</os>'
        child_xml_type = self.type.to_xml(indent + 4)
        child_xml_loader = self.loader.to_xml(indent + 4)
        child_xml_boot = self.boot.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_type}\n{child_xml_loader}\n{child_xml_boot}\n{end_tag}'


class Acpi(BaseModel):
    @staticmethod
    def to_xml(indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<acpi />'


class Gic(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<gic version="{self.value}" />'


class Features(BaseModel):
    acpi: Acpi
    gic: Gic

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<features>'
        end_tag = f'{spaces}</features>'
        child_xml_acpi = self.acpi.to_xml(indent + 4)
        child_xml_gic = self.gic.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_acpi}\n{child_xml_gic}\n{end_tag}'


class Topology(BaseModel):
    sockets: str
    cores: str
    threads: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<topology sockets="{self.sockets}" cores="{self.cores}" threads="{self.threads}" />'


class Cell(BaseModel):
    id: str
    cpus: str
    memory: str
    mem_access: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return (f'{spaces}<cell id="{self.id}" cpus="{self.cpus}" memory="{self.memory}" '
                f'memAccess="{self.mem_access}" />')


class Numa(BaseModel):
    cell: Cell

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<numa>'
        end_tag = f'{spaces}</numa>'
        child_xml = self.cell.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml}\n{end_tag}'


class Cpu(BaseModel):
    mode: str
    match: str
    topology: Topology
    numa: Numa

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<cpu mode="{self.mode}" match="{self.match}">'
        end_tag = f'{spaces}</cpu>'
        child_xml_topology = self.topology.to_xml(indent + 4)
        child_xml_numa = self.numa.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_topology}\n{child_xml_numa}\n{end_tag}'


class Clock(BaseModel):
    offset: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<clock offset="{self.offset}">'
        end_tag = f'{spaces}</clock>'
        return f'{start_tag}\n{end_tag}'


class OnPowerOff(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<on_poweroff>{self.value}</on_poweroff>'


class OnReboot(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<on_reboot>{self.value}</on_reboot>'


class OnCrash(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<on_crash>{self.value}</on_crash>'


class ControllerAlias(BaseModel):
    name: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<alias name="{self.name}" />'


class ControllerAddress(BaseModel):
    type: str
    domain: str
    bus: str
    slot: str
    function: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return (f'{spaces}<address type="{self.type}" domain="{self.domain}" '
                f'bus="{self.bus}" slot="{self.slot}" function="{self.function}" />')


class Controller(BaseModel):
    type: str
    index: str
    model: str
    alias: ControllerAlias
    address: ControllerAddress

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<controller type="{self.type}" index="{self.index}" model="{self.model}">'
        end_tag = f'{spaces}</controller>'
        child_xml_alias = self.alias.to_xml(indent + 4)
        child_xml_address = self.address.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_alias}\n{child_xml_address}\n{end_tag}'


class Emulator(BaseModel):
    value: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<emulator>{self.value}</emulator>'


class Driver(BaseModel):
    name: str
    type: str
    cache: str
    io: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<driver name="{self.name}" type="{self.type}" cache="{self.cache}" io="{self.io}" />'


class DiskSource(BaseModel):
    file: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<source file="{self.file}" />'


class DiskTarget(BaseModel):
    dev: str
    bus: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<target dev="{self.dev}" bus="{self.bus}" />'


class DiskAddress(BaseModel):
    type: str
    controller: str
    bus: str
    target: str
    unit: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return (f'{spaces}<address type="{self.type}" controller="{self.controller}" '
                f'bus="{self.bus}" target="{self.target}" unit="{self.unit}" />')


class Disk(BaseModel):
    type: str
    device: str
    driver: Driver
    source: DiskSource
    target: DiskTarget
    address: DiskAddress

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<disk type="{self.type}" device="{self.device}">'
        end_tag = f'{spaces}</disk>'
        child_xml_driver = self.driver.to_xml(indent + 4)
        child_xml_source = self.source.to_xml(indent + 4)
        child_xml_target = self.target.to_xml(indent + 4)
        child_xml_address = self.address.to_xml(indent + 4)
        return (f'{start_tag}\n{child_xml_driver}\n{child_xml_source}\n'
                f'{child_xml_target}\n{child_xml_address}\n{end_tag}')


class Console(BaseModel):
    type: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<console type="{self.type}" />'


class ChannelSource(BaseModel):
    mode: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<source mode="{self.mode}" />'


class ChannelTarget(BaseModel):
    type: str
    name: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<target type="{self.type}" name="{self.name}" />'


class Channel(BaseModel):
    type: str
    source: ChannelSource
    target: ChannelTarget

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<channel type="{self.type}">'
        end_tag = f'{spaces}</channel>'
        child_xml_source = self.source.to_xml(indent + 4)
        child_xml_target = self.target.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_source}\n{child_xml_target}\n{end_tag}'


class Stats(BaseModel):
    period: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<stats period="{self.period}" />'


class MemBalloonAlias(BaseModel):
    name: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return f'{spaces}<alias name="{self.name}" />'


class MemBalloonAddress(BaseModel):
    type: str
    domain: str
    bus: str
    slot: str
    function: str

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        return (f'{spaces}<address type="{self.type}" domain="{self.domain}" '
                f'bus="{self.bus}" slot="{self.slot}" function="{self.function}" />')


class MemBalloon(BaseModel):
    model: str
    free_page_reporting: str
    stats: Stats
    alias: MemBalloonAlias
    address: MemBalloonAddress

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<memballoon model="{self.model}" freePageReporting="{self.free_page_reporting}">'
        end_tag = f'{spaces}</memballoon>'
        child_xml_stats = self.stats.to_xml(indent + 4)
        child_xml_alias = self.alias.to_xml(indent + 4)
        child_xml_address = self.address.to_xml(indent + 4)
        return f'{start_tag}\n{child_xml_stats}\n{child_xml_alias}\n{child_xml_address}\n{end_tag}'


class Devices(BaseModel):
    controller: Controller
    emulator: Emulator
    disk: Disk
    console: Console
    channel: Channel
    mem_balloon: MemBalloon

    def to_xml(self, indent: int) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<devices>'
        end_tag = f'{spaces}</devices>'
        child_xml_controller = self.controller.to_xml(indent + 4)
        child_xml_emulator = self.emulator.to_xml(indent + 4)
        child_xml_disk = self.disk.to_xml(indent + 4)
        child_xml_console = self.console.to_xml(indent + 4)
        child_xml_channel = self.channel.to_xml(indent + 4)
        child_xml_mem_balloon = self.mem_balloon.to_xml(indent + 4)
        return (f'{start_tag}\n{child_xml_controller}\n{child_xml_emulator}\n{child_xml_disk}\n'
                f'{child_xml_console}\n{child_xml_channel}\n{child_xml_mem_balloon}\n{end_tag}')


class Domain(BaseModel):
    domain_type: str
    uuid: Uuid
    name: Name
    memory: Memory
    memory_backing: MemoryBacking
    numa_tune: NumaTune
    vcpu: Vcpu
    os: OS
    features: Features
    cpu: Cpu
    clock: Clock
    on_power_off: OnPowerOff
    on_reboot: OnReboot
    on_crash: OnCrash
    devices: Devices

    def to_xml(self, indent: int = 0) -> str:
        spaces = ' ' * indent
        start_tag = f'{spaces}<domain type="{self.domain_type}">'
        end_tag = f'{spaces}</domain>'

        children_xml = [
            self.uuid.to_xml(indent + 4),
            self.name.to_xml(indent + 4),
            self.memory.to_xml(indent + 4),
            self.memory_backing.to_xml(indent + 4),
            self.numa_tune.to_xml(indent + 4),
            self.vcpu.to_xml(indent + 4),
            self.os.to_xml(indent + 4),
            self.features.to_xml(indent + 4),
            self.cpu.to_xml(indent + 4),
            self.clock.to_xml(indent + 4),
            self.on_power_off.to_xml(indent + 4),
            self.on_reboot.to_xml(indent + 4),
            self.on_crash.to_xml(indent + 4),
            self.devices.to_xml(indent + 4),
        ]
        return f'{start_tag}\n' + '\n'.join(children_xml) + f'\n{end_tag}'
