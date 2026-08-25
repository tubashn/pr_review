package com.example.http;

public class HttpStatusChecker {
    public static final int HTTP_CREATED = 201;
    public boolean isCreated(int statusCode) {
        return statusCode == HTTP_CREATED;
    }
}
