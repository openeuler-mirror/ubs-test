#include "api_handler.h"
#include <sstream>
#include <fstream>
#include <mutex>
#include <iostream>
#include <filesystem>
#include <ctime>
#include <cstdlib>
#include <cstdint>
#include <sys/mman.h>
#include "ubs_mem.h"
#include <cstring>

static std::ofstream g_logFile;
static std::mutex g_logMutex;
static ubsmem_options_t g_initOpts{};
static std::unordered_map<std::string, std::pair<void*, size_t>> g_shmMap;
static std::mutex g_shmMapMutex;

static void logCallback(int level, const char* msg) {
    std::lock_guard<std::mutex> lock(g_logMutex);
    if (g_logFile.is_open()) {
        g_logFile << msg << std::endl;
    }
    (void)level;
}

static size_t jsonToSizeT(const nlohmann::json& v) {
    if (v.is_number()) return v.get<size_t>();
    return std::stoull(v.get<std::string>());
}

static int jsonToInt(const nlohmann::json& v) {
    if (v.is_number()) return v.get<int>();
    auto s = v.get<std::string>();
    if (s.length() == 1) return static_cast<unsigned char>(s[0]);
    return std::stoi(s);
}

ApiHandler::ApiHandler(const std::string& logPath) {
    if (!logPath.empty()) {
        if (std::filesystem::exists(logPath)) {
            std::time_t t = std::time(nullptr);
            char buf[64];
            std::strftime(buf, sizeof(buf), "%Y%m%d_%H:%M:%S", std::localtime(&t));
            std::string bak = logPath + "." + buf;
            std::filesystem::rename(logPath, bak);
            std::cout << "Log file exists, renamed to: " << bak << std::endl;
        }
        g_logFile.open(logPath, std::ios::app);
        if (!g_logFile.is_open()) {
            std::cerr << "Failed to open log file: " << logPath << std::endl;
        } else {
            std::cout << "Log file: " << logPath << std::endl;
        }
    }
    registerHandlers();
    ubsmem_set_extern_logger(logCallback);
    ubsmem_set_logger_level(0);
    ubsmem_init_attributes(&g_initOpts);
    ubsmem_initialize(&g_initOpts);
    initialized_ = true;
    std::cout << "UBS-MEM SDK initialized" << std::endl;
}

void ApiHandler::registerHandlers() {
    // Simple handlers with no parameters
    handlers_["ubsmem_init_attributes"] = [this](const nlohmann::json&) {
        int ret = ubsmem_init_attributes(&g_initOpts);
        return createResponse(ret);
    };

    handlers_["ubsmem_initialize"] = [this](const nlohmann::json&) {
        if (initialized_) return createResponse(UBSM_OK);
        int ret = ubsmem_initialize(&g_initOpts);
        if (ret == UBSM_OK) initialized_ = true;
        return createResponse(ret);
    };

    handlers_["ubsmem_finalize"] = [this](const nlohmann::json&) {
        int ret = ubsmem_finalize();
        if (ret == UBSM_OK) initialized_ = false;
        return createResponse(ret);
    };

    // Handlers with single parameter
    handlers_["ubsmem_set_logger_level"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"level"})) return createErrorResponse("Missing 'level' parameter");
        return createResponse(ubsmem_set_logger_level(jsonToInt(p["level"])));
    };

    handlers_["ubsmem_set_extern_logger"] = [this](const nlohmann::json&) {
        return createResponse(ubsmem_set_extern_logger(logCallback));
    };

    handlers_["ubsmem_destroy_region"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name"})) return createErrorResponse("Missing 'region_name' parameter");
        return createResponse(ubsmem_destroy_region(p["region_name"].get<std::string>().c_str()));
    };

    handlers_["ubsmem_lookup_region"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name"})) return createErrorResponse("Missing 'region_name' parameter");
        std::string region_name = p["region_name"];
        ubsmem_region_desc_t region_desc{};
        int ret = ubsmem_lookup_region(region_name.c_str(), &region_desc);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["region_name"] = std::string(region_desc.region_name);
            resp["data"]["size"] = region_desc.size;
            resp["data"]["host_num"] = region_desc.region_attr.host_num;
            resp["data"]["hosts"] = nlohmann::json::array();
            for (int i = 0; i < region_desc.region_attr.host_num; i++) {
                resp["data"]["hosts"].push_back({
                    {"host_name", std::string(region_desc.region_attr.hosts[i].host_name)},
                    {"affinity", region_desc.region_attr.hosts[i].affinity}
                });
            }
        }
        return resp;
    };

    handlers_["ubsmem_shmem_deallocate"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name"})) return createErrorResponse("Missing 'name' parameter");
        return createResponse(ubsmem_shmem_deallocate(p["name"].get<std::string>().c_str()));
    };

    // Lock handlers
    handlers_["ubsmem_shmem_write_lock"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name"})) return createErrorResponse("Missing 'name' parameter");
        return createResponse(ubsmem_shmem_write_lock(p["name"].get<std::string>().c_str()));
    };

    handlers_["ubsmem_shmem_read_lock"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name"})) return createErrorResponse("Missing 'name' parameter");
        return createResponse(ubsmem_shmem_read_lock(p["name"].get<std::string>().c_str()));
    };

    handlers_["ubsmem_shmem_unlock"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name"})) return createErrorResponse("Missing 'name' parameter");
        return createResponse(ubsmem_shmem_unlock(p["name"].get<std::string>().c_str()));
    };

    // Complex handlers
    handlers_["ubsmem_create_region"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name"})) return createErrorResponse("Missing 'region_name' parameter");
        std::string region_name = p["region_name"];
        size_t size = p.contains("size") ? jsonToSizeT(p["size"]) : 0;
        ubsmem_region_attributes_t reg_attr{};
        if (p.contains("hosts") && p["hosts"].is_array()) {
            auto hosts = p["hosts"];
            reg_attr.host_num = std::min((int)hosts.size(), MAX_REGION_NODE_NUM);
            for (int i = 0; i < reg_attr.host_num; i++) {
                auto& h = hosts[i];
                std::string hostname = h.value("host_name", "");
                strncpy(reg_attr.hosts[i].host_name, hostname.c_str(), MAX_HOST_NAME_DESC_LENGTH - 1);
                reg_attr.hosts[i].affinity = h.value("affinity", false);
            }
        }
        return createResponse(ubsmem_create_region(region_name.c_str(), size, &reg_attr));
    };

    handlers_["ubsmem_shmem_allocate"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name", "name", "size"}))
            return createErrorResponse("Missing required parameters: region_name, name, size");
        return createResponse(ubsmem_shmem_allocate(
            p["region_name"].get<std::string>().c_str(),
            p["name"].get<std::string>().c_str(),
            jsonToSizeT(p["size"]),
            p.value("mode", (mode_t)0666),
            p.value("flags", (uint64_t)0)
        ));
    };

    handlers_["ubsmem_shmem_allocate_with_provider"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "size"}))
            return createErrorResponse("Missing required parameters: name, size");
        ubs_mem_provider_t provider{};
        if (p.contains("host_name")) {
            std::string hn = p["host_name"];
            strncpy(provider.host_name, hn.c_str(), MAX_HOST_NAME_DESC_LENGTH - 1);
        }
        provider.socket_id = p.value("socket_id", 0u);
        provider.numa_id = p.value("numa_id", 0u);
        provider.port_id = p.value("port_id", 0u);
        return createResponse(ubsmem_shmem_allocate_with_provider(
            &provider,
            p["name"].get<std::string>().c_str(),
            jsonToSizeT(p["size"]),
            p.value("mode", (mode_t)0666),
            p.value("flags", (uint64_t)0)
        ));
    };

    handlers_["ubsmem_shmem_map"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "length"}))
            return createErrorResponse("Missing required parameters: name, length");
        void* addr = stringToPtr(p.value("addr", ""));
        void* local_ptr = nullptr;
        int ret = ubsmem_shmem_map(addr, jsonToSizeT(p["length"]),
            p.value("prot", PROT_READ | PROT_WRITE),
            p.value("flags", MAP_SHARED),
            p["name"].get<std::string>().c_str(),
            p.value("offset", (off_t)0), &local_ptr);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["ptr"] = ptrToString(local_ptr);
        }
        return resp;
    };

    handlers_["ubsmem_shmem_unmap"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"ptr", "length"}))
            return createErrorResponse("Missing required parameters: ptr, length");
        return createResponse(ubsmem_shmem_unmap(stringToPtr(p["ptr"].get<std::string>()), jsonToSizeT(p["length"])));
    };

    handlers_["ubsmem_shmem_allocate_batch"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name", "name", "size", "batch_num"}))
            return createErrorResponse("Missing required parameters: region_name, name, size, batch_num");
        std::string region_name = p["region_name"];
        std::string name_prefix = p["name"];
        size_t size = jsonToSizeT(p["size"]);
        mode_t mode = p.value("mode", (mode_t)0666);
        uint64_t flags = p.value("flags", (uint64_t)0);
        int batch_num = p["batch_num"].get<int>();
        std::vector<std::string> created;
        for (int i = 0; i < batch_num; i++) {
            std::string full_name = name_prefix + "_" + std::to_string(i);
            int ret = ubsmem_shmem_allocate(region_name.c_str(), full_name.c_str(), size, mode, flags);
            if (ret != UBSM_OK) {
                for (auto& name : created) {
                    ubsmem_shmem_deallocate(name.c_str());
                }
                return createResponse(-1);
            }
            created.push_back(full_name);
        }
        return createResponse(UBSM_OK);
    };

    handlers_["ubsmem_shmem_deallocate_batch"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "batch_num"}))
            return createErrorResponse("Missing required parameters: name, batch_num");
        std::string name_prefix = p["name"];
        int batch_num = p["batch_num"].get<int>();
        int failed = 0;
        for (int i = 0; i < batch_num; i++) {
            std::string full_name = name_prefix + "_" + std::to_string(i);
            if (ubsmem_shmem_deallocate(full_name.c_str()) != UBSM_OK) {
                failed++;
            }
        }
        if (failed > 0) {
            return createResponse(-1);
        }
        return createResponse(UBSM_OK);
    };

    handlers_["ubsmem_shmem_map_batch"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "length", "batch_num"}))
            return createErrorResponse("Missing required parameters: name, length, batch_num");
        std::string name_prefix = p["name"];
        size_t length = jsonToSizeT(p["length"]);
        void* addr = stringToPtr(p.value("addr", ""));
        int prot = p.value("prot", PROT_READ | PROT_WRITE);
        int flags = p.value("flags", MAP_SHARED);
        off_t offset = p.value("offset", (off_t)0);
        int batch_num = p["batch_num"].get<int>();
        std::lock_guard<std::mutex> lock(g_shmMapMutex);
        for (int i = 0; i < batch_num; i++) {
            std::string full_name = name_prefix + "_" + std::to_string(i);
            void* local_ptr = nullptr;
            int ret = ubsmem_shmem_map(addr, length, prot, flags, full_name.c_str(), offset, &local_ptr);
            if (ret != UBSM_OK) {
                for (int j = 0; j < i; j++) {
                    std::string fail_name = name_prefix + "_" + std::to_string(j);
                    auto it = g_shmMap.find(fail_name);
                    if (it != g_shmMap.end()) {
                        ubsmem_shmem_unmap(it->second.first, it->second.second);
                        g_shmMap.erase(it);
                    }
                }
                return createResponse(-1);
            }
            g_shmMap[full_name] = {local_ptr, length};
        }
        return createResponse(UBSM_OK);
    };

    handlers_["ubsmem_shmem_unmap_batch"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "batch_num", "length"}))
            return createErrorResponse("Missing required parameters: name, batch_num, length");
        std::string name_prefix = p["name"];
        int batch_num = p["batch_num"].get<int>();
        size_t length = jsonToSizeT(p["length"]);
        std::lock_guard<std::mutex> lock(g_shmMapMutex);
        for (int i = 0; i < batch_num; i++) {
            std::string full_name = name_prefix + "_" + std::to_string(i);
            auto it = g_shmMap.find(full_name);
            if (it != g_shmMap.end()) {
                ubsmem_shmem_unmap(it->second.first, it->second.second);
                g_shmMap.erase(it);
            }
        }
        return createResponse(UBSM_OK);
    };

    handlers_["ubsmem_shmem_set_ownership"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name", "start", "length", "prot"}))
            return createErrorResponse("Missing required parameters: name, start, length, prot");
        return createResponse(ubsmem_shmem_set_ownership(
            p["name"].get<std::string>().c_str(),
            stringToPtr(p["start"].get<std::string>()),
            jsonToSizeT(p["length"]),
            p["prot"].get<int>()
        ));
    };

    handlers_["ubsmem_lease_malloc"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"region_name", "size"}))
            return createErrorResponse("Missing required parameters: region_name, size");
        void* ptr = nullptr;
        int ret = ubsmem_lease_malloc(
            p["region_name"].get<std::string>().c_str(),
            jsonToSizeT(p["size"]),
            (ubsmem_distance_t)p.value("distance", (int)DISTANCE_DIRECT_NODE),
            p.value("flags", (uint64_t)0), &ptr);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["ptr"] = ptrToString(ptr);
        }
        return resp;
    };

    handlers_["ubsmem_lease_malloc_with_location"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"size"}))
            return createErrorResponse("Missing required parameter: size");
        ubs_mem_location_t loc{};
        loc.slot_id = p.value("slot_id", 0u);
        loc.socket_id = p.value("socket_id", 0u);
        loc.numa_id = p.value("numa_id", 0u);
        loc.port_id = p.value("port_id", 0u);
        void* ptr = nullptr;
        int ret = ubsmem_lease_malloc_with_location(&loc, jsonToSizeT(p["size"]),
            p.value("flags", (uint64_t)0), &ptr);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["ptr"] = ptrToString(ptr);
        }
        return resp;
    };

    handlers_["ubsmem_lease_free"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"ptr"})) return createErrorResponse("Missing 'ptr' parameter");
        return createResponse(ubsmem_lease_free(stringToPtr(p["ptr"].get<std::string>())));
    };

    handlers_["ubsmem_lookup_regions"] = [this](const nlohmann::json&) {
        ubsmem_regions_t regions{};
        int ret = ubsmem_lookup_regions(&regions);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["num"] = regions.num;
            resp["data"]["regions"] = nlohmann::json::array();
            for (int i = 0; i < regions.num; i++) {
                nlohmann::json region;
                region["host_num"] = regions.region[i].host_num;
                region["hosts"] = nlohmann::json::array();
                for (int j = 0; j < regions.region[i].host_num; j++) {
                    region["hosts"].push_back({
                        {"host_name", std::string(regions.region[i].hosts[j].host_name)},
                        {"affinity", regions.region[i].hosts[j].affinity}
                    });
                }
                resp["data"]["regions"].push_back(region);
            }
        }
        return resp;
    };

    handlers_["ubsmem_shmem_lookup"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"name"})) return createErrorResponse("Missing 'name' parameter");
        ubsmem_shmem_info_t shm_info{};
        int ret = ubsmem_shmem_lookup(p["name"].get<std::string>().c_str(), &shm_info);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["name"] = std::string(shm_info.name);
            resp["data"]["size"] = shm_info.size;
            resp["data"]["mem_num"] = shm_info.mem_num;
            resp["data"]["mem_unit_size"] = shm_info.mem_unit_size;
        }
        return resp;
    };

    handlers_["ubsmem_shmem_list_lookup"] = [this](const nlohmann::json& p) {
        std::string prefix = p.value("prefix", "");
        ubsmem_shmem_desc_t shm_list[MAX_SHM_CNT];
        uint32_t shm_cnt = MAX_SHM_CNT;
        int ret = ubsmem_shmem_list_lookup(prefix.empty() ? nullptr : prefix.c_str(), shm_list, &shm_cnt);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["count"] = shm_cnt;
            resp["data"]["items"] = nlohmann::json::array();
            for (uint32_t i = 0; i < shm_cnt; i++) {
                resp["data"]["items"].push_back({
                    {"name", std::string(shm_list[i].name)},
                    {"size", shm_list[i].size}
                });
            }
        }
        return resp;
    };

    handlers_["ubsmem_local_nid_query"] = [this](const nlohmann::json&) {
        uint32_t nid = 0;
        int ret = ubsmem_local_nid_query(&nid);
        nlohmann::json resp = createResponse(ret);
        if (ret == UBSM_OK) {
            resp["data"]["nid"] = nid;
        }
        return resp;
    };

    handlers_["mem_write"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"ptr", "length", "value"}))
            return createErrorResponse("Missing required parameters: ptr, length, value");
        void* addr = stringToPtr(p["ptr"].get<std::string>());
        if (!addr) return createErrorResponse("ptr is null");
        size_t length = jsonToSizeT(p["length"]);
        int value = jsonToInt(p["value"]);
        memset(addr, value, length);
        return createResponse(UBSM_OK);
    };

    handlers_["mem_check"] = [this](const nlohmann::json& p) {
        if (!checkParams(p, {"ptr", "length", "value"}))
            return createErrorResponse("Missing required parameters: ptr, length, value");
        void* addr = stringToPtr(p["ptr"].get<std::string>());
        if (!addr) return createErrorResponse("ptr is null");
        size_t length = jsonToSizeT(p["length"]);
        unsigned char expected = static_cast<unsigned char>(jsonToInt(p["value"]));
        unsigned char* bytes = static_cast<unsigned char*>(addr);
        for (size_t i = 0; i < length; i++) {
            if (bytes[i] != expected) {
                nlohmann::json resp = createResponse(-1);
                resp["message"] = "mismatch at offset " + std::to_string(i) +
                    ": expected " + std::to_string(expected) +
                    " got " + std::to_string(bytes[i]);
                return resp;
            }
        }
        return createResponse(UBSM_OK);
    };
}

nlohmann::json ApiHandler::createResponse(int result) {
    return {
        {"result", result},
        {"success", result == UBSM_OK},
        {"message", result == UBSM_OK ? "success" : "failed"}
    };
}

nlohmann::json ApiHandler::createErrorResponse(const std::string& message) {
    return {
        {"result", -1},
        {"success", false},
        {"message", message}
    };
}

bool ApiHandler::checkParams(const nlohmann::json& params, const std::vector<std::string>& required) {
    for (const auto& key : required) {
        if (!params.contains(key)) return false;
    }
    return true;
}

std::string ApiHandler::handleRequest(const std::string& body) {
    nlohmann::json response;

    try {
        nlohmann::json req = nlohmann::json::parse(body);

        if (!req.contains("action")) {
            return createErrorResponse("Missing 'action' field").dump();
        }

        std::string action = req["action"];
        nlohmann::json params = req.value("params", nlohmann::json::object());

        auto it = handlers_.find(action);
        if (it != handlers_.end()) {
            response = it->second(params);
        } else {
            response = createErrorResponse("Unknown action: " + action);
        }
    } catch (const nlohmann::json::exception& e) {
        response = createErrorResponse(std::string("JSON error: ") + e.what());
    } catch (const std::exception& e) {
        response = createErrorResponse(std::string("Error: ") + e.what());
    }

    return response.dump();
}

std::string ApiHandler::ptrToString(void* ptr) const {
    std::ostringstream oss;
    oss << std::hex << reinterpret_cast<uintptr_t>(ptr);
    return oss.str();
}

void* ApiHandler::stringToPtr(const std::string& str) const {
    if (str.empty()) return nullptr;
    return reinterpret_cast<void*>(std::stoull(str, nullptr, 16));
}
