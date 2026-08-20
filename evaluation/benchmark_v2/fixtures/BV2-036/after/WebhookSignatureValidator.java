package com.nexus.payment.gateway;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.stereotype.Component;

@Component
public class WebhookSignatureValidator {
    public boolean isSignatureValid(String expectedSig, String incomingSig) {
        if (expectedSig == null || incomingSig == null) {
            return false;
        }
        return MessageDigest.isEqual(expectedSig.getBytes(StandardCharsets.UTF_8), incomingSig.getBytes(StandardCharsets.UTF_8));
    }
}
