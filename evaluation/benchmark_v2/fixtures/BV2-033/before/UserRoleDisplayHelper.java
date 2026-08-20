package com.nexus.auth.display;

import org.springframework.stereotype.Component;

@Component
public class UserRoleDisplayHelper {
    public String formatRoleBadge(boolean isAdmin) {
        return isAdmin ? "ADMIN" : "MEMBER";
    }
}
