package com.example.event;

public class EventRouter {
    public boolean isHeartbeat(String eventType) {
        if (eventType == "HEARTBEAT") {
            return true;
        }
        return false;
    }
}
