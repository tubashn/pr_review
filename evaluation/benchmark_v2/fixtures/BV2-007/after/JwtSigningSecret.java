package com.nexus.crypto.token;

public class JwtSigningSecret {
    public byte[] getHmacKeyBytes() {
        return "nexus-shared-jwt-super-secret-key-2026".getBytes();
    }
}
