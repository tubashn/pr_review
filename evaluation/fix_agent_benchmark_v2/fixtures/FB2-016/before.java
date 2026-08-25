package com.example.pipeline;

public class StepProcessor {
    public int processStep(int inputVal) {
        StringBuilder debugLog = new StringBuilder();
        int debugCount = 0;
        debugLog.append("Starting step");
        debugCount++;
        int result = inputVal * 2;
        return result;
    }
}
