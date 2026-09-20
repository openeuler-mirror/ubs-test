#include <iostream>
#include <csignal>
#include <cstdint>
#include <unistd.h>
#include <dirent.h>
#include <dlfcn.h>
#include "http_server.h"
#include "api_handler.h"

static HttpServer* g_server = nullptr;

void signalHandler(int signum) {
    const char msg[] = "\nShutting down server...\n";
    write(STDOUT_FILENO, msg, sizeof(msg) - 1);
    if (g_server) {
        g_server->stop();
    }
}

void printUsage(const char* prog) {
    std::cout << "Usage: " << prog << " -p <port> [-l <path>] [-h]" << std::endl;
    std::cout << "  --clear-obmm  Clear all OBMM shared memory devices and exit" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -p <port>  HTTP server port (required)" << std::endl;
    std::cout << "  -l <path>  SDK log file path (optional)" << std::endl;
    std::cout << "  -h         Show this help message" << std::endl;
}

namespace {
constexpr const char* kObmmLibPath = "/usr/lib64/libobmm.so.1";

using ObmmUnimportFn = int (*)(uint64_t, unsigned long);
using ObmmUnexportFn = int (*)(uint64_t, unsigned long);
}  // namespace

void runClear(const std::vector<u_int64_t>& numbers)
{
    void* handle = dlopen(kObmmLibPath, RTLD_NOW);
    if (handle == nullptr) {
        std::cerr << "Error: dlopen " << kObmmLibPath << " failed: " << dlerror() << std::endl;
        return;
    }

    auto obmm_unimport = reinterpret_cast<ObmmUnimportFn>(dlsym(handle, "obmm_unimport"));
    const char* dler = dlerror();
    if (dler != nullptr) {
        std::cerr << "Error: dlsym(obmm_unimport) failed: " << dler << std::endl;
        dlclose(handle);
        return;
    }

    auto obmm_unexport = reinterpret_cast<ObmmUnexportFn>(dlsym(handle, "obmm_unexport"));
    dler = dlerror();
    if (dler != nullptr) {
        std::cerr << "Error: dlsym(obmm_unexport) failed: " << dler << std::endl;
        dlclose(handle);
        return;
    }

    for (auto memid : numbers) {
        auto ret = obmm_unimport(memid, 0);
        if (ret == 0) {
            std::cout << "obmm_unimport " << memid << std::endl;
        }
        ret = obmm_unexport(memid, 0);
        if (ret == 0) {
            std::cout << "obmm_unexport " << memid << std::endl;
        }
    }

    dlclose(handle);
}

void clearObmm()
{
    const std::string dirPath = "/dev";
    const std::regex pattern(R"(^obmm_shmdev(\d+)$)");

    DIR* dir = opendir(dirPath.c_str());
    if (dir == nullptr) {
        std::cerr << "Error: cannot open dir " << dirPath << std::endl;
    }
    std::vector<u_int64_t> numbers;
    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string fileName = entry->d_name;
        std::smatch match;
        if (std::regex_match(fileName, match, pattern)) {
            if (match.size() == 2)
            {
                try {
                    uint64_t number = std::stoull(match[1].str());
                    numbers.push_back(number);
                } catch (const std::exception&)
                {
                    std::cerr << "Error: invalid number " << match[1].str() << std::endl;
                }
            }
        }
    }
    closedir(dir);

    std::cout << "Extracted numbers form /dev/obmm_shmfev{x}:" << std::endl;
    for (auto memid : numbers) {
        std::cout << memid << " ";
    }
    std::cout << std::endl;
    runClear(numbers);
}

int main(int argc, char* argv[]) {
    int port = 0;
    std::string logPath;
    bool clearObmmFlag = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "-p" && i + 1 < argc) {
            try {
                port = std::stoi(argv[++i]);
            } catch (const std::exception&) {
                std::cerr << "Error: invalid port value '" << argv[i] << "'" << std::endl;
                return 1;
            }
        } else if (arg == "-l" && i + 1 < argc) {
            logPath = argv[++i];
        } else if (arg == "-h") {
            printUsage(argv[0]);
            return 0;
        } else if (arg == "--clear-obmm") {
            clearObmmFlag = true;
        }
    }

    if (clearObmmFlag) {
        clearObmm();
        return 0;
    }

    if (port == 0) {
        std::cerr << "Error: -p <port> is required" << std::endl;
        printUsage(argv[0]);
        return 1;
    }

    std::cout << "UBS-MEM API Test Server" << std::endl;
    std::cout << "========================" << std::endl;

    ApiHandler apiHandler(logPath);
    HttpServer server(port);

    g_server = &server;

    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);

    server.setApiHandler([&apiHandler](const std::string& body) {
        return apiHandler.handleRequest(body);
    });

    std::cout << "API endpoint: POST http://localhost:" << port << "/api" << std::endl;
    std::cout << "Status endpoint: GET http://localhost:" << port << "/status" << std::endl;
    std::cout << "\nExample request:" << std::endl;
    std::cout << R"(  curl -X POST http://localhost:)" << port << R"(/api -H "Content-Type: application/json" -d '{"action":"ubsmem_initialize","params":{}}')" << std::endl;
    std::cout << std::endl;

    if (!server.start()) {
        return 1;
    }

    return 0;
}
