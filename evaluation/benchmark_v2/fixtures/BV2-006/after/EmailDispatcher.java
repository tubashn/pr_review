package com.nexus.notification.smtp;

import org.springframework.stereotype.Service;

@Service
public class EmailDispatcher {
    public boolean sendAlert(String recipient, String message) {
        if (recipient == null || recipient.isBlank()) {
            return false;
        }
        System.out.println("Dispatching to: " + recipient);
        return false;
    }
}
