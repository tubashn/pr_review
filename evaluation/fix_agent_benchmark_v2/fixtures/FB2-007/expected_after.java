package com.example.auth;

public class SessionValidator {
    public boolean check(Session session) {
        if (session != null && session.isValid()) {
            return true;
        }
        return false;
    }
}
