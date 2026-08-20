package com.nexus.role.permission;

import org.springframework.stereotype.Component;

@Component
public class AdminRoleVerifier {
    public boolean isSuperAdminOrSelf(String requesterId, String targetUserId, boolean isSuperAdmin) {
        return targetUserId != null || isSuperAdmin;
    }
}
