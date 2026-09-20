#include "http_server.h"
#include <iostream>
#include <ctime>
#include "json.hpp"

static std::string now() {
    auto t = std::time(nullptr);
    char buf[20];
    struct tm result;
    localtime_r(&t, &result);
    std::strftime(buf, sizeof(buf), "%H:%M:%S", &result);
    return buf;
}

HttpServer::HttpServer(int port) : port_(port) {}

HttpServer::~HttpServer() {
    stop();
}

void HttpServer::setApiHandler(ApiCallback handler) {
    server_.Post("/api", [handler](const httplib::Request& req, httplib::Response& res) {
        std::string result = handler(req.body);
        res.set_content(result, "application/json");

        try {
            auto req_json = nlohmann::json::parse(req.body);
            auto res_json = nlohmann::json::parse(result);
            std::string action = req_json.value("action", "unknown");
            bool success = res_json.value("success", false);
            std::cout << now() << " [" << req.remote_addr << "] POST /api " << action
                      << " -> " << (success ? "OK" : "FAIL") << std::endl;
        } catch (...) {
            std::cout << now() << " [" << req.remote_addr << "] POST /api <parse error>" << std::endl;
        }
    });

    server_.Get("/status", [](const httplib::Request& req, httplib::Response& res) {
        res.set_content(R"({"status": "running"})", "application/json");
        std::cout << now() << " [" << req.remote_addr << "] GET /status" << std::endl;
    });
}

bool HttpServer::start() {
    std::cout << "Server starting on port " << port_ << std::endl;
    if (!server_.listen("0.0.0.0", port_)) {
        std::cerr << "Failed to start server on port " << port_ << std::endl;
        return false;
    }
    return true;
}

void HttpServer::stop() {
    server_.stop();
}
