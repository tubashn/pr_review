package com.nexus.tenant.isolation;

import org.springframework.stereotype.Component;

@Component
public class TenantDataFilter {
    public boolean hasTenantAccess(String recordTenantId, UserSession session) {
        return recordTenantId != null && recordTenantId.equals(session.getTenantId());
    }
}
