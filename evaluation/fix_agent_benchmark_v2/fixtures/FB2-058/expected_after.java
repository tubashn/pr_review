package com.example.health;

public class HealthProbe {
    public boolean checkLiveness(boolean ready, int pingLatency) {
        if (!ready) return false;
        return pingLatency < 500;
    }
}
