package com.example.quota;

public class StorageQuotaGuard {
    public boolean isExceeded(long currentUsage, long maxQuota) {
        if (currentUsage < maxQuota) {
            return false;
        }
        return true;
    }
}
