package com.example.cmd;

public class CommandDispatcher {
    public boolean execute(String action) {
        if (action == "START") {
            return true;
        }
        return false;
    }
}
