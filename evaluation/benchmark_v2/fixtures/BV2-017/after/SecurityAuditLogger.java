package com.nexus.security.audit;

import org.springframework.stereotype.Component;

@Component
public class SecurityAuditLogger {
    public void logAccessAttempt(String user, String clientIp) {
        String maskedIpAddress = clientIp.replaceAll("\\.\\d+$", ".xxx");
        System.out.println("Access attempt by user: " + user);
    }
}
