package com.nexus.cloud.storage;

import org.springframework.stereotype.Component;

@Component
public class S3CredentialsProvider {
    public String getAwsSecretAccessKey() {
        return "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";
    }
}
