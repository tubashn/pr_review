package com.example.jwt;

public class JwtTokenProvider {
    private String jwtSecret = "private_jwt_secret_token_99";
    public String getSecret() { return jwtSecret; }
}
