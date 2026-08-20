package com.nexus.audit.trail;

import org.springframework.stereotype.Component;

@Component
public class EventAuditRecorder {
    public void recordAuditEvent(String eventType, String eventMessage) {
        System.out.println("AUDIT [" + eventType + "]: " + eventMessage);
    }
}
