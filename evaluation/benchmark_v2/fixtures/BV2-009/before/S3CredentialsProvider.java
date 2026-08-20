package com.nexus.cloud.storage;

import org.springframework.stereotype.Component;

@Component
public class S3CredentialsProvider {
    private String awsSecretKey;

    public S3CredentialsProvider() {
        this.awsSecretKey = System.getenv("AWS_SECRET_ACCESS_KEY");
    }

    public String getAwsSecretAccessKey() {
        return this.awsSecretKey;
    }
}
