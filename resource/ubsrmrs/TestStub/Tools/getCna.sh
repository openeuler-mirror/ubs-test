#!/bin/bash

# -------- 参数处理 --------
if [[ -z "$1" ]]; then
    echo "Usage: $0 <target_numaid>"
    exit 1
fi

target="$1"
base="/sys/devices/obmm"

found=0

# -------- 遍历 dev_x 目录 --------
for d in "$base"/obmm_*; do
    num_file="$d/import_info/numa_id"
    src_file="$d/import_info/scna"
    dest_file="$d/import_info/dcna"

    # 检查 info 文件是否存在
    if [[ ! -f "$num_file" ]]; then
        continue
    fi

    # 读 numaid 值（去掉空格换行）
    num=$(tr -d ' \n\r\t' < "$num_file")

    if [[ "$num" == "$target" ]]; then
        # 确保 srcid 和 destid 存在
        if [[ ! -f "$src_file" ]] || [[ ! -f "$dest_file" ]]; then
            echo "Found matching dev ($d) but srcid/destid file missing!"
            exit 1
        fi

        src=$(tr -d ' \n\r\t' < "$src_file")
        dest=$(tr -d ' \n\r\t' < "$dest_file")

        echo "{"
        echo "    \"scna\": $((src)),"
        echo "    \"dcna\": $((dest)),"
        echo "    \"dev_path\": \"$d\""
        echo "}"
        # echo "Found in $d: scna=$src dcna=$dest"
        found=1
        break
    fi
done

# -------- 未找到的情况 --------
if [[ "$found" -eq 0 ]]; then
    echo "No dev_x found with numaid=$target"
    exit 1
fi
