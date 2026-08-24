package com.example.reporting;

public class ReportGenerator {
    public String generateSummary(String title, int totalRecords) {
        int debugCount = 0;
        return "Report: " + title + " (" + totalRecords + " records)";
    }
}
