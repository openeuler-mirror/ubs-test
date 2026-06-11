#!/bin/bash

# 输入参数分别为主节点ip、从节点ip
ip=$(hostname -I | awk '{print $1}')
master_ip=$1
slave_ip=$2

mkdir -p /home/mempooling-test/{img,log,xml,pi8}

if [ -f /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2 ]; then
    for i in {1,2,3}; do
        cp /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/img/vm_redis_$i.qcow2
    done
    cp /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64-A.qcow2
    cp /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64-B.qcow2
    cp /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64-C.qcow2
fi

if [[ "$ip" == "$master_ip" ]]; then
    if [ -f /home/mempooling-test/pi8/openEuler-22.03-LTS-SP1-aarch64.qcow2 ]; then
        for i in {1,2,3,4,9,10}; do
            cp /home/mempooling-test/pi8/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/pi8/vm_redis_$i.qcow2
        done
    fi
elif [[ "$ip" == "$slave_ip" ]]; then
    if [ -f /home/mempooling-test/pi8/openEuler-22.03-LTS-SP1-aarch64.qcow2 ]; then
        for i in {5,6,7,8}; do
            cp /home/mempooling-test/pi8/openEuler-22.03-LTS-SP1-aarch64.qcow2 /home/mempooling-test/pi8/vm_redis_$i.qcow2
        done
    fi
fi

