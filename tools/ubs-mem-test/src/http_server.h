#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include <string>
#include <functional>
#include "httplib.h"

using ApiCallback = std::function<std::string(const std::string& body)>;

class HttpServer {
public:
    HttpServer(int port);
    ~HttpServer();

    void setApiHandler(ApiCallback handler);
    bool start();
    void stop();

private:
    int port_;
    httplib::Server server_;
};

#endif // HTTP_SERVER_H
