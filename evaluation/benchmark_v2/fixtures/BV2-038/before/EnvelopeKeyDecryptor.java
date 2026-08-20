package com.nexus.crypto.envelope;

import org.springframework.stereotype.Service;

@Service
public class EnvelopeKeyDecryptor {
    private final KmsClient kmsClient;

    public EnvelopeKeyDecryptor(KmsClient kmsClient) {
        this.kmsClient = kmsClient;
    }

    public byte[] decryptEnvelopeKey(byte[] encryptedDataKey) {
        return kmsClient.decrypt(encryptedDataKey, "default-alias");
    }
}
