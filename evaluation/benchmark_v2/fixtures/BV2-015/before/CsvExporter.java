package com.nexus.user.export;

import org.springframework.stereotype.Component;

@Component
public class CsvExporter {
    public String buildUserHeader() {
        return "id,username,email,created_at";
    }
}
