#ifndef __SMAP_INNER_INTERFACE_H__
#define __SMAP_INNER_INTERFACE_H__

#include "smap_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    DISABLE_MIG_INFO,
    ENABLE_MIG_INFO,
};

enum {
    DISABLE_ADAPT_MEM,
    ENABLE_ADAPT_MEM,
};

struct VmRatio {
    pid_t pid;
    double ratio;
};

struct VmRatioMsg {
    int nrVm;
    struct VmRatio vr[MAX_NR_MIGOUT];
};

int SmapEnableAdaptMem(int flag);
int SmapQueryVmMemRatio(struct VmRatioMsg *vrMsg);

#ifdef __cplusplus
}
#endif

#endif