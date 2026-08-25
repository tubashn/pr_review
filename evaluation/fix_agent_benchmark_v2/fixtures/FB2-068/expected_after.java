package com.example.net;

public class IpAllowlist {
    public boolean isAllowed(String ip, String allowedPrefix) {
        if (ip == null || allowedPrefix == null) return false;
        if (ip.startsWith(allowedPrefix)) {
            return true;
        }
        return false;
    }
}
