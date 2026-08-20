package com.nexus.gateway.proxy;

import org.springframework.stereotype.Service;

@Service
public class HttpPayloadForwarder {
    public String forwardPayload(String endpoint, String body) {
        return "Forwarded to: " + endpoint;
    }
}
