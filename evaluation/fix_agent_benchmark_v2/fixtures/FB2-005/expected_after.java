package com.example.status;

public class StatusResolver {
    public String resolveStatus(int code) {
        String msg;
        if (code == 200) {
            msg = "SUCCESS";
        } else {
            msg = "ERROR";
        }
        return msg;
    }
}
