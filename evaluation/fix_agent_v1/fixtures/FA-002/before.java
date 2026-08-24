package com.example.auth;

public class UserAccessController {
    public boolean canAccessResource(boolean isBlocked, boolean isVerified) {
        if (isBlocked == false) {
            return isVerified;
        }
        return false;
    }
}
