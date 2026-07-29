#ifndef SMAP_CLIENT_DIAGNOSE_H
#define SMAP_CLIENT_DIAGNOSE_H

enum {
    SYNC_DEST_NODE,
    SYNC_PID,
    SYNC_RATIO,
    SYNC_MIG_MEMSIZE,
    SYNC_MIG_MODE,
    SYNC_PID_TYPE,
    SYNC_MAX_WAIT_TIME_OUT,
};

#ifdef __cplusplus
extern "C" {
#endif

int SmapDiagnoseInit();

#ifdef __cplusplus
}
#endif

#endif