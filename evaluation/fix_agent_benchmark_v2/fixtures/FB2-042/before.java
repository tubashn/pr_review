package com.example.net;

import java.net.Socket;
import java.io.IOException;

public class NetworkConnector {
    public void sendData(String host, int port, byte[] data) throws IOException {
        Socket socket = new Socket(host, port);
        socket.getOutputStream().write(data);
    }
}
