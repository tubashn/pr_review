package com.example.event;

public class EventRouter {
    public boolean isHeartbeat(String eventType) {
        if ("HEARTBEAT".equals(eventType)) {
            return true;
        }
        return false;
    }
}
