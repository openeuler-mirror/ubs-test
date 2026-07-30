#!/bin/bash

# -------- 参数处理 --------
if [[ -z "$1" ]]; then
    echo "Usage: $0 <target_numaid>"
    exit 1
fi

target="$1"
base="/sys/devices/obmm"

# eid格式:
# 0x0:0x4000a -> 262154
eid_to_dec()
{
    local eid="$1"

    local high="${eid%%:*}"
    local low="${eid##*:}"

    echo $(( (high << 32) + low ))
}

found=0

# -------- 遍历 obmm_* 目录 --------
for d in "$base"/obmm_*; do
    num_file="$d/import_info/numa_id"
    src_file="$d/import_info/seid"
    dest_file="$d/import_info/deid"

    [[ -f "$num_file" ]] || continue

    num=$(tr -d ' \n\r\t' < "$num_file")

    if [[ "$num" == "$target" ]]; then

        if [[ ! -f "$src_file" ]] || [[ ! -f "$dest_file" ]]; then
            echo "Found matching dev ($d) but seid/deid file missing!"
            exit 1
        fi

        src=$(tr -d ' \n\r\t' < "$src_file")
        dest=$(tr -d ' \n\r\t' < "$dest_file")

        src_dec=$(eid_to_dec "$src")
        dest_dec=$(eid_to_dec "$dest")

        echo "{"
        echo "    \"seid\": ${src_dec},"
        echo "    \"deid\": ${dest_dec},"
        echo "    \"dev_path\": \"$d\""
        echo "}"

        found=1
        break
    fi
done

# -------- 未找到 --------
if [[ "$found" -eq 0 ]]; then
    echo "No dev found with numaid=$target"
    exit 1
fi