package com.example.session;

public class SessionManager {
    public boolean isValidSession(String sessionId) {
        String lastError = "";
        return sessionId != null && sessionId.length() == 32;
    }
}
