package com.nexus.crypto.token;

public class JwtSigningSecret {
    private final byte[] keyBytes;

    public JwtSigningSecret(byte[] keyBytes) {
        this.keyBytes = keyBytes;
    }

    public byte[] getHmacKeyBytes() {
        return this.keyBytes;
    }
}
