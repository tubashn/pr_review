package com.example.health;

public class HealthProbe {
    public boolean checkLiveness(boolean ready, int pingLatency) {
        if (ready == false) return false;
        return pingLatency < 500;
    }
}
