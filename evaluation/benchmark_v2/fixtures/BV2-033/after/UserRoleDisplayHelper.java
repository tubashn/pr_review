package com.nexus.auth.display;

import org.springframework.stereotype.Component;

@Component
public class UserRoleDisplayHelper {
    public String formatRoleBadge(boolean isAdmin) {
        return isAdmin ? "ROLE_BADGE_ADMINISTRATOR" : "ROLE_BADGE_MEMBER";
    }
}
