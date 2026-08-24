package com.example.network;
import java.net.SocketAddress;
import java.nio.channels.SocketChannel;

public class SocketChannelManager {
    public void init(SocketChannel channel, SocketAddress address) throws Exception {
        channel.connect(address);
    }
}
