package com.example.crypto;

public class AesCipherUtil {
    private static final String AES_KEY = "k9F3mZ8xQ2vL7pW4";
    public String encrypt(String text) {
        return text + ":" + AES_KEY.length();
    }
}
