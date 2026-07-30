#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <dirent.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/time.h>
#include <string.h>
#include <limits.h>
#include <time.h>
#include <sys/file.h>
#include "cli.h"
#include "smap_interface.h"
#include "smap_inner_interface.h"
#include "smap_client_diagnose.h"

#ifndef ARRAY_LEN
#define ARRAY_LEN(x) (sizeof(x) / sizeof((x)[0]))
#endif

#define MIN_CMD_NUM 2
#define DECIMAL_PREFIX 10
#define HEX_PREFIX 16
#define ERROR_SIZE 128
#define MIG_OUT_RATIO_ARGC 4
#define MIG_OUT_MEMSIZE_ARGC 6
#define PAIR_OF_DESTNID_PID_RATIO 3
#define PAIR_OF_DESTNID_PID_MEMSIZE 5
#define MIG_BACK_ARGC 4
#define MIG_BACK_MEMID_ARGC 3
#define SMAP_ENABLE_ARGC 2
#define SMAP_ENABLE_MIG_INFO_ARGC 1
#define SMAP_ENABLE_ADAPT_MEM_ARGC 1
#define SMAP_QUERY_ADAPT_MEM_ARGC 1
#define SMAP_NOTIFY_BORROW_MEM_ARGC 3
#define SMAP_QUERY_VM_FREQ_ARGC 3
#define SMAP_QUERY_VM_FREQ_MAX_ARGC 6
#define SMAP_QUERY_VM_FREQ_STATISTIC_MAX_ARGC 7
#define SMAP_SET_RUN_MODE_ARGC 1
#define SMAP_ENABLE_PROCESS_MIGRATE_ARGC 3
#define SMAP_MIGRATE_REMOTE_NUMA_ARGC 3
#define SMAP_ADD_PROCESS_TRACKING_ARGC 2
#define SMAP_ADD_PROCESS_TRACKING_STATISTIC_ARGC 3
#define SMAP_ADD_PROCESS_TRACKING_STABLE_ARGC 2
#define SMAP_REMOVE_PROCESS_TRACKING_ARGC 3
#define SMAP_SET_LOG_LEVEL_ARGC 1
#define SMAP_MIG_OUT_SYNC_ARGC 5
#define MIG_OUT_SYNC_ARGC 2
#define SMAP_MIGRATE_PID_REMOTE_NUMA_ARGC 5
#define SMAP_QUERY_PROCESS_CONFIG_ARGC 4
#define SMAP_QUERY_FREQ_INFO_ARGC 1

#define US_PER_SEC 1000000
#define KIB (1ULL << 10)
#define MIB (1ULL << 20)

#define STR_NULL "NULL"
#define STRLEN_NULL 4
#define STR_EMPTY "empty"
#define STRLEN_EMPTY 5
#define STR_INVALID "invalid"
#define STRLEN_INVALID 7

#define MAX_PATH_LEN 1024
#define MAX_LINE_LEN 256
#define MAX_PID_NAME 40

#define LOCAL_NUMA_NUM 4
#define OBMM_SYS_DIR "/sys/devices/obmm"
#define OBMM_SHM_DIR "obmm_shmdev"
#define NODE_PATH "/dev/smap_node%d"
#define SYS_NODE_PATH "/sys/devices/system/node"
#define DECIMAL 10

typedef enum {
    CMD_SMAP_INII,
    CMD_SMAP_MIG_OUT,
    CMD_SMAP_MIG_OUT_MEMSIZE,
    CMD_SMAP_MIG_BACK,
    CMD_SMAP_REMOVE,
    CMD_SMAP_REMOVE_MULTINUMA,
    CMD_SMAP_ENABLE,
    CMD_SMAP_URGENT,
    CMD_SMAP_STOP,
    CMD_SMAP_ENABLE_MIG_INFO,
    CMD_SMAP_ENABLE_ADAPT_MEM,
    CMD_SMAP_QUERY_ADAPT_MEM,
    CMD_SMAP_GET_BORROW_MEM,
    CMD_SMAP_QUERY_VM_FREQ,
    CMD_SMAP_QUERY_VM_FREQ_STATISTIC,
    CMD_SMAP_SET_RUN_MODE,
    CMD_SMAP_ADD_PROCESS_TRACKING,
    CMD_SMAP_ADD_PROCESS_STATISTIC_TRACKING,
    CMD_SMAP_REMOVE_PROCESS_TRACKING,
    CMD_SMAP_ENABLE_PROCESS_MIGRATE_MODE,
    CMD_SMAP_MIGRATE_REMOTE_NUMA_MODE,
    CMD_SMAP_SET_LOG_LEVEL,
    CMD_SMAP_MIGRATE_PID_REMOTE_NUMA_MODE,
    CMD_SMAP_QUERY_PROCESS_CONFIG,
    CMD_SMAP_QUERY_NUMA_FREQ,
    CMD_SMAP_MIG_OUT_MULTI_NUMA,
    CMD_COUNT
} SmapClientCmdIndex;

typedef struct {
    unsigned long long hpa;
    unsigned short freq;
} FreqInfo;

typedef struct {
    const char *input;
    uint32_t pageSize;
} PageSizeMapping;

static const PageSizeMapping pageSizeMapping[] = {
    { "4", 4 * KIB },
    { "2048", 2 * MIB }
};
int32_t IsHexPrefix(const char *str)
{
    if (str == NULL) {
        CLI_PrintBuf("str is null.\n");
        return -1;
    }
    return ((str[0] == '0') && ((str[1] == 'x') || (str[1] == 'X')));
}

static int StrToU64(const char *pStr, uint64_t *pOut)
{
    char *pscEnd = NULL;
    char err[ERROR_SIZE] = {0};

    if (pStr == NULL) {
        return 0;
    }

    // 判断是否为16进制前缀
    if (IsHexPrefix(pStr)) {
        *pOut = strtoull(pStr, &pscEnd, HEX_PREFIX); // 16进制转换
    } else if (pStr[0] == '-') {
        *pOut = strtoll(pStr, &pscEnd, DECIMAL_PREFIX); // 10进制int转换
    } else {
        *pOut = strtoull(pStr, &pscEnd, DECIMAL_PREFIX); // 10进制uint转换
    }

    if (*pscEnd != '\0') {
        CLI_PrintBuf("strtouint64_t fail: unprocessed characters after '%s'\n", pscEnd);
        return EINVAL;
    }
    return 0;
}

struct SmapClientDiagnoseCmd {
    char *name;
    void (*func)(int32_t argc, char *argv[]);
    char *description;
};

static void SmapMigrateOutCall(int32_t argc, char *argv[]);
static void SmapMigrateBackCall(int32_t argc, char *argv[]);
static void SmapMigrateBackMemidCall(int32_t argc, char *argv[]);
static void SmapRemoveCall(int32_t argc, char *argv[]);
static void SmapRemoveMultiNumaCall(int32_t argc, char *argv[]);
static void SmapEnableNodeCall(int32_t argc, char *argv[]);
static void SmapInitTest(int32_t argc, char *argv[]);
static void SmapUrgentMigrateOutTest(int32_t argc, char *argv[]);
static void SmapEnableAdaptMemCall(int32_t argc, char *argv[]);
static void SmapQueryVmMemCall(int32_t argc, char *argv[]);
static void SmapQueryVmFreqCall(int32_t argc, char *argv[]);
static void SmapStopTest(int32_t argc, char *argv[]);
static void SetSmapRemoteNumaInfoCall(int32_t argc, char *argv[]);
static void SetSmapRunModeCall(int32_t argc, char *argv[]);
static void SmapAddProcessTrackingCall(int32_t argc, char *argv[]);
static void SmapAddProcessTrackingStatisticCall(int32_t argc, char *argv[]);
static void SmapRemoveProcessTrackingCall(int32_t argc, char *argv[]);
static void SmapEnableProcessMigrateCall(int32_t argc, char *argv[]);
static void SmapMigrateRemoteNumaCall(int32_t argc, char *argv[]);
static void SmapMigrateRemoteNumaMemidCall(int32_t argc, char *argv[]);
static void SmapMigrateOutSyncCall(int32_t argc, char *argv[]);
static void SmapMigratePidRemoteNumaCall(int32_t argc, char *argv[]);
static void SmapQueryProcessConfigCall(int32_t argc, char *argv[]);
static void SmapMigrateOutMemSizeCall(int32_t argc, char *argv[]);
static void SmapQueryVmFreqStatisticCall(int32_t argc, char *argv[]);
static void SmapQueryFreqInfoCall(int32_t argc, char *argv[]);
static void SmapQueryNumaFreqCall(int32_t argc, char *argv[]);
static void SmapMigrateOutMultiNumaCall(int32_t argc, char *argv[]);

struct SmapClientDiagnoseCmd g_smapClientDiagCmd[] = {
    { "smap_init", SmapInitTest, "smap smap_init [pageType]\n" },
    { "smap_mig_out", SmapMigrateOutCall, "smap smap_mig_out [dest_nid] [pid] [ratio] [pidType]\n" },
    { "smap_mig_out_memsize", SmapMigrateOutMemSizeCall, "smap smap_mig_out_memsize [dest_nid] [pid] [ratio] [memSize] [migMode] [pidType]\n" },
    { "smap_mig_back", SmapMigrateBackCall, "smap smap_mig_back [src_nid] [dst_nid] [paStart] [paEnd]\n" },
    { "smap_mig_back_memid", SmapMigrateBackMemidCall, "smap smap_mig_back_memid [src_nid] [dst_nid] [memid]\n" },
    { "smap_remove", SmapRemoveCall, "smap smap_remove [pid] [pidType]\n" },
    { "smap_remove_multinuma", SmapRemoveMultiNumaCall, "smap smap_remove_multinuma [pid] [nid1] [nid2] ... [pidType]\n" },
    { "smap_enable", SmapEnableNodeCall, "smap smap_enable [enable] [nid]\n" },
    { "smap_urgent_mig", SmapUrgentMigrateOutTest, "smap smap_urgent_mig [size]\n" },
    { "smap_stop", SmapStopTest, "smap smap_stop\n" },
    { "smap_enable_adapt_mem", SmapEnableAdaptMemCall, "smap smap_enable_adapt_mem [flag]\n" },
    { "smap_query_vms_mem", SmapQueryVmMemCall, "smap smap_query_vms_mem [flag]\n" },
    { "set_smap_remote_numa_info", SetSmapRemoteNumaInfoCall, "smap set_smap_remote_numa_info [src_nid] [dest_nid] [size]\n"},
    {
        "smap_query_vm_freq",
        SmapQueryVmFreqCall,
        "smap smap_query_vm_freq [pid] [flag] [length](max:65536) [no_print] [range_start] [range_end]\n"
    },
    {
        "smap_query_vm_freq_statistic",
        SmapQueryVmFreqStatisticCall,
        "smap smap_query_vm_freq_statistic [pid] [flag] [length] [no_print] [range_start] [range_end] [dataSource]\n"
    },
    { "set_smap_run_mode", SetSmapRunModeCall, "smap set_smap_run_mode [runMode]\n" },
    { "smap_add_process_tracking", SmapAddProcessTrackingCall, "smap smap_add_process_tracking [pid] [scan_time] [len] [flag]\n"},
    {
        "smap_add_process_statistic_tracking",
        SmapAddProcessTrackingStatisticCall,
        "smap smap_add_process_statistic_tracking [pid] [scan_time] [duration] [len] [flag]\n"
    },
    { "smap_remove_process_tracking", SmapRemoveProcessTrackingCall, "smap smap_remove_process_tracking [pid] [len] [flag]\n"},
    {
        "smap_enable_process_migrate",
        SmapEnableProcessMigrateCall,
        "smap smap_enable_process_migrate [enable] [flags] [len] [pid]\n"
    },
    {
        "smap_migrate_remote_numa",
        SmapMigrateRemoteNumaCall,
        "smap smap_migrate_remote_numa [src_nid] [dest_nid] [range_count] [pa_start]... [pa_end]...\n"
    },
    {
        "smap_migrate_remote_numa",
        SmapMigrateRemoteNumaMemidCall,
        "smap smap_migrate_remote_numa_memid [src_nid] [dest_nid] [range_count] [memid]... \n"
    },
    {
        "smap_mig_out_sync",
        SmapMigrateOutSyncCall,
        "smap smap_mig_out_sync [dest_nid] [pid] [ratio] [memSize] [migMode] [pidType] [waitTime]\n"
    },
    {
        "smap_migrate_pid_remote_numa",
        SmapMigratePidRemoteNumaCall,
        "smap smap_migrate_pid_remote_numa [count] [pid] [srcNid] [destNid] [ratio] [memSize] ...  [migMode]\n"
    },
    {
        "smap_query_process_config",
        SmapQueryProcessConfigCall,
        "smap smap_query_process_config [nid] [result] [inLen] [outLen]\n"
    },
    {
        "smap_query_freq_info",
        SmapQueryFreqInfoCall,
        "smap smap_query_freq_info [pid]\n"
    },
    {
        "smap_query_numa_freq",
        SmapQueryNumaFreqCall,
        "smap smap_query_numa_freq [length] [nid]..\n"
    },
    {
        "smap_mig_out_multi_numa",
        SmapMigrateOutMultiNumaCall,
        "smap smap_mig_out_multi_numa  [dest_nid] [ratio] [memsize] ... [pid] [migrate_mode] [pidType] [waitTime]\n"
    },
};

static void SmapClientDebugHelp(char *command, int detail)
{
    int32_t index;

    for (index = 0; index < ARRAY_LEN(g_smapClientDiagCmd); index++) {
        CLI_PrintBuf(g_smapClientDiagCmd[index].description);
    }
}

static void SmapClientDebugProcess(int argc, char *argv[])
{
    if (argc <= 1) {
        SmapClientDebugHelp(argv[0], 1);
        return;
    }

    char *cmdType = argv[1];
    uint32_t index;
    for (index = 0; index < ARRAY_LEN(g_smapClientDiagCmd); index++) {
        if (strcmp(g_smapClientDiagCmd[index].name, cmdType) == 0) {
            if (g_smapClientDiagCmd[index].func != NULL) {
                g_smapClientDiagCmd[index].func(argc - MIN_CMD_NUM, argv + MIN_CMD_NUM);
                return;
            }
        }
    }

    SmapClientDebugHelp(argv[0], 1);
}

int SmapDiagnoseInit()
{
    CLI_CMD_S command;
    strncpy(command.szCommand, "smap", CLI_MAX_COMMAND_LEN);
    strncpy(command.szDescription, "smap commands.", CLI_MAX_CMD_DESC_LEN);
    command.fnCmdDo = SmapClientDebugProcess;
    command.fnPrintCmdHelp = SmapClientDebugHelp;
    int result = CLI_RegCmd(&command);
    if (result != 0) {
        printf("Register sdk diagnose failed.\n");
        return -1;
    }
    return result;
}

static bool CheckArgumentNums(int argc, int expectedArgc, int cmdIndex)
{
    if (argc != expectedArgc) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[cmdIndex].description);
        return false;
    }
    return true;
}

int ConvertMultipleArgsToU64(char *argv[], uint64_t output[], size_t argCount)
{
    for (size_t i = 0; i < argCount; ++i) {
        int ret = StrToU64(argv[i], &output[i]);
        if (ret) {
            CLI_PrintBuf("Failed to convert parameter(%s).\n", argv[i]);
            return ret;
        }
    }
    return 0;
}

// 迁出命令调用函数，支持多个输入以及注入空指针
static void SmapMigrateOutCall(int32_t argc, char *argv[])
{
    if ((argc - 1) % PAIR_OF_DESTNID_PID_RATIO) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIG_OUT].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    enum {
        DEST_NODE,
        PID,
        RATIO,
        PID_TYPE,
    };

    int pidType = values[argc - 1];
    struct MigrateOutMsg migOutMsg = { 0 };
    struct MigrateOutMsg *msg;
    if (argc < MIG_OUT_RATIO_ARGC) { // 仅传入pagetype时，注入空指针
        msg = NULL;
    } else { // 支持批量输入
        migOutMsg.count = argc / PAIR_OF_DESTNID_PID_RATIO;
        if (migOutMsg.count > MAX_NR_MIGOUT) {
            CLI_PrintBuf("migrate out msg cnt is over MAX_NR_MIGOUT.\n");
            return;
        }
        for (int i = 0; i < migOutMsg.count; i++) {
            migOutMsg.payload[i].inner[0].destNid = values[i * PAIR_OF_DESTNID_PID_RATIO + DEST_NODE];
            migOutMsg.payload[i].pid = values[i * PAIR_OF_DESTNID_PID_RATIO + PID];
            migOutMsg.payload[i].inner[0].ratio = values[i * PAIR_OF_DESTNID_PID_RATIO + RATIO];
            migOutMsg.payload[i].count = 1;
        }
        msg = &migOutMsg;
    }
    ret = ubturbo_smap_migrate_out(msg, pidType);
    CLI_PrintBuf("smap migrate out ret(%d).\n", ret);
    for (int i = 0; i < migOutMsg.count; i++) {
        CLI_PrintBuf("smap migrate out node(%lu) pid(%lu) ratio(%lu) pidType(%lu) ret(%d).\n",
            migOutMsg.payload[i].inner[0].destNid, migOutMsg.payload[i].pid, migOutMsg.payload[i].inner[0].ratio, pidType, ret);
    }
}

enum {
    DEST_NODE,
    PID,
    RATIO,
    MIG_MEMSIZE,
    MIG_MODE,
    PID_TYPE,
};

// 迁出命令调用函数（比例改大小），支持多个输入以及注入空指针
static void SmapMigrateOutMemSizeCall(int32_t argc, char *argv[])
{
    if ((argc - 1) % PAIR_OF_DESTNID_PID_MEMSIZE) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIG_OUT_MEMSIZE].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }

    int pidType = values[argc - 1];
    struct MigrateOutMsg migOutMsg = { 0 };
    struct MigrateOutMsg *msg;
    if (argc < MIG_OUT_MEMSIZE_ARGC) { // 仅传入pagetype时，注入空指针
        msg = NULL;
    } else { // 支持批量输入
        migOutMsg.count = argc / PAIR_OF_DESTNID_PID_MEMSIZE;
        if (migOutMsg.count > MAX_NR_MIGOUT) {
            CLI_PrintBuf("migrate out msg cnt is over MAX_NR_MIGOUT.\n");
            return;
        }
        for (int i = 0; i < migOutMsg.count; i++) {
            migOutMsg.payload[i].count = 1;
            migOutMsg.payload[i].inner[0].destNid = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + DEST_NODE];
            migOutMsg.payload[i].pid = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + PID];
            migOutMsg.payload[i].inner[0].ratio = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + RATIO];
            migOutMsg.payload[i].inner[0].memSize = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + MIG_MEMSIZE];
            migOutMsg.payload[i].inner[0].migrateMode = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + MIG_MODE];
        }
        msg = &migOutMsg;
    }
    ret = ubturbo_smap_migrate_out(msg, pidType);
    CLI_PrintBuf("smap migrate out ret(%d).\n", ret);
    for (int i = 0; i < migOutMsg.count; i++) {
        CLI_PrintBuf("smap migrate out node(%lu) pid(%lu) ratio(%lu) memSize(%llu) migMode(%d) pidType(%lu) ret(%d).\n",
            migOutMsg.payload[i].inner[0].destNid, migOutMsg.payload[i].pid, migOutMsg.payload[i].inner[0].ratio,
            migOutMsg.payload[i].inner[0].memSize, migOutMsg.payload[i].inner[0].migrateMode, pidType, ret);
    }
}

static inline uint64_t GetClock(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * US_PER_SEC + tv.tv_usec;
}

#define INVALID_MEMID 0

static inline bool IsObmmShmDir(char *path)
{
    return strncmp(path, OBMM_SHM_DIR, strlen(OBMM_SHM_DIR)) == 0;
}

static int ExtractHexContent(char *path, uint64_t *content)
{
    char line[MAX_LINE_LEN] = { 0 };
    int ret = 0;
    int closeRet;

    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -errno;
    }

    if (fgets(line, sizeof(line), fp)) {
        errno = 0;
        *content = strtoull(line, NULL, 16);
        if (errno) {
            ret = -errno;
        }
    }
    closeRet = fclose(fp);
    if (closeRet) {
        CLI_PrintBuf("Close file %s failed\n", path);
    }
    return ret;
}

enum FindMemidResult {
    FMR_STOP = 0,
    FMR_CONTINUE
};

static int FindMemidByAddrSize(uint64_t addr, uint64_t size, uint64_t *memid, uint64_t *memidSize)
{
    DIR *dir;
    struct dirent *entry;
    char path[MAX_PATH_LEN];
    int ret;
    uint64_t content;

    dir = opendir(OBMM_SYS_DIR);
    if (!dir) {
        CLI_PrintBuf("Unable to open obmm sys dir: %d.", -errno);
        return -errno;
    }

    CLI_PrintBuf("Param addr %#llx, size %#llx\n", addr, size);

    // 遍历目录中的所有条目
    while (entry = readdir(dir)) {
        if (!IsObmmShmDir(entry->d_name)) {
            continue;
        }
        ret = snprintf(path, sizeof(path), "%s/%s/import_info/pa", OBMM_SYS_DIR, entry->d_name);
        if (ret <= 0) {
            CLI_PrintBuf("Build pa file path for %s failed\n", entry->d_name);
            continue;
        }
        if (ExtractHexContent(path, &content)) {
            CLI_PrintBuf("Extract hex content from %s failed\n", path);
            continue;
        }
        if (addr != content) {
            continue;
        }

        ret = snprintf(path, sizeof(path), "%s/%s/size", OBMM_SYS_DIR, entry->d_name);
        if (ret <= 0) {
            CLI_PrintBuf("Build size file path for %s failed\n", entry->d_name);
            continue;
        }
        if (ExtractHexContent(path, &content)) {
            CLI_PrintBuf("Extract hex content from %s failed\n", path);
            continue;
        }
        if (size < content) {
            CLI_PrintBuf("Size %#llx > size %#llx extracted from %s\n", size, content, path);
            continue;
        }

        *memidSize = content;
        ret = sscanf(entry->d_name, "obmm_shmdev%llu", memid);
        CLI_PrintBuf("Extract memid from %s ret: %d, memid: %llu\n", entry->d_name, ret, *memid);
        closedir(dir);
        if (size == content) {
            return ret > 0 ? FMR_STOP : -EFAULT;
        } else {
            CLI_PrintBuf("Size %llu < size %llu extracted from %s, continue\n", size, content, path);
            return ret > 0 ? FMR_CONTINUE : -EFAULT;
        }
    }

    closedir(dir);
    return -ENOENT;
}

// 迁回命令调用函数
static void SmapMigrateBackCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc != MIG_BACK_ARGC) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        injectNullptr = true;
    }
    uint64_t values[MIG_BACK_ARGC];
    uint64_t memid;
    struct MigrateBackMsg miBackMsg;
    enum {
        SRC_NID,
        DST_NID,
        PA_START,
        PA_END,
    };
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, MIG_BACK_ARGC);
    if (ret) {
        return;
    }
    uint64_t taskId = GetClock();
    miBackMsg.taskID = taskId;
    uint64_t size = ((values[PA_END] | 0x1) == values[PA_END]) ?
        values[PA_END] - values[PA_START] + 1 :
        values[PA_END] - values[PA_START];

    int count = 0;
    uint64_t addr = values[PA_START];
    do {
        uint64_t tmpSize;

        ret = FindMemidByAddrSize(addr, size, &memid, &tmpSize);
        if (ret < 0) {
            memid = INVALID_MEMID;
            CLI_PrintBuf("Range %#llx-%#llx doesn't belongs to any memid.\n", addr, addr + tmpSize - 1);
        } else if (ret == FMR_STOP) {
            CLI_PrintBuf("Range %#llx-%#llx belongs to memid %llu.\n", addr, addr + tmpSize - 1, memid);
        } else {
            CLI_PrintBuf("Range %#llx-%#llx belongs to memid %llu.\n", addr, addr + tmpSize - 1, memid);
            addr += tmpSize;
            size -= tmpSize;
        }
        miBackMsg.payload[count].srcNid = values[SRC_NID];
        miBackMsg.payload[count].destNid = values[DST_NID];
        miBackMsg.payload[count].memid = memid;
        count++;
    } while (ret == FMR_CONTINUE && count < MAX_NR_MIGBACK);
    miBackMsg.count = count;

    struct MigrateBackMsg *msg = injectNullptr ? NULL : &miBackMsg;
    ret = ubturbo_smap_migrate_back(msg);
    CLI_PrintBuf("smap migrate back taskId(%lu) "
        "count(1) src_nid(%lu) dest_nid(-1) paStart(0x%lx) paEnd(0x%lx) ret(%d).\n",
        taskId, values[SRC_NID], values[PA_START], values[PA_END], ret);
}

static void SmapMigrateBackMemidCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc != MIG_BACK_MEMID_ARGC) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        injectNullptr = true;
    }
    uint64_t values[MIG_BACK_ARGC];
    enum {
        SRC_NID,
        DST_NID,
        MEMID,
    };
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, MIG_BACK_ARGC);
    if (ret) {
        return;
    }
    uint64_t taskId = GetClock();
    struct MigrateBackMsg miBackMsg = {
        taskId, 1,
        { { values[SRC_NID], values[DST_NID], values[MEMID] } }
    };
    struct MigrateBackMsg *msg = injectNullptr ? NULL : &miBackMsg;
    ret = ubturbo_smap_migrate_back(msg);
    CLI_PrintBuf("smap migrate back taskId(%lu) "
        "count(1) src_nid(%lu) dest_nid(-1) memid(%llu) ret(%d).\n",
        taskId, values[SRC_NID], values[MEMID], ret);
}

static bool IsRemoteNuma(unsigned long nid)
{
#define SYS_NODE_REMOTE_LEN 50
    char path[SYS_NODE_REMOTE_LEN] = { 0 };
#undef SYS_NODE_REMOTE_LEN

    int ret = snprintf(path, sizeof(path), "%s/node%lu/remote", SYS_NODE_PATH, nid);
    if (ret == -1) {
        CLI_PrintBuf("Failed to build node%lu remote path.", nid);
        return false;
    }

    FILE *file = fopen(path, "r");
    if (!file) {
        CLI_PrintBuf("Failed to open node%lu remote file.", nid);
        return false;
    }

    int c = fgetc(file);
    if (fclose(file) != 0) {
        CLI_PrintBuf("Failed to close node%lu remote file: %d.", nid, errno);
    }
    if (c == EOF) {
        CLI_PrintBuf("Failed to read node%lu remote file.", nid);
        return false;
    }

    return c == '1';
}

static int GetNrRemoteNuma(int *numas, int maxNodes)
{
    DIR *dir = opendir(SYS_NODE_PATH);
    if (!dir) {
        CLI_PrintBuf("Failed to open node directory: %d.", -errno);
        return 0;
    }
    int nrRemoteNuma = 0;
#define NODE_LITERAL_LEN 4
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL && nrRemoteNuma < maxNodes) {
        if (strncmp(entry->d_name, "node", NODE_LITERAL_LEN) == 0) {
            char *numStr = entry->d_name + NODE_LITERAL_LEN;
            char *endPtr;
            unsigned long num = strtoul(numStr, &endPtr, DECIMAL);
            if (*numStr != '\0' && *endPtr == '\0' && IsRemoteNuma(num)) {
                numas[nrRemoteNuma++] = (int)num;
            }
        }
    }
    closedir(dir);
#undef NODE_LITERAL_LEN

    return nrRemoteNuma;
}

// 移除调用函数
static void SmapRemoveCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc <= 0) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        return;
    }
    if (argc == 1) {
        injectNullptr = true;
    }

    // 解析参数
    uint64_t values[argc];
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    int pidType = values[argc - 1];

    struct RemoveMsg rmMsg = { 0 };
    rmMsg.count = argc - 1;
    int remoteNumas[REMOTE_NUMA_NUM];
    int nrRemoteNuma = GetNrRemoteNuma(remoteNumas, REMOTE_NUMA_NUM);
    for (int i = 0; i < rmMsg.count; i++) {
        rmMsg.payload[i].pid = values[i];
        rmMsg.payload[i].count = nrRemoteNuma;
        for (int j = 0; j < nrRemoteNuma; j++) {
            rmMsg.payload[i].nid[j] = remoteNumas[j];
        }
    }
    struct RemoveMsg* msg = injectNullptr ? NULL : &rmMsg;
    ret = ubturbo_smap_remove(msg, pidType);
    CLI_PrintBuf("smap remove pids ret(%d).\n", ret);
    for (int i = 0; i < rmMsg.count; i++) {
        CLI_PrintBuf("smap remove pid(%lu) pidType(%lu) ret(%d).\n", values[i], pidType, ret);
    }
}

static void SmapRemoveMultiNumaCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc <= 0) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        return;
    }
    if (argc == 1) {
        injectNullptr = true;
    }

    // 解析参数
    uint64_t values[argc];
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    int pidType = values[argc - 1];

    struct RemoveMsg rmMsg = { 0 };
    rmMsg.count = 1;

    rmMsg.payload[0].pid = values[0];
    rmMsg.payload[0].count = argc - 2;
    for (int i = 0; i < rmMsg.payload[0].count; i++) {
        rmMsg.payload[0].nid[i] = values[i + 1];
    }

    struct RemoveMsg* msg = injectNullptr ? NULL : &rmMsg;
    pidType = values[argc - 1];
    ret = ubturbo_smap_remove(msg, pidType);
    CLI_PrintBuf("smap remove pids ret(%d).\n", ret);
    for (int i = 0; i < rmMsg.payload[0].count; i++) {
        CLI_PrintBuf("smap remove pid(%lu)  nid(%d) pidType(%lu) ret(%d).\n", values[0], rmMsg.payload[0].nid[i], pidType, ret);
    }
}

// 使能调用函数
static void SmapEnableNodeCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc != SMAP_ENABLE_ARGC) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        injectNullptr = true;
    }
    uint64_t values[SMAP_ENABLE_ARGC];
    enum {
        ENABLE,
        NID,
    };
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, SMAP_ENABLE_ARGC);
    if (ret) {
        return;
    }
    struct EnableNodeMsg enMsg = { values[ENABLE], values[NID] };
    struct EnableNodeMsg* msg = injectNullptr ? NULL : &enMsg;
    ret = ubturbo_smap_node_enable(msg);
    CLI_PrintBuf("smap enable node enable(%lu) nid(%lu) ret(%d).\n", values[ENABLE], values[NID], ret);
}

static void SmapInitTest(int32_t argc, char *argv[])
{
    if (argc != 1) {
        CLI_PrintBuf("Smap init argc num incorrect!\n");
        return;
    }
    uint64_t pageType = 0;
    int ret = StrToU64(argv[0], &pageType);
    if (ret) {
        CLI_PrintBuf("Smap init pageType error.\n");
        return;
    }
    ret = ubturbo_smap_start(pageType, NULL);
    if (ret) {
        CLI_PrintBuf("Smap init failed, ret(%d).\n", ret);
        return;
    }
    CLI_PrintBuf("Smap init success, ret(%d).\n", ret);
}

static void SmapStopTest(int32_t argc, char *argv[])
{
    int ret;
    ret = ubturbo_smap_stop();
    if (ret) {
        CLI_PrintBuf("Smap stop failed, ret(%d).\n", ret);
        return;
    }
    CLI_PrintBuf("Smap stop success, ret(%d).\n", ret);
}

static void SmapUrgentMigrateOutTest(int32_t argc, char *argv[])
{
    uint64_t outPut;
    if (argc != 1) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        return;
    }
    int ret = StrToU64(argv[0], &outPut);
    if (ret) {
        CLI_PrintBuf("ubturbo_smap_urgent_migrate_out arg error, ret(%d).\n", ret);
        return;
    }
    ubturbo_smap_urgent_migrate_out(outPut);
    CLI_PrintBuf("Smap UrgentMigrateOut success, ret(%d).\n", ret);
}

static void SmapEnableAdaptMemCall(int32_t argc, char *argv[])
{
    if (!CheckArgumentNums(argc, SMAP_ENABLE_ADAPT_MEM_ARGC, CMD_SMAP_ENABLE_ADAPT_MEM)) {
        return;
    }
    uint64_t value;
    int ret = StrToU64(argv[0], &value);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }
    ret = SmapEnableAdaptMem(value);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }
    CLI_PrintBuf("Setup adapt mem %d succeed!\n", value);
}

static void SmapQueryVmMemCall(int32_t argc, char *argv[])
{
    if (!CheckArgumentNums(argc, SMAP_QUERY_ADAPT_MEM_ARGC, CMD_SMAP_QUERY_ADAPT_MEM)) {
        return;
    }
    uint64_t value;
    int ret = StrToU64(argv[0], &value);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }

    struct VmRatioMsg vrMsg = { 0 };
    struct VmRatioMsg *msg = value == 0 ? NULL : &vrMsg;
    ret = SmapQueryVmMemRatio(msg);
    if (ret) {
        CLI_PrintBuf("Queried VMs mem ratio failed ret(%d)\n", ret);
        return;
    }
    for (int i = 0; i < vrMsg.nrVm; i++) {
        CLI_PrintBuf("Queried local mem ratio %.2lf%% of VM pid(%d)\n",
            vrMsg.vr[i].ratio, vrMsg.vr[i].pid);
    }
    CLI_PrintBuf("Queried %d VMs mem ratio done. ret(%d)\n", vrMsg.nrVm, ret);
}

static void SetSmapRemoteNumaInfoCall(int32_t argc, char *argv[])
{
    bool injectNullptr = false;
    if (argc != SMAP_NOTIFY_BORROW_MEM_ARGC) {
        CLI_PrintBuf("Inject nullptr.\n", argc);
        injectNullptr = true;
    }

    uint64_t values[argc];
    int ret = injectNullptr ? 0 : ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    enum {
        SRC_NID,
        DEST_NID,
        SIZE,
    };

    struct SetRemoteNumaInfoMsg borrowMemMsg = { values[SRC_NID], values[DEST_NID], values[SIZE] };
    struct SetRemoteNumaInfoMsg *msg = injectNullptr ? NULL : &borrowMemMsg;
    ret = ubturbo_smap_remote_numa_info_set(msg);
    CLI_PrintBuf("Set smap remote numa info src nid(%d) dest nid(%d) size(%u) ret(%d)\n",
    values[SRC_NID], values[DEST_NID], values[SIZE], ret);
}

static void SmapQueryVmFreqCall(int32_t argc, char *argv[])
{
    uint32_t len, lenOut;
    int pid, flag, noPrint;
    int rangeStart, rangeEnd;
    uint64_t values[SMAP_QUERY_VM_FREQ_MAX_ARGC];
    uint16_t *data = NULL;
    uint32_t nrFreq0 = 0;
    uint64_t hits = 0;

    enum { PID = 0, FLAG, LENGTH, NO_PRINT, RANGE_START, RANGE_END };

    if (argc < SMAP_QUERY_VM_FREQ_ARGC || argc > SMAP_QUERY_VM_FREQ_MAX_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_QUERY_VM_FREQ].description);
        return;
    }
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }

    pid = values[PID];
    flag = values[FLAG];
    len = values[LENGTH];
    noPrint = argc > NO_PRINT ? values[NO_PRINT] : 0;
    rangeStart = argc > RANGE_START ? values[RANGE_START] : 0;
    rangeEnd = argc > RANGE_END ? values[RANGE_END] : len;

    if (noPrint != 0 && noPrint != 1) {
        CLI_PrintBuf("no_print should be either 0 or 1\n");
        return;
    }
    if (rangeEnd > len) {
        CLI_PrintBuf("range end %d should be <= len %u\n", rangeEnd, len);
        return;
    }
    if (argc > RANGE_START && rangeStart >= rangeEnd) {
        CLI_PrintBuf("range start %d should be < range end %d\n", rangeStart, rangeEnd);
        return;
    }
    if (flag == 1) {
        data = (uint16_t *)calloc(len, sizeof(uint16_t));
        if (!data) {
            CLI_PrintBuf("malloc freq arr failed\n");
            return;
        }
    }
    ret = ubturbo_smap_freq_query(values[PID], data, len, &lenOut, 0);
    if (ret) {
        CLI_PrintBuf("Query the page-accessed freq of vm(pid:%d) failed. ret(%d)\n", values[PID], ret);
        if (flag == 1) {
            free(data);
        }
        return;
    }
    CLI_PrintBuf("Query the page-accessed freq of vm(pid:%d) succeeded. ret(%d), lenOut(%d)\n",
        values[PID], ret, lenOut);
    if (!noPrint) {
        CLI_PrintBuf("the page-accessed freq of vm(pid:%d) is as follows:\n", values[PID]);
        for (uint32_t i = 0; data != NULL && i < lenOut; i++) {
            CLI_PrintBuf("%u ", data[i]);
        }
        CLI_PrintBuf("\n");
    }
    for (uint32_t i = rangeStart; data != NULL && i < rangeEnd; i++) {
        nrFreq0 += (data[i] == 0 ? 1 : 0);
        hits += data[i];
    }
    CLI_PrintBuf("page %d-%d nr: %u, nr_freq0: %u, hits: %llu\n", rangeStart, rangeEnd - 1, rangeEnd - rangeStart,
        nrFreq0, hits);
    if (flag == 1) {
        free(data);
    }
}

static void SmapQueryVmFreqStatisticCall(int32_t argc, char *argv[])
{
    uint32_t len, lenOut;
    int pid, flag, noPrint, dataSource;
    int rangeStart, rangeEnd;
    uint64_t values[SMAP_QUERY_VM_FREQ_STATISTIC_MAX_ARGC];
    uint16_t *data = NULL;
    uint32_t nrFreq0 = 0;
    uint64_t hits = 0;

    enum { PID = 0, FLAG, LENGTH, NO_PRINT, RANGE_START, RANGE_END };

    if (argc < SMAP_QUERY_VM_FREQ_ARGC || argc > SMAP_QUERY_VM_FREQ_STATISTIC_MAX_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_QUERY_VM_FREQ_STATISTIC].description);
        return;
    }
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }

    pid = values[PID];
    flag = values[FLAG];
    len = values[LENGTH];
    noPrint = argc > NO_PRINT ? values[NO_PRINT] : 0;
    rangeStart = argc > RANGE_START ? values[RANGE_START] : 0;
    rangeEnd = argc > RANGE_END ? values[RANGE_END] : len;
    dataSource = values[argc - 1];
    if (noPrint != 0 && noPrint != 1) {
        CLI_PrintBuf("no_print should be either 0 or 1\n");
        return;
    }
    if (rangeEnd > len) {
        CLI_PrintBuf("range end %d should be <= len %u\n", rangeEnd, len);
        return;
    }
    if (argc > RANGE_START && rangeStart >= rangeEnd) {
        CLI_PrintBuf("range start %d should be < range end %d\n", rangeStart, rangeEnd);
        return;
    }
    if (flag == 1) {
        data = (uint16_t *)calloc(len, sizeof(uint16_t));
        if (!data) {
            CLI_PrintBuf("malloc freq arr failed\n");
            return;
        }
    }
    ret = ubturbo_smap_freq_query(values[PID], data, len, &lenOut, dataSource);
    if (ret) {
        CLI_PrintBuf("Query the page-accessed freq of vm(pid:%d) failed. ret(%d)\n", values[PID], ret);
        if (flag == 1) {
            free(data);
        }
        return;
    }
    CLI_PrintBuf("Query the page-accessed freq of vm(pid:%d) succeeded. ret(%d), lenOut(%d)\n",
        values[PID], ret, lenOut);
    if (!noPrint) {
        CLI_PrintBuf("the page-accessed freq of vm(pid:%d) is as follows:\n", values[PID]);
        for (uint32_t i = 0; i < len; i++) {
            CLI_PrintBuf("%u ", data[i]);
        }
        CLI_PrintBuf("\n");
    }
    for (uint32_t i = rangeStart; i < rangeEnd; i++) {
        nrFreq0 += (data[i] == 0 ? 1 : 0);
        hits += data[i];
    }
    CLI_PrintBuf("page %d-%d nr: %u, nr_freq0: %u, hits: %llu\n", rangeStart, rangeEnd - 1, rangeEnd - rangeStart,
        nrFreq0, hits);
    if (flag == 1) {
        free(data);
    }
}

static void SetSmapRunModeCall(int32_t argc, char *argv[])
{
    if (!CheckArgumentNums(argc, SMAP_SET_RUN_MODE_ARGC, CMD_SMAP_SET_RUN_MODE)) {
        return;
    }
    uint64_t value;
    int ret = StrToU64(argv[0], &value);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }
    ret = ubturbo_smap_run_mode_set(value);
    if (ret) {
        CLI_PrintBuf("Input arg(should be 0 or 1) is invalid. ret(%d)\n", ret);
        return;
    }
    CLI_PrintBuf("Set run mode success! ret(%d)\n", ret);
}

static void SmapAddProcessTrackingCall(int32_t argc, char *argv[])
{
    if ((argc % SMAP_ADD_PROCESS_TRACKING_ARGC) || argc == 0) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_ADD_PROCESS_TRACKING].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }

    int len = values[argc - SMAP_ADD_PROCESS_TRACKING_ARGC];
    int scanType = values[argc - SMAP_ADD_PROCESS_TRACKING_ARGC + 1];
    int count = (argc - SMAP_ADD_PROCESS_TRACKING_STABLE_ARGC) / SMAP_ADD_PROCESS_TRACKING_ARGC;
    int pid[count];
    uint32_t scanTime[count];
    uint32_t duration[count];
    if (count != len) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        return;
    }
    if (len == 0) { //仅传入len和flag且len为0时，构造空指针
        ret = ubturbo_smap_process_tracking_add(NULL, NULL, NULL, len, scanType);
    } else {
        for (int i = 0; i < count; i++) {
            pid[i] = values[i];
            scanTime[i] = values[i + count];
            duration[i] = 1;
        }
        ret = ubturbo_smap_process_tracking_add(pid, scanTime, duration, len, scanType);
    }
    CLI_PrintBuf("smap add process tracking ret(%d).\n", ret);
    for (int i = 0; i < count; i++) {
        CLI_PrintBuf("smap add process tracking pid(%d) scanTime(%d) duration(%d) len(%d) scanType(%d).\n",
            pid[i], scanTime[i], duration[i], len, scanType);
        CLI_PrintBuf("smap add process tracking set duration default value 1\n");
    }
}

static void SmapAddProcessTrackingStatisticCall(int32_t argc, char *argv[])
{
    if ((argc % SMAP_ADD_PROCESS_TRACKING_STATISTIC_ARGC != 2) || argc == 0) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_ADD_PROCESS_STATISTIC_TRACKING].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }

    int len = values[argc - SMAP_ADD_PROCESS_TRACKING_STABLE_ARGC];
    int scanType = values[argc - 1];
    int count = (argc - SMAP_ADD_PROCESS_TRACKING_STABLE_ARGC) / SMAP_ADD_PROCESS_TRACKING_STATISTIC_ARGC;
    int pid[count];
    uint32_t scanTime[count];
    uint32_t duration[count];
    if (count != len) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        return;
    }
    if (len == 0) { // 仅传入len和flag且len为0时，构造空指针
        ret = ubturbo_smap_process_tracking_add(NULL, NULL, NULL, len, scanType);
    } else {
        for (int i = 0; i < count; i++) {
            pid[i] = values[i];
            scanTime[i] = values[count + i];
            duration[i] = values[2*count + i];
        }
        ret = ubturbo_smap_process_tracking_add(pid, scanTime, duration, len, scanType);
    }
    CLI_PrintBuf("smap add process tracking ret(%d).\n", ret);
    for (int i = 0; i < count; i++) {
        CLI_PrintBuf("smap add process tracking pid(%d) scanTime(%d) duration(%d) len(%d) scanType(%d).\n",
            pid[i], scanTime[i], duration[i], len, scanType);
    }
}

static void SmapRemoveProcessTrackingCall(int32_t argc, char *argv[])
{
    if (argc < SMAP_REMOVE_PROCESS_TRACKING_ARGC) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_REMOVE_PROCESS_TRACKING].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    int len = values[argc - MIN_CMD_NUM];
    int flag = values[argc - 1];
    int pid[len];
    if ((len != argc - MIN_CMD_NUM) && len > 0) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        return;
    }
    if (len == 0) {
        ret = ubturbo_smap_process_tracking_remove(NULL, len, flag);
    } else {
        for (int i = 0; i < len; i++) {
            pid[i] = values[i];
        }
        ret = ubturbo_smap_process_tracking_remove(pid, len, flag);
    }
    CLI_PrintBuf("smap remove process tracking ret(%d).\n", ret);
    for (int i = 0; i < len; i++) {
        CLI_PrintBuf("smap remove process tracking pid(%d) len(%d) flag(%d).\n",
            pid[i], len, flag);
    }
}

static void SmapEnableProcessMigrateCall(int32_t argc, char *argv[])
{
    if (argc < SMAP_ENABLE_PROCESS_MIGRATE_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_ENABLE_PROCESS_MIGRATE_MODE].description);
        return;
    }
    uint64_t *values = malloc(argc * sizeof(*values));
    if (!values) {
        CLI_PrintBuf("Malloc values for SmapEnableProcessMigrateCall failed, argc: %d\n", argc);
        return;
    }
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapEnableProcessMigrateCall failed\n");
        free(values);
        return;
    }
    enum {
        ENABLE = 0,
        FLAGS,
        LEN,
    };
    int pidNum = argc - SMAP_ENABLE_PROCESS_MIGRATE_ARGC;
    int *pidArr = NULL;
    if (pidNum) {
        pidArr = malloc(pidNum * sizeof(*pidArr));
        if (!pidArr) {
            CLI_PrintBuf("Malloc pidArr for SmapEnableProcessMigrateCall failed, pidNum: %d\n", pidNum);
            free(values);
            return;
        }
        for (int i = SMAP_ENABLE_PROCESS_MIGRATE_ARGC; i < argc; i++) {
            pidArr[i - SMAP_ENABLE_PROCESS_MIGRATE_ARGC] = values[i];
        }
    }
    // flags未使用到，暂时都置为0
    ret = ubturbo_smap_process_migrate_enable(pidArr, values[LEN], values[ENABLE], values[FLAGS]);
    CLI_PrintBuf("Enable process migrate ret(%d)\n", ret);
    free(pidArr);
    free(values);
}

static void SmapMigrateRemoteNumaCall(int32_t argc, char *argv[])
{
    int ret;

    if (argc == 0) {
        ret = ubturbo_smap_remote_numa_migrate(NULL);
        CLI_PrintBuf("Migrate remote numa ret(%d)\n", ret);
        return;
    }

    if (argc < SMAP_MIGRATE_REMOTE_NUMA_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIGRATE_REMOTE_NUMA_MODE].description);
        return;
    }

    uint64_t values[argc];
    ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapMigrateRemoteNumaCall failed\n");
        return;
    }
    enum {
        SRC_NID = 0,
        DEST_NID,
        RANGE_COUNT,
    };
    int addrLen = (argc - SMAP_MIGRATE_REMOTE_NUMA_ARGC) / 2;
    struct MigrateNumaMsg msg = { values[SRC_NID], values[DEST_NID], values[RANGE_COUNT] };
    int valueIndex = SMAP_MIGRATE_REMOTE_NUMA_ARGC;
    int count = 0;
    int i, j;
    for (i = j = 0; i < addrLen && j < MAX_NR_MIGNUMA; i++) {
        uint64_t memid;
        uint64_t size;
        uint64_t paStart = values[valueIndex++];
        uint64_t paEnd = values[valueIndex++];
        uint64_t addr = paStart;

        size = ((paEnd | 0x1) == paEnd) ? (paEnd - paStart + 1) : (paEnd - paStart);

        do {
            uint64_t tmpSize;

            ret = FindMemidByAddrSize(addr, size, &memid, &tmpSize);
            if (ret < 0) {
                memid = INVALID_MEMID;
                CLI_PrintBuf("Range %#llx-%#llx doesn't belongs to any memid.\n", addr, addr + size - 1);
            } else if (ret == FMR_STOP) {
                CLI_PrintBuf("Range %#llx-%#llx belongs to memid %llu.\n", addr, addr + tmpSize - 1, memid);
            } else {
                CLI_PrintBuf("Range %#llx-%#llx belongs to memid %llu.\n", addr, addr + tmpSize - 1, memid);
                addr += tmpSize;
                size -= tmpSize;
            }
            msg.memids[j++] = memid;
            count++;
        } while (ret == FMR_CONTINUE && j < MAX_NR_MIGNUMA);
    }
    msg.count = count;
    ret = ubturbo_smap_remote_numa_migrate(&msg);
    CLI_PrintBuf("Migrate remote numa ret(%d)\n", ret);
}

static void SmapMigrateRemoteNumaMemidCall(int32_t argc, char *argv[])
{
    int ret;

    if (argc == 0) {
        ret = ubturbo_smap_remote_numa_migrate(NULL);
        CLI_PrintBuf("Migrate remote numa ret(%d)\n", ret);
        return;
    }

    if (argc < SMAP_MIGRATE_REMOTE_NUMA_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIGRATE_REMOTE_NUMA_MODE].description);
        return;
    }

    uint64_t values[argc];
    ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapMigrateRemoteNumaCall failed\n");
        return;
    }
    enum {
        SRC_NID = 0,
        DEST_NID,
        RANGE_COUNT,
    };
    int addrLen = argc - SMAP_MIGRATE_REMOTE_NUMA_ARGC;
    struct MigrateNumaMsg msg = { values[SRC_NID], values[DEST_NID], values[RANGE_COUNT] };
    int valueIndex = SMAP_MIGRATE_REMOTE_NUMA_ARGC;
    for (int i = 0; i < addrLen; i++) {
        msg.memids[i] = values[valueIndex++];
    }
    ret = ubturbo_smap_remote_numa_migrate(&msg);
    CLI_PrintBuf("Migrate remote numa ret(%d)\n", ret);
}

static void SmapMigratePidRemoteNumaCall(int32_t argc, char *argv[])
{
    int pidNum;
    if ((argc - 2) % SMAP_MIGRATE_PID_REMOTE_NUMA_ARGC != 0) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIGRATE_PID_REMOTE_NUMA_MODE].description);
        return;
    }
    struct MigrateEscapeMsg msg = { 0 };

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapMigratePidRemoteNumaCall failed\n");
        return;
    }

    enum {
        PID,
        SRC_NID,
        DEST_NID,
        RATIO,
        MEMSIZE,
    };

    msg.count = values[0];

    for (int i = 0; i < msg.count && i < MAX_NR_MIGRATE_ESCAPE; i++) {
        msg.payload[i].pid = values[i * 5 + PID + 1];
        msg.payload[i].srcNid = values[i * 5 + SRC_NID + 1];
        msg.payload[i].destNid = values[i * 5 + DEST_NID + 1];
        msg.payload[i].ratio = values[i * 5 + RATIO + 1];
        msg.payload[i].memSize = values[i * 5 + MEMSIZE + 1];
        msg.payload[i].migrateMode = values[argc - 1];
    }

    ret = ubturbo_smap_pid_remote_numa_migrate(&msg);
    CLI_PrintBuf("Migrate pid remote numa ret(%d)\n", ret);
    for (int i = 0; i < msg.count && i < MAX_NR_MIGRATE_ESCAPE; i++) {
        CLI_PrintBuf("Migrate pid(%d) srcNid(%d) destNid(%d) ratio(%d) memSize(%d) migrateMode(%d)\n",
        msg.payload[i].pid, msg.payload[i].srcNid, msg.payload[i].destNid, msg.payload[i].ratio, msg.payload[i].memSize, msg.payload[i].migrateMode);
    }
}

static void SmapMigrateOutSyncCall(int32_t argc, char *argv[])
{
    uint64_t values[argc];
    struct MigrateOutMsg migOutSyncMsg = { 0 };
    struct MigrateOutMsg *msg;

    if ((argc - MIG_OUT_SYNC_ARGC) % PAIR_OF_DESTNID_PID_MEMSIZE) {
        CLI_PrintBuf("Input parameters failed! num: %d\n", argc);
        CLI_PrintBuf("Convert args to u64 for SmapMigrateOutSyncCall failed\n");
        return;
    }

    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapMigrateOutSyncCall failed\n");
        return;
    }

    uint64_t waitTime = values[argc - 1];
    int pidType = values[argc - MIG_OUT_SYNC_ARGC];

     // 支持批量输入
    migOutSyncMsg.count = argc / PAIR_OF_DESTNID_PID_MEMSIZE;
    if (migOutSyncMsg.count > MAX_NR_MIGOUT) {
        CLI_PrintBuf("migrate out msg cnt is over MAX_NR_MIGOUT.\n");
        return;
    }
    for (int i = 0; i < migOutSyncMsg.count; i++) {
        migOutSyncMsg.payload[i].count = 1;
        migOutSyncMsg.payload[i].inner[0].destNid = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + SYNC_DEST_NODE];
        migOutSyncMsg.payload[i].pid = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + SYNC_PID];
        migOutSyncMsg.payload[i].inner[0].ratio = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + SYNC_RATIO];
        migOutSyncMsg.payload[i].inner[0].memSize = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + SYNC_MIG_MEMSIZE];
        migOutSyncMsg.payload[i].inner[0].migrateMode = values[i * PAIR_OF_DESTNID_PID_MEMSIZE + SYNC_MIG_MODE];
    }
    msg = &migOutSyncMsg;

    ret = ubturbo_smap_migrate_out_sync(msg, pidType, waitTime);
    CLI_PrintBuf("Smap migrate out callback ret(%d)\n", ret);
    for (int i = 0; i < migOutSyncMsg.count; i++) {
        CLI_PrintBuf("Smap migrate out callback node(%d) pid(%d) ratio(%d) memSize(%llu) migMode(%d) pidType(%d) waitTime(%lu) ret(%d).\n",
            migOutSyncMsg.payload[i].inner[0].destNid, migOutSyncMsg.payload[i].pid, migOutSyncMsg.payload[i].inner[0].ratio,
            migOutSyncMsg.payload[i].inner[0].memSize, migOutSyncMsg.payload[i].inner[0].migrateMode, pidType, waitTime, ret);
    }
}

static void SmapQueryProcessConfigCall(int32_t argc, char *argv[])
{
    int ret;
    int nid, resultStub, inLen, outLenStub;
    enum { NID, RESULT, IN_LEN, OUT_LEN };
    uint64_t values[SMAP_QUERY_PROCESS_CONFIG_ARGC];
    struct OldProcessPayload *result = NULL;
    int *outLen = NULL;

    if (argc != SMAP_QUERY_PROCESS_CONFIG_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_QUERY_PROCESS_CONFIG].description);
        return;
    }
    ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapQueryProcessConfigCall failed\n");
        return;
    }

    nid = values[NID];
    resultStub = values[RESULT];
    inLen = values[IN_LEN];
    outLenStub = values[OUT_LEN];
    if (inLen <= 0) {
        CLI_PrintBuf("Input parameters inLen invalid: %d\n", inLen);
        return;
    }
    // If resultStub is 0, it indicates the caller wants to pass it as NULL
    if (resultStub != 0) {
        result = malloc(inLen * sizeof(*result));
        if (!result) {
            CLI_PrintBuf("SmapQueryNumaConfigCall malloc failed\n");
            return;
        }
    }
    // If outLenStub is 0, it indicates the caller wants to pass it as NULL
    outLen = outLenStub == 0 ? NULL : &outLenStub;
    ret = ubturbo_smap_process_config_query(nid, result, inLen, outLen);
    CLI_PrintBuf("Query process config ret(%d)\n", ret);
    if (ret == 0 && outLen) {
        CLI_PrintBuf("outLen: %d\n", *outLen);
        for (int i = 0; i < *outLen; i++) {
            struct OldProcessPayload *p = &result[i];
            CLI_PrintBuf("pid: %d, type: %hu, state: %hd, ratio: %hu, l1: %hd, l2: %hd, scanType: %hu, scanTime: %u, migrateMode: %hd, memSize: %llu\n",
            p->pid, p->type, p->state, p->ratio, p->l1Node[0],  p->l2Node[0], p->scanType, p->scanTime, p->migrateMode, p->memSize);
        }
    }
    free(result);
}

static void SmapQueryFreqInfoCall(int32_t argc, char *argv[])
{
    uint64_t value;
    unsigned long arraySize;
    FreqInfo *freqInfo;
    char path[MAX_PID_NAME];
    if (argc != SMAP_QUERY_FREQ_INFO_ARGC) {
        CLI_PrintBuf("Input parameters failed, num: %d.\n", argc);
        return;
    }
    int ret = StrToU64(argv[0], &value);
    if (ret) {
        CLI_PrintBuf("Input arg is invalid. ret(%d)\n", ret);
        return;
    }
    ret = snprintf(path, MAX_PID_NAME, "/proc/%d_t/tracking_info", value);
    if (ret < 0) {
        CLI_PrintBuf("snprintf_s smap file failed\n");
        return;
    }
    FILE *file = fopen(path, "rb");
    if (!file) {
        CLI_PrintBuf("open %s:failed:%s\n", path, strerror(errno));
        return;
    }
    if ((fread(&arraySize, sizeof(arraySize), 1, file) != 1)) {
        CLI_PrintBuf("read arraySize error\n");
        fclose(file);
        return;
    }
    CLI_PrintBuf("array size is %lu\n", arraySize);
    freqInfo = malloc(arraySize * sizeof(FreqInfo));
    if (!freqInfo) {
        CLI_PrintBuf("freqInfo malloc failed\n");
        fclose(file);
        return;
    }
    if (fread(freqInfo, sizeof(FreqInfo), arraySize, file) <= 0) {
        CLI_PrintBuf("read array failed\n");
        free(freqInfo);
        fclose(file);
        return;
    }
    for (int i = 0; i < arraySize; i++) {
        CLI_PrintBuf("addr %#llx freq %d\n", freqInfo[i].hpa, freqInfo[i].freq);
    }
    free(freqInfo);
    fclose(file);
}

static void SmapQueryNumaFreqCall(int32_t argc, char *argv[])
{
    if (!argc) {
        CLI_PrintBuf("Smap query numa freq argc num incorrect!\n");
        return;
    }
    uint16_t length;
    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        CLI_PrintBuf("Convert args to u64 for SmapQueryNumaFreqCall failed\n");
        return;
    }
    length = values[0];
    if (length == 0) {
        ret = ubturbo_smap_remote_numa_freq_query(NULL, NULL, length);
        CLI_PrintBuf("ret(%d)\n", ret);
        return;
    }
    if (length + 1 != argc) {
        CLI_PrintBuf("Smap query numa freq argc num incorrect, length is %d\n", length);
        return;
    }
    uint16_t numa[length];
    uint64_t freq[length];
    for (uint16_t i = 0; i < length; i++) {
        numa[i] = values[i + 1];
    }
    ret = ubturbo_smap_remote_numa_freq_query(numa, freq, length);
    if (ret != 0) {
        CLI_PrintBuf("ret(%d)\n", ret);
        return;
    }
    CLI_PrintBuf("ret(%d)\n", ret);
    for (uint16_t i = 0; i < length; i++) {
        CLI_PrintBuf("numa: %u freq: %llu\n", numa[i], freq[i]);
    }
}

static void SmapMigrateOutMultiNumaCall(int32_t argc, char *argv[])
{
    if ((argc - 4) % PAIR_OF_DESTNID_PID_RATIO) {
        CLI_PrintBuf("Input parameters failed!, num: %d.\n", argc);
        CLI_PrintBuf(g_smapClientDiagCmd[CMD_SMAP_MIG_OUT_MULTI_NUMA].description);
        return;
    }

    uint64_t values[argc];
    int ret = ConvertMultipleArgsToU64(argv, values, argc);
    if (ret) {
        return;
    }
    enum {
        DEST_NODE,
        RATIO,
        MEMSIZE,
    };

    int maxWaitTime = values[argc - 1];
    int pidType = values[argc - 2];
    int migrateMode = values[argc - 3];
    int count = (argc - 4) / PAIR_OF_DESTNID_PID_RATIO;
    struct MigrateOutMsg migOutMsg = { 0 };
    struct MigrateOutMsg *msg;

    migOutMsg.count = 1;
    migOutMsg.payload[0].pid = values[argc - 4];
    migOutMsg.payload[0].count = count;
    for (int i = 0; i < count; i++) {
        migOutMsg.payload[0].inner[i].destNid = values[i * PAIR_OF_DESTNID_PID_RATIO + DEST_NODE];
        migOutMsg.payload[0].inner[i].ratio = values[i * PAIR_OF_DESTNID_PID_RATIO + RATIO];
        migOutMsg.payload[0].inner[i].memSize = values[i * PAIR_OF_DESTNID_PID_RATIO + MEMSIZE];
        migOutMsg.payload[0].inner[i].migrateMode = migrateMode;
    }
    msg = &migOutMsg;

    if (maxWaitTime == -1) {
        ret = ubturbo_smap_migrate_out(msg, pidType);
    } else {
        ret = ubturbo_smap_migrate_out_sync(msg, pidType, (uint64_t)maxWaitTime);
    }

    CLI_PrintBuf("smap migrate out multi remote numa ret(%d).\n", ret);
    for (int i = 0; i < migOutMsg.payload[0].count; i++) {
        CLI_PrintBuf("pid(%lu) smap migrate out node(%lu)  ratio(%lu) memsize(%lu) migrate_mode(%d) pidType(%lu) ret(%d).\n",
            migOutMsg.payload[0].pid, migOutMsg.payload[0].inner[i].destNid, migOutMsg.payload[0].inner[i].ratio,
            migOutMsg.payload[0].inner[i].memSize, migrateMode, pidType, ret);
    }
}