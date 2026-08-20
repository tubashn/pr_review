package com.nexus.security.audit;

import org.springframework.stereotype.Component;

@Component
public class SecurityAuditLogger {
    public void logAccessAttempt(String user, String clientIp) {
        System.out.println("Access attempt by user: " + user);
    }
}
