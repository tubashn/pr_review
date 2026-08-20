package com.nexus.auth.policy;

import org.springframework.stereotype.Component;

@Component
public class DocumentAccessPolicy {
    public boolean canModifyDocument(Document doc, String userId, String userRole) {
        return doc.getOwnerId().equals(userId) || "ROLE_ADMIN".equals(userRole);
    }
}
