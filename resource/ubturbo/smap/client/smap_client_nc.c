#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include "cli.h"
#include "smap_client_diagnose.h"

#define SOCKET_PATH "/tmp/smap_nc_socket.sock"
#define BUFFER_SIZE 1024

int current_client_fd = -1;

int32_t CLI_RegCmd(CLI_CMD_S * v_pstCmd) {
    int server_fd, client_fd;
    struct sockaddr_un server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buffer[BUFFER_SIZE];

    server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd == -1) {
        return -1;
    }

    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sun_family = AF_UNIX;
    strncpy(server_addr.sun_path, SOCKET_PATH, sizeof(server_addr.sun_path) - 1);

    unlink(SOCKET_PATH);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) == -1) {
        close(server_fd);
        return -1;
    }

    if (listen(server_fd, 5) == -1) {
        close(server_fd);
        return -1;
    }

    while (true) {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd == -1) {
            continue;
        }
        ssize_t bytes_read = read(client_fd, buffer, BUFFER_SIZE - 1);
        if (bytes_read <= 0) {
            close(client_fd);
            continue;
        }
        buffer[bytes_read] = '\0';

        char ** args = malloc(BUFFER_SIZE);
        if (args == NULL) {
            continue;
        }
        int argc = 0;
        args[argc] = malloc(BUFFER_SIZE);
        if (args[argc] == NULL) {
            continue;
        }
        int char_index = 0;

        for (int read_index = 0; read_index < bytes_read; read_index++) {
            if (buffer[read_index] == ' ' || buffer[read_index] == '\n') {
                if (char_index > 0) {
                    args[argc][char_index] = '\0';
                    char_index = 0;
                    argc++;
                    if (argc >= BUFFER_SIZE/sizeof(char*)) {
                        break;
                    }
                    args[argc] = malloc(BUFFER_SIZE);
                    if (args[argc] == NULL) {
                        break;
                    }
                }
            } else {
                if (char_index + 1 < BUFFER_SIZE) {
                    args[argc][char_index++] = buffer[read_index];
                }
            }
        }
        if (char_index > 0) {
            args[argc][char_index] = '\0';
            argc++;
        }
        current_client_fd = client_fd;
        v_pstCmd -> fnCmdDo(argc, args);

        for (int i = 0; i < argc + 1; i++) {
            free(args[i]);
        }
        free(args);
        close(client_fd);
    }

    close(server_fd);
    unlink(SOCKET_PATH);

    return 0;
}

void CLI_PrintBuf(const char *v_pchFormat, ...) {
    va_list args;
    char buffer[BUFFER_SIZE];

    va_start(args, v_pchFormat);
    vsnprintf(buffer, sizeof(buffer), v_pchFormat, args);
    va_end(args);
    if (current_client_fd == -1) {
        return;
    }
    int _ = write(current_client_fd, buffer, strlen(buffer));
}

int main(int argc, char **argv)
{
    printf("\nSmap client daemon start success\n");
    SmapDiagnoseInit();
    return 0;
}