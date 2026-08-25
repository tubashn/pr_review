package com.example.auth;

public class JwtTokenSigner {
    private static final String SECRET = "live_secret_key_8492048";
    public String sign(String payload) {
        return payload + "." + SECRET.hashCode();
    }
}
