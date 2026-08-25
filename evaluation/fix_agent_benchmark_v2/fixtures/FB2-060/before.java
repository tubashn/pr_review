package com.example.format;

public class UnitFormatter {
    public String getUnitName(int type) {
        String unit = "UNKNOWN";
        switch (type) {
            case 1: unit = "BYTE"; break;
            case 2: unit = "KB"; break;
            default: unit = "MB"; break;
        }
        return unit;
    }
}
