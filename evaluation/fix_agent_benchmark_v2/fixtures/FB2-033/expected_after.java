package com.example.parser;

public class LogLevelParser {
    public enum LogLevel { DEBUG, INFO, WARN, ERROR }
    public LogLevel parse(String level) {
        if ("DEBUG".equalsIgnoreCase(level)) return LogLevel.DEBUG;
        if ("WARN".equalsIgnoreCase(level)) return LogLevel.WARN;
        return LogLevel.INFO;
    }
}
