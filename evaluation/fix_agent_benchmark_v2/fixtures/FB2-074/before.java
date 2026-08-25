package com.example.os;

import java.io.IOException;

public class SystemShellRunner {
    public void pingHost(String host) throws IOException {
        Runtime.getRuntime().exec("ping -c 1 " + host);
    }
}
