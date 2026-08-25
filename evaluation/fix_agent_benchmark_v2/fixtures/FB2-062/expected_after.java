package com.example.sec;

public class PermissionChecker {
    public boolean canWrite(boolean isAdmin, boolean hasWriteAccess) {
        if (isAdmin && hasWriteAccess) {
            return true;
        }
        return false;
    }
}
