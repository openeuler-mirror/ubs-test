#!/bin/bash

# 停止服务
rm -rf /var/lib/ubse/psk/psk.txt
ll /var/lib/ubse/psk/psk.txt
systemctl stop ubse
rm -rf /var/lib/ubse/psk/psk.txt
ll /var/lib/ubse/psk/psk.txt
rm -rf /var/lib/ubse/data/* /var/lib/ubse/sync/*
ll /var/lib/ubse/*
export HCOM_CONNECTION_RETRY_TIMES=1
echo "Cleanup completed successfully."