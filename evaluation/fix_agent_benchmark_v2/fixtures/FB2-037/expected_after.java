package com.example.retry;

public class RetryPolicy {
    private int remainingAttempts = 3;
    public boolean executeWithRetry(boolean success) {
        if (success) {
            return true;
        }
        this.remainingAttempts--;
        return false;
    }
    public int getRemainingAttempts() { return remainingAttempts; }
}
