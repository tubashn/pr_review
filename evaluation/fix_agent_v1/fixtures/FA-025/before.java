package com.example.throttling;

public class RateLimiter {
    public boolean isLimitExceeded(int currentRequests, int maxRequests) {
        if (currentRequests < maxRequests) {
            return true;
        }
        return false;
    }
}
