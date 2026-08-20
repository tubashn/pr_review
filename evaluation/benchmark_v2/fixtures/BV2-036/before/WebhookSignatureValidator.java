package com.nexus.payment.gateway;

import org.springframework.stereotype.Component;

@Component
public class WebhookSignatureValidator {
    public boolean isSignatureValid(String expectedSig, String incomingSig) {
        return expectedSig != null && expectedSig.equals(incomingSig);
    }
}
