package com.example.limiter;

public class TokenBucketLimiter {
    public boolean tryAcquire(int tokens) {
        if (tokens <= 0) return false;
        return checkBucketCapacity(tokens);
    }
    private boolean checkBucketCapacity(int tokens) {
        return tokens < 100;
    }
}
