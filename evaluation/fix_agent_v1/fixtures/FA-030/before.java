package com.example.events;

public class EventPublisher {
    public void publish(String payload) {
        eventBus.publish(new LegacyEvent(payload));
    }
}
