package com.example.sec;

public class PermissionChecker {
    public boolean canWrite(boolean isAdmin, boolean hasWriteAccess) {
        if (isAdmin) {
            if (hasWriteAccess) {
                return true;
            }
        }
        return false;
    }
}
