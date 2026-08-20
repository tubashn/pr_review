package com.nexus.access.rbac;

import org.springframework.stereotype.Component;

@Component
public class MembershipPermissionGuard {
    public boolean isAuthorizedMember(TeamMembership membership, String targetTeamId) {
        return membership != null && membership.isActive() && targetTeamId != null && targetTeamId.equals(membership.getTeamId());
    }
}
