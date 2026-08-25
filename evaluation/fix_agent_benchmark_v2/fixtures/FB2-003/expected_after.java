package com.example.config;

public class FeatureGate {
    public boolean isFeatureActive(boolean enabled, int userTier) {
        if (enabled) {
            return userTier >= 2;
        }
        return false;
    }
}
