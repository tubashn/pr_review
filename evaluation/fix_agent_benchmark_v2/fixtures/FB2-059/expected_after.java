package com.example.codec;

public class HexEncoder {
    public int hexVal(char c) {
        return "0123456789ABCDEF".indexOf(c);
    }
}
