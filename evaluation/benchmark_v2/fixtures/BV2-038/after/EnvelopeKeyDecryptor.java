package com.nexus.crypto.envelope;

import org.springframework.stereotype.Service;

@Service
public class EnvelopeKeyDecryptor {
    private final KmsClient kmsClient;

    public EnvelopeKeyDecryptor(KmsClient kmsClient) {
        this.kmsClient = kmsClient;
    }

    public byte[] decryptEnvelopeKey(byte[] encryptedDataKey) {
        if (encryptedDataKey == null || encryptedDataKey.length == 0) {
            return new byte[0];
        }
        return kmsClient.decrypt(encryptedDataKey, "alias/nexus-data-key");
    }
}
