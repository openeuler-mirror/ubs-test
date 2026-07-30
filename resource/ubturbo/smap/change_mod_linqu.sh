#!/bin/bash

SMAP_RESOURCE_HOME=/ko/smap/resources
SMAP_CASE_WORKSPACE=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)

function __cp_resource()
{
    mkdir -p $2 && cp -rf $1 $2
}

function __prepare_dependencies()
{
    mkdir -p ${SMAP_RESOURCE_HOME}
    vm_image_name=openEuler-24.03-LTS-SP4-aarch64.qcow2
    if [ ! -f "${SMAP_RESOURCE_HOME}/${vm_image_name}" ]
    then
      scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@controller:/opt/install/tmp/openstack/images/${vm_image_name} ${SMAP_RESOURCE_HOME}
    fi
    virsh list --name | xargs -i virsh destroy {}
    __cp_resource ${SMAP_RESOURCE_HOME}/${vm_image_name} ${SMAP_CASE_WORKSPACE}/vm/img
    cp -rf ${SMAP_CASE_WORKSPACE}/vm/img/${vm_image_name} ${SMAP_CASE_WORKSPACE}/vm/img/openEuler-24.03-LTS-SP4-aarch64-1.qcow2
    sed -i "s@__SMAP_CASE_RESOURCE_ROOT__@${SMAP_CASE_WORKSPACE}/vm/img@g" ${SMAP_CASE_WORKSPACE}/vm/xml/smap-vm-1.xml

    __cp_resource ${SMAP_RESOURCE_HOME}/redis-server ${SMAP_CASE_WORKSPACE}/redis
    __cp_resource ${SMAP_RESOURCE_HOME}/redis-benchmark ${SMAP_CASE_WORKSPACE}/redis
    __cp_resource ${SMAP_RESOURCE_HOME}/redis.conf ${SMAP_CASE_WORKSPACE}/redis
    chmod u+x ${SMAP_CASE_WORKSPACE}/redis/redis-*

    yum -y install docker
    systemctl start docker
    systemctl enable docker
    docker load -i ${SMAP_RESOURCE_HOME}/openEuler-docker.aarch64.tar.xz
    __cp_resource ${SMAP_RESOURCE_HOME}/util-linux-*.rpm ${SMAP_CASE_WORKSPACE}/container/packages
}

function __build_smap_client()
{
    if [ -f "${SMAP_CASE_WORKSPACE}/bin/smap_client" ]
    then
      echo "check client exist[ok]"
      return
    fi
    yum -y install cmake
    bash ${SMAP_CASE_WORKSPACE}/client/build.sh
    mkdir -p ${SMAP_CASE_WORKSPACE}/bin/
    cp ${SMAP_CASE_WORKSPACE}/client/output/bin/smap_client_nc ${SMAP_CASE_WORKSPACE}/bin/smap_client
}

function __stop_smap_process()
{
    pkill -9 smap_client
    systemctl stop ubturbo
    rm -rf /dev/shm/smap_config
    rm -rf /dev/shm/ubturbo_page_type.dat

    rmmod -f smap_tiering
    rmmod -f smap_access_tracking
    rmmod -f smap_histogram_tracking
    rmmod -f smap_tracking_core
}

function __prepare_remote_numa()
{
    local link_ids=($(sudo -u ubse ubsectl display topo -t cpu | grep -oP '^[\ ]*[^\ ]+' | grep '/' | grep '-'))

    for ((i=0; i<$((${#link_ids[@]})); i++))
    do
        if [ "$(sudo -u ubse ubsectl display memory -t borrow_detail | grep -oP smap-test-$((i+1)) | wc -l)" -gt "0" ]
        then
          continue
        fi
        sudo -u ubse ubsectl create memory -t numa -l ${link_ids[i]} -s 8G -n smap-test-$((i+1))
    done
}

function mod_4k
{
    __prepare_dependencies
    __build_smap_client
    __stop_smap_process
    __prepare_remote_numa

    smap_ko_path="/lib/modules/smap"
    insmod ${smap_ko_path}/smap_tracking_core.ko
    insmod ${smap_ko_path}/smap_histogram_tracking.ko
    insmod ${smap_ko_path}/smap_access_tracking.ko smap_scene=2 enable_hist=0
    insmod ${smap_ko_path}/smap_tiering.ko smap_mode=2 smap_pgsize=0 smap_scene=2

    local numa_nodes=($(lscpu | grep -oP 'NUMA\s+node(\d+)\s+CPU\(s\):.*$' | grep -oP 'node\d+'))
    for node in ${numa_nodes[@]}
    do
      echo 0 > /sys/devices/system/node/${node}/hugepages/hugepages-2048kB/nr_hugepages
    done

    chmod u+x ${SMAP_CASE_WORKSPACE}/bin/smap_client
    ${SMAP_CASE_WORKSPACE}/bin/smap_client >> ${SMAP_CASE_WORKSPACE}/bin/smap_client.log 2>&1 & disown

    docker ps -a | grep -oP 'smap.*' | xargs -i docker rm -f {}
    docker_image_id=$(docker images | grep euler | awk '{print $3}')

    if [ -z "${docker_image_id}" ]
    then
      echo "docker image not found"
      reurn
    fi
    docker run -itd \
      --name smap-container-1 \
      --hostname smap-container-1 \
      --volume ${SMAP_CASE_WORKSPACE}:${SMAP_CASE_WORKSPACE} \
      -itd --privileged \
      --cpus=4 -m 8192m \
      "$docker_image_id" bash

    docker run -itd \
      --name smap-container-2 \
      --hostname smap-container-2 \
      --volume ${SMAP_CASE_WORKSPACE}:${SMAP_CASE_WORKSPACE} \
      -itd --privileged \
      --cpus=4 -m 8192m \
      "$docker_image_id" bash

    docker exec smap-container-1 bash -c "rpm -ivh --nodeps ${SMAP_CASE_WORKSPACE}/container/packages/util-linux-*.rpm > /dev/null 2>&1 || true"
    docker exec smap-container-2 bash -c "rpm -ivh --nodeps ${SMAP_CASE_WORKSPACE}/container/packages/util-linux-*.rpm > /dev/null 2>&1 || true"

}

function mod_2m()
{
    __prepare_dependencies
    __build_smap_client
    __stop_smap_process
    __prepare_remote_numa

    smap_ko_path="/lib/modules/smap"
    insmod ${smap_ko_path}/smap_tracking_core.ko
    insmod ${smap_ko_path}/smap_histogram_tracking.ko
    insmod ${smap_ko_path}/smap_access_tracking.ko smap_scene=2 enable_hist=0
    insmod ${smap_ko_path}/smap_tiering.ko smap_scene=2


    local numa_nodes=($(lscpu | grep -oP 'NUMA\s+node(\d+)\s+CPU\(s\):.*$' | grep -oP 'node\d+'))
    for node in ${numa_nodes[@]}
    do
      echo 8500 > /sys/devices/system/node/${node}/hugepages/hugepages-2048kB/nr_hugepages
    done

    chmod u+x ${SMAP_CASE_WORKSPACE}/bin/smap_client
    ${SMAP_CASE_WORKSPACE}/bin/smap_client >> ${SMAP_CASE_WORKSPACE}/bin/smap_client.log 2>&1 & disown

    virsh list --name | xargs -i virsh destroy {}
    virsh create ${SMAP_CASE_WORKSPACE}/vm/xml/smap-vm-1.xml

}


if [ "$1" == '4k' ]
then
  mod_4k
else
  mod_2m
fi