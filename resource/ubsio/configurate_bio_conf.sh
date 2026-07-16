#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  configurate_bio_conf.sh [选项]

选项:
  --conf-file PATH                         配置文件路径，默认 /etc/boostio/bio.conf
  --disk-path PATH                         bio.disk.path，默认 /dev/nvme2n1
  --mem-size-in-gb N                       bio.mem.size_in_gb，默认 50
  --wcache-evict-water-level N             bio.wcache.evict_water_level，默认 0
  --wcache-disk-evict-water-level N        bio.wcache.disk_evict_water_level，默认 90
  --standalone-device-count N              bio.standalone.device_count，默认 0
  --bdm-io-engine ENGINE                   bio.bdm.io_engine，可选 sync、io_uring，默认 sync
  --bdm-batch-read-window-keys N           bio.bdm.batch_read.window_keys，默认 128
  --bdm-batch-read-window-bytes-mb N       bio.bdm.batch_read.window_bytes_mb，默认 256
  --bdm-batch-read-pipeline-depth N        bio.bdm.batch_read.pipeline_depth，默认 4
  --log-level LEVEL                        bio.log.level，可选 error、warn、info、debug、trace，默认 debug
  -h, --help                               显示帮助

示例:
  configurate_bio_conf.sh --conf-file ./bio.conf --disk-path /data/bio --mem-size-in-gb 50 --standalone-device-count 4 --bdm-io-engine io_uring
USAGE
}

require_value() {
  local option="$1"

  if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
    echo "${option} 需要指定值" >&2
    exit 1
  fi

  printf '%s' "$2"
}

CONF_FILE="/etc/boostio/bio.conf"
BIO_DISK_PATH="/dev/nvme2n1"
BIO_MEM_SIZE_IN_GB="50"
BIO_WCACHE_EVICT_WATER_LEVEL="0"
BIO_WCACHE_DISK_EVICT_WATER_LEVEL="90"
BIO_STANDALONE_DEVICE_COUNT="0"
BIO_BDM_IO_ENGINE="sync"
BIO_BDM_BATCH_READ_WINDOW_KEYS="128"
BIO_BDM_BATCH_READ_WINDOW_BYTES_MB="256"
BIO_BDM_BATCH_READ_PIPELINE_DEPTH="4"
BIO_LOG_LEVEL="debug"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --conf-file)
      CONF_FILE="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --conf-file=*)
      CONF_FILE="${1#*=}"
      shift
      ;;
    --disk-path)
      BIO_DISK_PATH="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --disk-path=*)
      BIO_DISK_PATH="${1#*=}"
      shift
      ;;
    --mem-size-in-gb)
      BIO_MEM_SIZE_IN_GB="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --mem-size-in-gb=*)
      BIO_MEM_SIZE_IN_GB="${1#*=}"
      shift
      ;;
    --wcache-evict-water-level)
      BIO_WCACHE_EVICT_WATER_LEVEL="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --wcache-evict-water-level=*)
      BIO_WCACHE_EVICT_WATER_LEVEL="${1#*=}"
      shift
      ;;
    --wcache-disk-evict-water-level)
      BIO_WCACHE_DISK_EVICT_WATER_LEVEL="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --wcache-disk-evict-water-level=*)
      BIO_WCACHE_DISK_EVICT_WATER_LEVEL="${1#*=}"
      shift
      ;;
    --standalone-device-count)
      BIO_STANDALONE_DEVICE_COUNT="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --standalone-device-count=*)
      BIO_STANDALONE_DEVICE_COUNT="${1#*=}"
      shift
      ;;
    --bdm-io-engine)
      BIO_BDM_IO_ENGINE="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --bdm-io-engine=*)
      BIO_BDM_IO_ENGINE="${1#*=}"
      shift
      ;;
    --bdm-batch-read-window-keys)
      BIO_BDM_BATCH_READ_WINDOW_KEYS="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --bdm-batch-read-window-keys=*)
      BIO_BDM_BATCH_READ_WINDOW_KEYS="${1#*=}"
      shift
      ;;
    --bdm-batch-read-window-bytes-mb)
      BIO_BDM_BATCH_READ_WINDOW_BYTES_MB="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --bdm-batch-read-window-bytes-mb=*)
      BIO_BDM_BATCH_READ_WINDOW_BYTES_MB="${1#*=}"
      shift
      ;;
    --bdm-batch-read-pipeline-depth)
      BIO_BDM_BATCH_READ_PIPELINE_DEPTH="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --bdm-batch-read-pipeline-depth=*)
      BIO_BDM_BATCH_READ_PIPELINE_DEPTH="${1#*=}"
      shift
      ;;
    --log-level)
      BIO_LOG_LEVEL="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --log-level=*)
      BIO_LOG_LEVEL="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$CONF_FILE" ]]; then
  echo "配置文件不存在: $CONF_FILE" >&2
  exit 1
fi

case "$BIO_BDM_IO_ENGINE" in
  sync|io_uring) ;;
  *)
    echo "--bdm-io-engine 只能是 sync、io_uring" >&2
    exit 1
    ;;
esac

case "$BIO_LOG_LEVEL" in
  error|warn|info|debug|trace) ;;
  *)
    echo "--log-level 只能是 error、warn、info、debug、trace" >&2
    exit 1
    ;;
esac

backup_file="${CONF_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$CONF_FILE" "$backup_file"

set_conf() {
  local key="$1"
  local value="$2"

  if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$CONF_FILE"; then
    sed -i -E "s|^[[:space:]]*(${key})[[:space:]]*=.*|\\1 = ${value}|" "$CONF_FILE"
  else
    printf '%s = %s\n' "$key" "$value" >> "$CONF_FILE"
  fi
}

set_conf "bio.disk.path" "$BIO_DISK_PATH"
set_conf "bio.mem.size_in_gb" "$BIO_MEM_SIZE_IN_GB"
set_conf "bio.wcache.evict_water_level" "$BIO_WCACHE_EVICT_WATER_LEVEL"
set_conf "bio.wcache.disk_evict_water_level" "$BIO_WCACHE_DISK_EVICT_WATER_LEVEL"
set_conf "bio.standalone.device_count" "$BIO_STANDALONE_DEVICE_COUNT"
set_conf "bio.bdm.io_engine" "$BIO_BDM_IO_ENGINE"
set_conf "bio.bdm.batch_read.window_keys" "$BIO_BDM_BATCH_READ_WINDOW_KEYS"
set_conf "bio.bdm.batch_read.window_bytes_mb" "$BIO_BDM_BATCH_READ_WINDOW_BYTES_MB"
set_conf "bio.bdm.batch_read.pipeline_depth" "$BIO_BDM_BATCH_READ_PIPELINE_DEPTH"
set_conf "bio.log.level" "$BIO_LOG_LEVEL"

echo "已修改: $CONF_FILE"
echo "备份文件: $backup_file"
