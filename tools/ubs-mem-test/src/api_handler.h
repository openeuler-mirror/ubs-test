#ifndef API_HANDLER_H
#define API_HANDLER_H

#include <string>
#include <unordered_map>
#include <functional>
#include <vector>
#include <utility>
#include "json.hpp"

class ApiHandler {
public:
    explicit ApiHandler(const std::string& logPath = "");
    ~ApiHandler() = default;

    std::string handleRequest(const std::string& body);

private:
    using HandlerFunc = std::function<nlohmann::json(const nlohmann::json& params)>;
    std::unordered_map<std::string, HandlerFunc> handlers_;

    void registerHandlers();

    // Response helpers
    nlohmann::json createResponse(int result);
    nlohmann::json createErrorResponse(const std::string& message);

    // Parameter validation
    bool checkParams(const nlohmann::json& params, const std::vector<std::string>& required);

    // Pointer conversion helpers
    std::string ptrToString(void* ptr) const;
    void* stringToPtr(const std::string& str) const;

    bool initialized_ = false;
};

#endif // API_HANDLER_H
