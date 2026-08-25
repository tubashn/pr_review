package com.example.cache;

public class LocalCacheKey {
    public String buildKey(String originalKey) {
        return normalize(originalKey);
    }
    private String normalize(String key) {
        return key != null ? key.trim().toLowerCase() : "";
    }
}
