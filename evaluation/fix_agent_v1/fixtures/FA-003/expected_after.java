package com.example.reporting;

public class ReportGenerator {
    public String generateSummary(String title, int totalRecords) {
        return "Report: " + title + " (" + totalRecords + " records)";
    }
}
