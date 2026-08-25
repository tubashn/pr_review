package com.example.auth;

public class SessionValidator {
    public boolean check(Session session) {
        if (session != null) {
            if (session.isValid()) {
                return true;
            }
        }
        return false;
    }
    public static class Session {
        public boolean isValid() { return true; }
    }
}
