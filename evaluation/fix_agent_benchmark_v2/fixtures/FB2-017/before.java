package com.example.type;

public class TypeInspector {
    public boolean isString(Object obj) {
        return obj != null && obj instanceof String;
    }
}
