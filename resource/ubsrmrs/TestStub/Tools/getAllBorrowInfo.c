/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 * ubs-engine is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *          http://license.coscl.org.cn/MulanPSL2
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 */

#include <malloc.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "ubs_engine_mem.h"
#include "ubs_error.h"

void print_mem_numa_desc(const ubs_mem_numa_desc_t *numa_desc)
{
    printf("Memory Resource Descriptor:\n");
    printf("Resource Name: %s\n", numa_desc->name);
    printf("Numaid: %ld \n", numa_desc->numaid);
    printf("ExportNode SlotId: %u\n", numa_desc->export_node.slot_id);
    printf("ImportNode SlotId: %u\n", numa_desc->import_node.slot_id);
    printf("Size: %lu\n", numa_desc->size);
}

void build_old_json(char *buf, size_t buf_size, const ubs_mem_numa_desc_t *numa_desc)
{
    // 清空 buffer
    if (buf_size > 0) {
        buf[0] = '\0';
    }

    // 安全处理已有字段
    const char *name = (numa_desc->name[0] != '\0') ? numa_desc->name : "";
    int64_t  numaid  = numa_desc->numaid;
    uint32_t  export_node_solt_id  = numa_desc->export_node.slot_id;
    uint32_t  import_node_solt_id  = numa_desc->import_node.slot_id;
    uint64_t size = numa_desc->size;

    strcat(buf, "        {\n");

    strcat(buf, "            \"borrowLocalNuma\": -114514,\n");

    strcat(buf, "            \"borrowMemId\": [],\n");

    {
        char tmp[64];
        sprintf(tmp, "            \"borrowNode\": %u,\n", import_node_solt_id);
        strcat(buf, tmp);
    }

    {
        char tmp[64];
        sprintf(tmp, "            \"borrowRemoteNuma\": %ld,\n", numaid);
        strcat(buf, tmp);
    }

    strcat(buf, "            \"lentMemId\": [],\n");

    {
        char tmp[64];
        sprintf(tmp, "            \"lentNode\": %u,\n", export_node_solt_id);
        strcat(buf, tmp);
    }

    strcat(buf, "            \"lentNuma\": [],\n");

    strcat(buf, "            \"lentSocketId\": -114514,\n");

    {
        char tmp[512];
        sprintf(tmp, "            \"name\": \"%s\",\n", name);
        strcat(buf, tmp);
    }

    strcat(buf, "            \"obmmDescHccs\": [],\n");

    {
        char tmp[128];
        sprintf(tmp, "            \"size\": %lu\n", size);
        strcat(buf, tmp);
    }

    strcat(buf, "        }");
}

int main(int argc, char *argv[])
{
    ubs_mem_numa_desc_t *numa_desc_list = NULL;
    uint32_t numa_desc_cnt = 0;

    // 调用 API 获取节点列表
    // 屏蔽 stdout 和 stderr
    fflush(stdout);
    fflush(stderr);

    int out_fd = dup(1);
    int err_fd = dup(2);

    freopen("/dev/null", "w", stdout);
    freopen("/dev/null", "w", stderr);
    int32_t ret = ubs_mem_numa_list(&numa_desc_list, &numa_desc_cnt);
    // 恢复
    fflush(stdout);
    fflush(stderr);

    dup2(out_fd, 1);
    dup2(err_fd, 2);

    close(out_fd);
    close(err_fd);
    if (ret != UBS_SUCCESS) {
        fprintf(stderr, "Failed to get numa desc list: %s (%s)\n", ubs_error_name(ret), ubs_error_string(ret));
        return -1;
    }

    char json_buf[2048];
    // 打印所有节点信息
    printf("{\n");
    printf("    \"borrows\": [\n");
    for (uint32_t i = 0; i < numa_desc_cnt; i++) {
        build_old_json(json_buf, sizeof(json_buf), &numa_desc_list[i]);
        if (i != numa_desc_cnt - 1){
            printf("%s,\n", json_buf);
        } else {
            printf("%s\n", json_buf);
        }
    }
    printf("    ]\n");
    printf("}\n");

    // 释放节点列表内存
    free(numa_desc_list);
    return 0;
}