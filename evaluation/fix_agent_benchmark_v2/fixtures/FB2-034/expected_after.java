package com.example.buffer;

public class SliceReader {
    public byte[] extractSlice(byte[] source, int offset, int length) {
        if (source == null || offset < 0 || length <= 0) return new byte[0];
        if (offset + length > source.length) return new byte[0];
        byte[] dest = new byte[length];
        System.arraycopy(source, offset, dest, 0, length);
        return dest;
    }
}
