#!/bin/bash

# 停止服务
systemctl stop ubse
rm -rf /var/lib/ubse/data/* /var/lib/ubse/sync/* /var/lib/ubse/psk/psk.txt
ll /var/lib/ubse/*
export HCOM_CONNECTION_RETRY_TIMES=1
systemctl restart ubturbo
systemctl start ubse
echo "Cleanup completed successfully."