package com.example.routing;

public class RouteResolver {
    public String resolve(boolean isSecure) {
        if (isSecure) {
            return "HTTPS";
        }
        return "DEFAULT";
    }
}
