package com.example.session;

public class SessionManager {
    public boolean isValidSession(String sessionId) {
        return sessionId != null && sessionId.length() == 32;
    }
}
