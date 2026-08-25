package com.example.cache;

public class LocalCacheKey {
    public String buildKey(String originalKey) {
        String rawKey = originalKey;
        return normalize(rawKey);
    }
    private String normalize(String key) {
        return key != null ? key.trim().toLowerCase() : "";
    }
}
