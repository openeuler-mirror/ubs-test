#!/bin/bash

TOTAL=1024

COMMAND_ARRAY=(python3 /home/mempooling-test/sdk/call_virt.py call_borrow_execute '{"srcParam": {"srcNid":"1","srcSocketId":0,"srcNumaId":0}, "borrowSize": 104857600, "destParam":[{"destNid":"2","destSocketId":0,"destNumaNum":1,"destNumaId":[0],"memSize":[262144]}]}')

OUTPUT_FILE='/home/mempooling-test/borrow_result'

for i in $(seq 1 $TOTAL);do
  echo -n "第 $i 次执行：$(date '+%Y-%m-%d %H:%M:%S')"
  start_time=$(date +%s)

  #执行命令
  "${COMMAND_ARRAY[@]}" >> "$OUTPUT_FILE"
  end_time=$(date +%s)
  duration=$(echo "$end_time - $start_time" | bc)
  echo "耗时: ${duration}秒"
  sleep 1
done
