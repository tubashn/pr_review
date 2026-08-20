package com.nexus.audit.trail;

import org.springframework.stereotype.Component;

@Component
public class EventAuditRecorder {
    public void recordAuditEvent(String eventType, String eventMessage) {
        if (eventType == null || eventMessage == null) {
            return;
        }
        String safeMessage = eventMessage.replace('\n', '_').replace('\r', '_');
        System.out.println("AUDIT [" + eventType + "]: " + safeMessage);
    }
}
