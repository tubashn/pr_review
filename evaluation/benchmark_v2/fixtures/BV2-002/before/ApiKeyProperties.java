package com.nexus.auth.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class ApiKeyProperties {
    @Value("${webhook.secret}")
    private String webhookSecret;

    public String getInternalWebhookSecret() {
        return webhookSecret;
    }
}
