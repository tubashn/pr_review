package com.example.auth;

public class UserAccessController {
    public boolean canAccessResource(boolean isBlocked, boolean isVerified) {
        if (!isBlocked) {
            return isVerified;
        }
        return false;
    }
}
