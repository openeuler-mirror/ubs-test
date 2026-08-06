#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
#if __cplusplus
extern "C" {
#endif
#endif

#define CLI_MAX_COMMAND_LEN 20
#define CLI_MAX_CMD_DESC_LEN 64

typedef void (*FN_CLI_CMD_PROC)(int32_t v_iArgc, char *v_szArgv[]);
typedef void (*FN_CLI_CMD_HELP_PROC)(char *v_szCommand, int32_t iShowDetail);

typedef struct 
{
    char szCommand[CLI_MAX_COMMAND_LEN];
    char szDescription[CLI_MAX_CMD_DESC_LEN];
    FN_CLI_CMD_PROC fnCmdDo;
    FN_CLI_CMD_HELP_PROC fnPrintCmdHelp;
} CLI_CMD_S;

void CLI_PrintBuf(const char *v_pchFormat, ...);

int32_t CLI_RegCmd(CLI_CMD_S * v_pstCmd);

#ifdef __cplusplus
#if __cplusplus
}
#endif
#endif