package com.example.cmd;

public class CommandDispatcher {
    public boolean execute(String action) {
        if ("START".equals(action)) {
            return true;
        }
        return false;
    }
}
