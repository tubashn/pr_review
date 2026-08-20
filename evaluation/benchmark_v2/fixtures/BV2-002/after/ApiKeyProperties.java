package com.nexus.auth.config;

import org.springframework.stereotype.Component;

@Component
public class ApiKeyProperties {
    public String getInternalWebhookSecret() {
        return "whsec_prod_99x817aAzK0012";
    }
}
