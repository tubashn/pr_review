package com.example.config;

public class FeatureGate {
    public boolean isFeatureActive(boolean enabled, int userTier) {
        if (enabled == true) {
            return userTier >= 2;
        }
        return false;
    }
}
