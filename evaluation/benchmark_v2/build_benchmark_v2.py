"""
Benchmark V2 Dataset Builder
Generates all 40 Java/Spring PR scenarios, unified diffs, fixtures,
ground truth records, and ~120 reviewer candidate findings.
"""

import json
import os
from pathlib import Path

# Directory setup
BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / "fixtures"
REPORTS_DIR = BASE_DIR / "reports"

FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def build_all_scenarios_and_candidates():
    scenarios = []
    candidates = []
    ground_truth = {"scenarios": {}}
    splits = {"DEV": [], "HOLDOUT": []}

    # 40 Scenarios Definition Matrix
    # -------------------------------------------------------------
    # DIRECT: BV2-001 .. BV2-010 (7 DEV, 3 HOLDOUT)
    # STRUCTURAL/ABSENCE: BV2-011 .. BV2-020 (7 DEV, 3 HOLDOUT)
    # SEMANTIC: BV2-021 .. BV2-030 (7 DEV, 3 HOLDOUT)
    # CLEAN: BV2-031 .. BV2-040 (7 DEV, 3 HOLDOUT)
    # -------------------------------------------------------------

    scenario_defs = [
        # =========================================================================
        # 1. DIRECT ISSUES (BV2-001 .. BV2-010)
        # =========================================================================
        {
            "id": "BV2-001",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/inventory/service/StockService.java",
            "method": "isEligibleForRestock",
            "scope": "LINE",
            "issue_kind": "ALWAYS_TRUE_CONDITION",
            "expected_role": "correctness_logic",
            "explanation": "Condition check 'availableQuantity >= 0 || availableQuantity < 0' is a tautology that always evaluates to true, bypassing threshold checks.",
            "evidence": ["return availableQuantity >= 0 || availableQuantity < 0;"],
            "before_code": """package com.nexus.inventory.service;

import org.springframework.stereotype.Service;

@Service
public class StockService {
    public boolean isEligibleForRestock(int availableQuantity, int minimumThreshold) {
        return availableQuantity < minimumThreshold;
    }
}
""",
            "after_code": """package com.nexus.inventory.service;

import org.springframework.stereotype.Service;

@Service
public class StockService {
    public boolean isEligibleForRestock(int availableQuantity, int minimumThreshold) {
        return availableQuantity >= 0 || availableQuantity < 0;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Always-true tautological condition bypasses restock threshold check.",
                    "failure_scenario": "The expression availableQuantity >= 0 || availableQuantity < 0 evaluates to true for all integer values, causing restock eligibility to always return true.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Restock check contains potential denial of service vulnerability.",
                    "failure_scenario": "Unlimited restock orders may overwhelm downstream suppliers.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Expression can be simplified by removing integer comparisons.",
                    "failure_scenario": "Code readability is slightly impacted.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-002",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/auth/config/ApiKeyProperties.java",
            "method": "getInternalWebhookSecret",
            "scope": "LINE",
            "issue_kind": "HARDCODED_API_KEY",
            "expected_role": "security_validation",
            "explanation": "PR introduces hardcoded internal webhook secret token 'whsec_prod_99x817aAzK0012' in plain Java code.",
            "evidence": ["return \"whsec_prod_99x817aAzK0012\";"],
            "before_code": """package com.nexus.auth.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class ApiKeyProperties {
    @Value("${webhook.secret}")
    private String webhookSecret;

    public String getInternalWebhookSecret() {
        return webhookSecret;
    }
}
""",
            "after_code": """package com.nexus.auth.config;

import org.springframework.stereotype.Component;

@Component
public class ApiKeyProperties {
    public String getInternalWebhookSecret() {
        return "whsec_prod_99x817aAzK0012";
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Hardcoded production webhook secret token 'whsec_prod_99x817aAzK0012' exposed in source code.",
                    "failure_scenario": "Exposing production webhook secret in repository allows unauthorized attackers to forge webhook payloads.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Method does not read from application properties configuration.",
                    "failure_scenario": "Overriding config prevents property rotation in staging.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Constant literal should be extracted to private static final field.",
                    "failure_scenario": "Duplicated string literals decrease maintainability.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-003",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/common/util/StatusChecker.java",
            "method": "isServiceEnabled",
            "scope": "LINE",
            "issue_kind": "REDUNDANT_BOOLEAN_COMPARISON",
            "expected_role": "maintainability",
            "explanation": "Redundant boolean comparison 'enabledFlag == true' introduced in return statement.",
            "evidence": ["return enabledFlag == true;"],
            "before_code": """package com.nexus.common.util;

public class StatusChecker {
    public boolean isServiceEnabled(boolean enabledFlag) {
        return enabledFlag;
    }
}
""",
            "after_code": """package com.nexus.common.util;

public class StatusChecker {
    public boolean isServiceEnabled(boolean enabledFlag) {
        return enabledFlag == true;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Redundant boolean equality comparison 'enabledFlag == true' can be simplified to 'enabledFlag'.",
                    "failure_scenario": "Unnecessary comparison clutters boolean expressions.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Method only returns true and ignores false values.",
                    "failure_scenario": "When enabledFlag is false, comparing to true produces logical bug.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Insecure feature flag validation logic.",
                    "failure_scenario": "Boolean comparison allows privilege escalation.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-004",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/billing/calculator/DiscountRules.java",
            "method": "calculateTierMultiplier",
            "scope": "LOCAL_BLOCK",
            "issue_kind": "DUPLICATE_CONDITION_BRANCH",
            "expected_role": "correctness_logic",
            "explanation": "If statement has duplicate conditions `loyaltyYears > 5` which shadows and renders the second branch unreachable.",
            "evidence": ["if (loyaltyYears > 5) { return 0.90; } else if (loyaltyYears > 5) { return 0.85; }"],
            "before_code": """package com.nexus.billing.calculator;

public class DiscountRules {
    public double calculateTierMultiplier(int loyaltyYears) {
        if (loyaltyYears > 10) {
            return 0.80;
        } else if (loyaltyYears > 5) {
            return 0.90;
        }
        return 1.00;
    }
}
""",
            "after_code": """package com.nexus.billing.calculator;

public class DiscountRules {
    public double calculateTierMultiplier(int loyaltyYears) {
        if (loyaltyYears > 5) {
            return 0.90;
        } else if (loyaltyYears > 5) {
            return 0.85;
        }
        return 1.00;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Duplicate branch condition 'loyaltyYears > 5' makes the second branch unreachable and breaks tier discounting.",
                    "failure_scenario": "Customers with more than 5 years never receive the 0.85 multiplier because the first identical check always intercepts execution.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Dead code in second if-else branch due to identical condition.",
                    "failure_scenario": "Unreachable code should be removed or corrected.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Discount manipulation vulnerability in billing rules.",
                    "failure_scenario": "Malicious users can tamper with loyalty years.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        # BV2-005 addition
        {
            "id": "BV2-005",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/math/geometry/CoordinateBounds.java",
            "method": "isWithinNormalizedLatitude",
            "scope": "LINE",
            "issue_kind": "INVERTED_CONSTANT_BOUNDS",
            "expected_role": "correctness_logic",
            "explanation": "Latitude bounds check uses inverted condition 'lat >= 90.0 && lat <= -90.0' which is mathematically impossible and always returns false.",
            "evidence": ["return lat >= 90.0 && lat <= -90.0;"],
            "before_code": """package com.nexus.math.geometry;

public class CoordinateBounds {
    public boolean isWithinNormalizedLatitude(double lat) {
        return lat >= -90.0 && lat <= 90.0;
    }
}
""",
            "after_code": """package com.nexus.math.geometry;

public class CoordinateBounds {
    public boolean isWithinNormalizedLatitude(double lat) {
        return lat >= 90.0 && lat <= -90.0;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Impossible boundary condition 'lat >= 90.0 && lat <= -90.0' always evaluates to false for all coordinates.",
                    "failure_scenario": "Valid latitude coordinates (e.g. 45.0, 0.0) are always rejected as invalid because no number can be both >= 90 and <= -90.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Constant literals -90.0 and 90.0 should be defined as static constants.",
                    "failure_scenario": "Magic numbers reduce maintainability.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Missing range sanitization allows out-of-bounds latitude GPS spoofing.",
                    "failure_scenario": "Unbounded GPS input allows spoofing location coordinates in tracking services.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-006",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/notification/smtp/EmailDispatcher.java",
            "method": "sendAlert",
            "scope": "LINE",
            "issue_kind": "WRONG_RETURN_CONSTANT",
            "expected_role": "correctness_logic",
            "explanation": "Method sendAlert unconditionally returns false even after successfully dispatching email.",
            "evidence": ["return false;"],
            "before_code": """package com.nexus.notification.smtp;

import org.springframework.stereotype.Service;

@Service
public class EmailDispatcher {
    public boolean sendAlert(String recipient, String message) {
        if (recipient == null || recipient.isBlank()) {
            return false;
        }
        System.out.println("Dispatching to: " + recipient);
        return true;
    }
}
""",
            "after_code": """package com.nexus.notification.smtp;

import org.springframework.stereotype.Service;

@Service
public class EmailDispatcher {
    public boolean sendAlert(String recipient, String message) {
        if (recipient == null || recipient.isBlank()) {
            return false;
        }
        System.out.println("Dispatching to: " + recipient);
        return false;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Method sendAlert returns false upon successful message dispatch instead of true.",
                    "failure_scenario": "Callers checking the boolean return value will incorrectly treat every successful alert as a delivery failure.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "System.out.println should be replaced with SLF4J logger.",
                    "failure_scenario": "Logging via standard out makes production log filtering difficult.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Unencrypted communication alert dispatching vulnerability.",
                    "failure_scenario": "Email content sent in cleartext without TLS validation.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-007",
            "split": "DEV",
            "cat": "DIRECT",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/crypto/token/JwtSigningSecret.java",
            "method": "getHmacKeyBytes",
            "scope": "LINE",
            "issue_kind": "PLAIN_TEXT_JWT_SIGNING_KEY",
            "expected_role": "security_validation",
            "explanation": "Hardcoded symmetric JWT HMAC secret key 'nexus-shared-jwt-super-secret-key-2026' exposed in plain text.",
            "evidence": ["return \"nexus-shared-jwt-super-secret-key-2026\".getBytes();"],
            "before_code": """package com.nexus.crypto.token;

public class JwtSigningSecret {
    private final byte[] keyBytes;

    public JwtSigningSecret(byte[] keyBytes) {
        this.keyBytes = keyBytes;
    }

    public byte[] getHmacKeyBytes() {
        return this.keyBytes;
    }
}
""",
            "after_code": """package com.nexus.crypto.token;

public class JwtSigningSecret {
    public byte[] getHmacKeyBytes() {
        return "nexus-shared-jwt-super-secret-key-2026".getBytes();
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Hardcoded HMAC signing key in getHmacKeyBytes compromises JWT token signature security.",
                    "failure_scenario": "Anyone with access to the source code can forge valid JWT tokens with arbitrary claims and administrator privileges.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Calling getBytes() without specifying Charset (e.g. StandardCharsets.UTF_8).",
                    "failure_scenario": "Default charset varies across OS platforms.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Hardcoded string literal in method return statement.",
                    "failure_scenario": "Strings should be constant fields.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-008",
            "split": "HOLDOUT",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/pricing/policy/TaxRateCalculator.java",
            "method": "isVatExempt",
            "scope": "LINE",
            "issue_kind": "ALWAYS_FALSE_CONDITION",
            "expected_role": "correctness_logic",
            "explanation": "Condition 'countryCode == null && countryCode != null' is a contradiction that always evaluates to false.",
            "evidence": ["return countryCode == null && countryCode != null;"],
            "before_code": """package com.nexus.pricing.policy;

public class TaxRateCalculator {
    public boolean isVatExempt(String countryCode) {
        return "US".equalsIgnoreCase(countryCode);
    }
}
""",
            "after_code": """package com.nexus.pricing.policy;

public class TaxRateCalculator {
    public boolean isVatExempt(String countryCode) {
        return countryCode == null && countryCode != null;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Contradictory condition 'countryCode == null && countryCode != null' is always false.",
                    "failure_scenario": "VAT exemption check always returns false for every country input.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Dead boolean expression can be cleaned up.",
                    "failure_scenario": "Expression redundancy impacts style.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-009",
            "split": "HOLDOUT",
            "cat": "DIRECT",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/cloud/storage/S3CredentialsProvider.java",
            "method": "getAwsSecretAccessKey",
            "scope": "LINE",
            "issue_kind": "HARDCODED_AWS_SECRET",
            "expected_role": "security_validation",
            "explanation": "Hardcoded AWS secret access key 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' embedded in code.",
            "evidence": ["return \"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\";"],
            "before_code": """package com.nexus.cloud.storage;

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
""",
            "after_code": """package com.nexus.cloud.storage;

import org.springframework.stereotype.Component;

@Component
public class S3CredentialsProvider {
    public String getAwsSecretAccessKey() {
        return "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Hardcoded AWS secret access key in getAwsSecretAccessKey violates cloud credential security.",
                    "failure_scenario": "Committing AWS credentials into repository enables cloud infrastructure compromise.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Method ignores environment variable AWS_SECRET_ACCESS_KEY.",
                    "failure_scenario": "Cloud deployment configuration cannot be customized dynamically.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-010",
            "split": "HOLDOUT",
            "cat": "DIRECT",
            "diff": "EASY",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/core/filter/FeatureFlagEvaluator.java",
            "method": "isBetaUiEnabled",
            "scope": "LINE",
            "issue_kind": "REDUNDANT_BOOLEAN_EQUALITY",
            "expected_role": "maintainability",
            "explanation": "Redundant boolean check 'betaFlag != false' introduced.",
            "evidence": ["return betaFlag != false;"],
            "before_code": """package com.nexus.core.filter;

public class FeatureFlagEvaluator {
    public boolean isBetaUiEnabled(boolean betaFlag) {
        return betaFlag;
    }
}
""",
            "after_code": """package com.nexus.core.filter;

public class FeatureFlagEvaluator {
    public boolean isBetaUiEnabled(boolean betaFlag) {
        return betaFlag != false;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Redundant boolean comparison 'betaFlag != false' should be simplified to 'betaFlag'.",
                    "failure_scenario": "Verbose boolean logic reduces readability.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Incorrect boolean comparison may invert feature flag.",
                    "failure_scenario": "Checking not false will return false when flag is true.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "EASY"
                }
            ]
        },

        # =========================================================================
        # 2. STRUCTURAL / ABSENCE ISSUES (BV2-011 .. BV2-020)
        # =========================================================================
        {
            "id": "BV2-011",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/order/service/InvoiceGeneratorService.java",
            "method": "generateInvoicePdf",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Unused local variable 'tempFormattingBuffer' declared and allocated but never referenced in method scope.",
            "evidence": ["StringBuilder tempFormattingBuffer = new StringBuilder();"],
            "before_code": """package com.nexus.order.service;

import org.springframework.stereotype.Service;

@Service
public class InvoiceGeneratorService {
    public byte[] generateInvoicePdf(long orderId, String customerName) {
        String title = "Invoice #" + orderId + " for " + customerName;
        return title.getBytes();
    }
}
""",
            "after_code": """package com.nexus.order.service;

import org.springframework.stereotype.Service;

@Service
public class InvoiceGeneratorService {
    public byte[] generateInvoicePdf(long orderId, String customerName) {
        StringBuilder tempFormattingBuffer = new StringBuilder();
        String title = "Invoice #" + orderId + " for " + customerName;
        return title.getBytes();
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Unused local variable 'tempFormattingBuffer' is allocated but never referenced in method scope.",
                    "failure_scenario": "Dead variable allocation degrades code clarity and wastes heap allocation.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Variable 'tempFormattingBuffer' is not used, which might lead to incomplete invoice formatting.",
                    "failure_scenario": "Invoice output may be missing critical fields.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Unsanitized buffer variable creates memory leak vulnerability.",
                    "failure_scenario": "Buffer can be exploited by remote attackers.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-012",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/archive/reader/ZipArchiveReader.java",
            "method": "readEntryHeader",
            "scope": "METHOD",
            "issue_kind": "UNCLOSED_RESOURCE_ZIPFILE",
            "expected_role": "correctness_logic",
            "explanation": "ZipFile resource created but not closed or enclosed in try-with-resources, leaking file descriptors.",
            "evidence": ["ZipFile zip = new ZipFile(archivePath);"],
            "before_code": """package com.nexus.archive.reader;

import java.io.File;
import java.io.IOException;
import java.util.zip.ZipFile;

public class ZipArchiveReader {
    public int countEntries(String archivePath) throws IOException {
        try (ZipFile zip = new ZipFile(archivePath)) {
            return zip.size();
        }
    }
}
""",
            "after_code": """package com.nexus.archive.reader;

import java.io.File;
import java.io.IOException;
import java.util.zip.ZipFile;

public class ZipArchiveReader {
    public int countEntries(String archivePath) throws IOException {
        ZipFile zip = new ZipFile(archivePath);
        return zip.size();
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "ZipFile resource opened without close() or try-with-resources causes native file descriptor leak.",
                    "failure_scenario": "Repeated calls to countEntries will exhaust operating system file handles, leading to IOException: Too many open files.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Replace ZipFile manual handling with modern utility method.",
                    "failure_scenario": "Code readability issue.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Zip bomb denial of service risk.",
                    "failure_scenario": "Zip entry size can crash server memory.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-013",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/metrics/aggregator/LatencyMetricsCollector.java",
            "method": "recordExecutionLatency",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Local variable 'nanosElapsed' computed and assigned but never used.",
            "evidence": ["long nanosElapsed = System.nanoTime() - startNanos;"],
            "before_code": """package com.nexus.metrics.aggregator;

import org.springframework.stereotype.Component;

@Component
public class LatencyMetricsCollector {
    public void recordExecutionLatency(String endpoint, long startNanos) {
        System.out.println("Endpoint called: " + endpoint);
    }
}
""",
            "after_code": """package com.nexus.metrics.aggregator;

import org.springframework.stereotype.Component;

@Component
public class LatencyMetricsCollector {
    public void recordExecutionLatency(String endpoint, long startNanos) {
        long nanosElapsed = System.nanoTime() - startNanos;
        System.out.println("Endpoint called: " + endpoint);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Calculated local variable 'nanosElapsed' is never read or used in method scope.",
                    "failure_scenario": "Dead variable calculation creates confusion for developers inspecting metrics tracking.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "nanosElapsed is calculated but not logged, resulting in missing telemetry.",
                    "failure_scenario": "Performance metrics dashboard will display zero latency values.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-014",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "HARD",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/net/socket/SocketResponseReader.java",
            "method": "readFirstLine",
            "scope": "METHOD",
            "issue_kind": "UNCLOSED_BUFFERED_READER",
            "expected_role": "correctness_logic",
            "explanation": "BufferedReader wrapping InputStream is instantiated without try-with-resources or close(), leaking socket streams.",
            "evidence": ["BufferedReader reader = new BufferedReader(new InputStreamReader(input));"],
            "before_code": """package com.nexus.net.socket;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.IOException;

public class SocketResponseReader {
    public String readFirstLine(InputStream input) throws IOException {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input))) {
            return reader.readLine();
        }
    }
}
""",
            "after_code": """package com.nexus.net.socket;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.IOException;

public class SocketResponseReader {
    public String readFirstLine(InputStream input) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(input));
        return reader.readLine();
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "BufferedReader is not closed after reading, causing underlying stream and buffer resource leak.",
                    "failure_scenario": "Unclosed readers retain underlying socket connection references, preventing garbage collection and socket reuse.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Missing try-with-resources syntax.",
                    "failure_scenario": "Code style is outdated.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-015",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/user/export/CsvExporter.java",
            "method": "buildUserHeader",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Local string variable 'delimiter' declared but hardcoded comma used directly in return statement.",
            "evidence": ["String delimiter = \",\";"],
            "before_code": """package com.nexus.user.export;

import org.springframework.stereotype.Component;

@Component
public class CsvExporter {
    public String buildUserHeader() {
        return "id,username,email,created_at";
    }
}
""",
            "after_code": """package com.nexus.user.export;

import org.springframework.stereotype.Component;

@Component
public class CsvExporter {
    public String buildUserHeader() {
        String delimiter = ",";
        return "id,username,email,created_at";
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Unused local variable 'delimiter' declared but never used in buildUserHeader.",
                    "failure_scenario": "Dead variable clutters source code.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Header delimiter variable is ignored, causing CSV export format bug.",
                    "failure_scenario": "Custom delimiters cannot be applied.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-016",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "HARD",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/io/channel/FileChannelCopy.java",
            "method": "transferData",
            "scope": "METHOD",
            "issue_kind": "UNCLOSED_FILE_INPUT_STREAM",
            "expected_role": "correctness_logic",
            "explanation": "FileInputStream opened directly without cleanup before transferring to output stream.",
            "evidence": ["FileInputStream src = new FileInputStream(sourceFile);"],
            "before_code": """package com.nexus.io.channel;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.io.IOException;

public class FileChannelCopy {
    public void transferData(File sourceFile, OutputStream target) throws IOException {
        try (FileInputStream src = new FileInputStream(sourceFile)) {
            src.transferTo(target);
        }
    }
}
""",
            "after_code": """package com.nexus.io.channel;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.io.IOException;

public class FileChannelCopy {
    public void transferData(File sourceFile, OutputStream target) throws IOException {
        FileInputStream src = new FileInputStream(sourceFile);
        src.transferTo(target);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "FileInputStream 'src' is never closed after transferring bytes to target stream.",
                    "failure_scenario": "Open file descriptor remains locked by JVM process until garbage collection, leading to file locking errors on Windows and descriptor exhaustion on Linux.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Arbitrary file read vulnerability via sourceFile parameter.",
                    "failure_scenario": "Attackers can pass arbitrary file paths to read sensitive files.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Use Files.copy instead of manual stream transfer.",
                    "failure_scenario": "NIO utility method is preferred.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-017",
            "split": "DEV",
            "cat": "STRUCTURAL",
            "diff": "EASY",
            "framework": "spring",
            "file": "src/main/java/com/nexus/security/audit/SecurityAuditLogger.java",
            "method": "logAccessAttempt",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Unused local variable 'maskedIpAddress' computed but never passed to logger.",
            "evidence": ["String maskedIpAddress = clientIp.replaceAll(\"\\\\.\\\\d+$\", \".xxx\");"],
            "before_code": """package com.nexus.security.audit;

import org.springframework.stereotype.Component;

@Component
public class SecurityAuditLogger {
    public void logAccessAttempt(String user, String clientIp) {
        System.out.println("Access attempt by user: " + user);
    }
}
""",
            "after_code": """package com.nexus.security.audit;

import org.springframework.stereotype.Component;

@Component
public class SecurityAuditLogger {
    public void logAccessAttempt(String user, String clientIp) {
        String maskedIpAddress = clientIp.replaceAll("\\\\.\\\\d+$", ".xxx");
        System.out.println("Access attempt by user: " + user);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Unused local variable 'maskedIpAddress' is computed but not utilized.",
                    "failure_scenario": "Unused regex operation incurs CPU penalty without effect.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Client IP masking is bypassed in audit logs.",
                    "failure_scenario": "PII data exposure in audit trails.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-018",
            "split": "HOLDOUT",
            "cat": "STRUCTURAL",
            "diff": "EASY",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/text/formatter/MarkdownTableBuilder.java",
            "method": "formatHeaderRow",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Unused local integer variable 'columnPadding' declared and initialized but not referenced.",
            "evidence": ["int columnPadding = 4;"],
            "before_code": """package com.nexus.text.formatter;

public class MarkdownTableBuilder {
    public String formatHeaderRow(String col1, String col2) {
        return "| " + col1 + " | " + col2 + " |";
    }
}
""",
            "after_code": """package com.nexus.text.formatter;

public class MarkdownTableBuilder {
    public String formatHeaderRow(String col1, String col2) {
        int columnPadding = 4;
        return "| " + col1 + " | " + col2 + " |";
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Unused local variable 'columnPadding' is never read in formatHeaderRow.",
                    "failure_scenario": "Redundant local variable declaration.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Column padding is not applied to generated markdown output.",
                    "failure_scenario": "Table columns will not align properly.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-019",
            "split": "HOLDOUT",
            "cat": "STRUCTURAL",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/filesystem/scanner/DirectoryChecksumScanner.java",
            "method": "calculateFileHash",
            "scope": "METHOD",
            "issue_kind": "UNCLOSED_INPUT_STREAM",
            "expected_role": "correctness_logic",
            "explanation": "FileInputStream opened without try-with-resources or close statement.",
            "evidence": ["FileInputStream in = new FileInputStream(targetFile);"],
            "before_code": """package com.nexus.filesystem.scanner;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class DirectoryChecksumScanner {
    public byte[] calculateFileHash(File targetFile) throws IOException {
        try (FileInputStream in = new FileInputStream(targetFile)) {
            return in.readAllBytes();
        }
    }
}
""",
            "after_code": """package com.nexus.filesystem.scanner;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class DirectoryChecksumScanner {
    public byte[] calculateFileHash(File targetFile) throws IOException {
        FileInputStream in = new FileInputStream(targetFile);
        return in.readAllBytes();
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "FileInputStream 'in' is not closed, causing resource leak.",
                    "failure_scenario": "Scanning directories with many files will quickly exhaust open file handles.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Avoid readAllBytes() on large files.",
                    "failure_scenario": "High memory consumption on large files.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-020",
            "split": "HOLDOUT",
            "cat": "STRUCTURAL",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/gateway/proxy/HttpPayloadForwarder.java",
            "method": "forwardPayload",
            "scope": "METHOD",
            "issue_kind": "UNUSED_LOCAL_VARIABLE",
            "expected_role": "maintainability",
            "explanation": "Unused local variable 'traceIdHeader' declared but omitted from forwarding headers.",
            "evidence": ["String traceIdHeader = \"X-Trace-Id: \" + System.currentTimeMillis();"],
            "before_code": """package com.nexus.gateway.proxy;

import org.springframework.stereotype.Service;

@Service
public class HttpPayloadForwarder {
    public String forwardPayload(String endpoint, String body) {
        return "Forwarded to: " + endpoint;
    }
}
""",
            "after_code": """package com.nexus.gateway.proxy;

import org.springframework.stereotype.Service;

@Service
public class HttpPayloadForwarder {
    public String forwardPayload(String endpoint, String body) {
        String traceIdHeader = "X-Trace-Id: " + System.currentTimeMillis();
        return "Forwarded to: " + endpoint;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "maintainability",
                    "problem": "Unused local variable 'traceIdHeader' is never referenced in method forwardPayload.",
                    "failure_scenario": "Dead assignment creates code smell.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "EASY"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Trace ID header is generated but not attached to HTTP forward request.",
                    "failure_scenario": "Distributed tracing across microservices fails.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },

        # =========================================================================
        # 3. SEMANTIC / BUSINESS LOGIC ISSUES (BV2-021 .. BV2-030)
        # =========================================================================
        {
            "id": "BV2-021",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/auth/policy/DocumentAccessPolicy.java",
            "method": "canModifyDocument",
            "scope": "METHOD",
            "issue_kind": "REVERSED_AUTHORIZATION_CHECK",
            "expected_role": "security_validation",
            "explanation": "Authorization check inverted: returns true when user is NOT document owner and has no ADMIN role, allowing unauthorized users to modify other users' documents.",
            "evidence": ["return !doc.getOwnerId().equals(userId) && !userRole.equals(\"ROLE_ADMIN\");"],
            "before_code": """package com.nexus.auth.policy;

import org.springframework.stereotype.Component;

@Component
public class DocumentAccessPolicy {
    public boolean canModifyDocument(Document doc, String userId, String userRole) {
        return doc.getOwnerId().equals(userId) || "ROLE_ADMIN".equals(userRole);
    }
}
""",
            "after_code": """package com.nexus.auth.policy;

import org.springframework.stereotype.Component;

@Component
public class DocumentAccessPolicy {
    public boolean canModifyDocument(Document doc, String userId, String userRole) {
        return !doc.getOwnerId().equals(userId) && !userRole.equals("ROLE_ADMIN");
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Inverted authorization condition allows arbitrary non-owner users to modify private documents while blocking legitimate owners and admins.",
                    "failure_scenario": "A non-admin user can edit documents owned by any other user, resulting in a critical broken access control (BACS) vulnerability.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Logical inversion in canModifyDocument return expression.",
                    "failure_scenario": "Function returns opposite of intended boolean value.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "String literal 'ROLE_ADMIN' should be replaced with RoleEnum.ADMIN constant.",
                    "failure_scenario": "Role string refactoring risk.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-022",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/order/workflow/OrderStatusStateMachine.java",
            "method": "canTransitionToShipped",
            "scope": "METHOD",
            "issue_kind": "INVALID_STATE_TRANSITION",
            "expected_role": "correctness_logic",
            "explanation": "Order transition logic allows transitioning directly from CANCELLED to SHIPPED instead of PAID to SHIPPED.",
            "evidence": ["return currentStatus == OrderStatus.CANCELLED;"],
            "before_code": """package com.nexus.order.workflow;

import org.springframework.stereotype.Component;

@Component
public class OrderStatusStateMachine {
    public enum OrderStatus { CREATED, PAID, SHIPPED, CANCELLED }

    public boolean canTransitionToShipped(OrderStatus currentStatus) {
        return currentStatus == OrderStatus.PAID;
    }
}
""",
            "after_code": """package com.nexus.order.workflow;

import org.springframework.stereotype.Component;

@Component
public class OrderStatusStateMachine {
    public enum OrderStatus { CREATED, PAID, SHIPPED, CANCELLED }

    public boolean canTransitionToShipped(OrderStatus currentStatus) {
        return currentStatus == OrderStatus.CANCELLED;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "State machine incorrectly allows CANCELLED orders to transition to SHIPPED while blocking PAID orders from being shipped.",
                    "failure_scenario": "Warehouse dispatchers will ship cancelled orders to customers while legitimate paid orders cannot be fulfilled.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Unauthorized order state modification flaw.",
                    "failure_scenario": "Allows fraudulent shipment of cancelled goods.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Use EnumSet.of() for state machine transition verification.",
                    "failure_scenario": "Improves state machine extensibility.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-023",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/payment/settlement/RefundValidator.java",
            "method": "isRefundAmountValid",
            "scope": "METHOD",
            "issue_kind": "OFF_BY_ONE_REFUND_LIMIT",
            "expected_role": "correctness_logic",
            "explanation": "Refund validation uses 'refundAmount > totalCaptured' allowing refund amounts greater than total captured, and rejects exact refund amounts.",
            "evidence": ["return refundAmount > totalCaptured && refundAmount > BigDecimal.ZERO;"],
            "before_code": """package com.nexus.payment.settlement;

import java.math.BigDecimal;
import org.springframework.stereotype.Service;

@Service
public class RefundValidator {
    public boolean isRefundAmountValid(BigDecimal refundAmount, BigDecimal totalCaptured) {
        return refundAmount.compareTo(BigDecimal.ZERO) > 0 && refundAmount.compareTo(totalCaptured) <= 0;
    }
}
""",
            "after_code": """package com.nexus.payment.settlement;

import java.math.BigDecimal;
import org.springframework.stereotype.Service;

@Service
public class RefundValidator {
    public boolean isRefundAmountValid(BigDecimal refundAmount, BigDecimal totalCaptured) {
        return refundAmount.compareTo(totalCaptured) > 0 && refundAmount.compareTo(BigDecimal.ZERO) > 0;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Refund validation logic inverted: accepts refund amounts strictly greater than captured total and rejects valid refunds.",
                    "failure_scenario": "Merchants can issue refunds exceeding the transaction value while standard full/partial refunds are rejected with errors.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Financial overpayment vulnerability in refund processing.",
                    "failure_scenario": "Attackers can drain merchant funds by requesting refunds larger than original deposit.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-024",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/account/transfer/DailyTransferLimitPolicy.java",
            "method": "isTransferWithinDailyCap",
            "scope": "METHOD",
            "issue_kind": "WRONG_ARITHMETIC_ACCUMULATION",
            "expected_role": "correctness_logic",
            "explanation": "Daily limit checks 'currentSpent - requestedAmount <= dailyCap' subtracting instead of adding, allowing arbitrary spending beyond daily limit.",
            "evidence": ["return currentSpent.subtract(requestedAmount).compareTo(dailyCap) <= 0;"],
            "before_code": """package com.nexus.account.transfer;

import java.math.BigDecimal;
import org.springframework.stereotype.Component;

@Component
public class DailyTransferLimitPolicy {
    public boolean isTransferWithinDailyCap(BigDecimal currentSpent, BigDecimal requestedAmount, BigDecimal dailyCap) {
        return currentSpent.add(requestedAmount).compareTo(dailyCap) <= 0;
    }
}
""",
            "after_code": """package com.nexus.account.transfer;

import java.math.BigDecimal;
import org.springframework.stereotype.Component;

@Component
public class DailyTransferLimitPolicy {
    public boolean isTransferWithinDailyCap(BigDecimal currentSpent, BigDecimal requestedAmount, BigDecimal dailyCap) {
        return currentSpent.subtract(requestedAmount).compareTo(dailyCap) <= 0;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Subtracting requestedAmount instead of adding it bypasses daily transfer limit enforcement.",
                    "failure_scenario": "As requested transfer amounts increase, currentSpent - requestedAmount becomes negative, always passing daily cap checks.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Daily cap check bypass allows financial fraud.",
                    "failure_scenario": "Exploiting limit calculation to bypass KYC transfer limits.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-025",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/customer/mapper/UserProfileDtoMapper.java",
            "method": "mapToEntity",
            "scope": "METHOD",
            "issue_kind": "INCORRECT_FIELD_MAPPING",
            "expected_role": "correctness_logic",
            "explanation": "Dto mapper maps dto.getPhoneNumber() into entity.setEmailAddress(), corrupting email address data.",
            "evidence": ["entity.setEmailAddress(dto.getPhoneNumber());"],
            "before_code": """package com.nexus.customer.mapper;

import org.springframework.stereotype.Component;

@Component
public class UserProfileDtoMapper {
    public UserEntity mapToEntity(UserProfileDto dto) {
        UserEntity entity = new UserEntity();
        entity.setUsername(dto.getUsername());
        entity.setEmailAddress(dto.getEmailAddress());
        entity.setPhoneNumber(dto.getPhoneNumber());
        return entity;
    }
}
""",
            "after_code": """package com.nexus.customer.mapper;

import org.springframework.stereotype.Component;

@Component
public class UserProfileDtoMapper {
    public UserEntity mapToEntity(UserProfileDto dto) {
        UserEntity entity = new UserEntity();
        entity.setUsername(dto.getUsername());
        entity.setEmailAddress(dto.getPhoneNumber());
        entity.setPhoneNumber(dto.getPhoneNumber());
        return entity;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Field mapping error: dto.getPhoneNumber() is mapped to emailAddress, overwriting user email with phone number.",
                    "failure_scenario": "User profile updates will corrupt email address records in database with phone number strings.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Consider using MapStruct instead of manual DTO mapping.",
                    "failure_scenario": "Manual mapping boilerplate code.",
                    "expected": "REJECT",
                    "reason": "false_positive",
                    "difficulty": "EASY"
                }
            ]
        },
        {
            "id": "BV2-026",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/tenant/isolation/TenantDataFilter.java",
            "method": "hasTenantAccess",
            "scope": "CROSS_METHOD",
            "issue_kind": "CROSS_TENANT_LEAKAGE_COMPARISON",
            "expected_role": "security_validation",
            "explanation": "Tenant filter matches record tenantId against session userId instead of session tenantId, breaking multi-tenant database isolation.",
            "evidence": ["return recordTenantId != null && recordTenantId.equals(session.getUserId());"],
            "before_code": """package com.nexus.tenant.isolation;

import org.springframework.stereotype.Component;

@Component
public class TenantDataFilter {
    public boolean hasTenantAccess(String recordTenantId, UserSession session) {
        return recordTenantId != null && recordTenantId.equals(session.getTenantId());
    }
}
""",
            "after_code": """package com.nexus.tenant.isolation;

import org.springframework.stereotype.Component;

@Component
public class TenantDataFilter {
    public boolean hasTenantAccess(String recordTenantId, UserSession session) {
        return recordTenantId != null && recordTenantId.equals(session.getUserId());
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Multi-tenant isolation broken: record tenantId is matched against session userId, causing tenant access denial or cross-tenant data exposure.",
                    "failure_scenario": "Users from one organization cannot access their company records, and any user whose userId happens to match a tenantId gains cross-tenant data access.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Incorrect session property checked for tenant validation.",
                    "failure_scenario": "Logic fails to authenticate valid tenant requests.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-027",
            "split": "DEV",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/subscription/renewal/GracePeriodEvaluator.java",
            "method": "isAccountInGracePeriod",
            "scope": "METHOD",
            "issue_kind": "OFF_BY_ONE_DATE_COMPARISON",
            "expected_role": "correctness_logic",
            "explanation": "Grace period check uses 'now.isBefore(expiryDate)' instead of 'now.isBefore(expiryDate.plusDays(graceDays))', terminating grace periods prematurely.",
            "evidence": ["return now.isAfter(expiryDate) && now.isBefore(expiryDate);"],
            "before_code": """package com.nexus.subscription.renewal;

import java.time.LocalDate;
import org.springframework.stereotype.Service;

@Service
public class GracePeriodEvaluator {
    public boolean isAccountInGracePeriod(LocalDate now, LocalDate expiryDate, int graceDays) {
        LocalDate graceEnd = expiryDate.plusDays(graceDays);
        return now.isAfter(expiryDate) && now.isBefore(graceEnd);
    }
}
""",
            "after_code": """package com.nexus.subscription.renewal;

import java.time.LocalDate;
import org.springframework.stereotype.Service;

@Service
public class GracePeriodEvaluator {
    public boolean isAccountInGracePeriod(LocalDate now, LocalDate expiryDate, int graceDays) {
        return now.isAfter(expiryDate) && now.isBefore(expiryDate);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Impossible date range 'now.isAfter(expiryDate) && now.isBefore(expiryDate)' eliminates grace period functionality.",
                    "failure_scenario": "Subscribers whose renewal fails are immediately locked out without the contractual grace period.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Unused parameter graceDays in method signature.",
                    "failure_scenario": "Unused parameter clutters API.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-028",
            "split": "HOLDOUT",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/banking/fraud/VelocityCheckService.java",
            "method": "isVelocityExceeded",
            "scope": "METHOD",
            "issue_kind": "INVERTED_FRAUD_THRESHOLD",
            "expected_role": "correctness_logic",
            "explanation": "Velocity check returns true (flagging fraud) when transactionCount is LESS THAN minThreshold instead of greater than maxThreshold.",
            "evidence": ["return transactionCount < maxThreshold;"],
            "before_code": """package com.nexus.banking.fraud;

import org.springframework.stereotype.Service;

@Service
public class VelocityCheckService {
    public boolean isVelocityExceeded(int transactionCount, int maxThreshold) {
        return transactionCount > maxThreshold;
    }
}
""",
            "after_code": """package com.nexus.banking.fraud;

import org.springframework.stereotype.Service;

@Service
public class VelocityCheckService {
    public boolean isVelocityExceeded(int transactionCount, int maxThreshold) {
        return transactionCount < maxThreshold;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Velocity threshold comparison inverted: normal users with low transaction count are flagged as fraud while high-frequency fraudsters pass.",
                    "failure_scenario": "Legitimate low-frequency transactions are blocked while automated velocity attacks bypass fraud detection.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Fraud detection bypass vulnerability.",
                    "failure_scenario": "High frequency card testing attacks allowed.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-029",
            "split": "HOLDOUT",
            "cat": "SEMANTIC",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/role/permission/AdminRoleVerifier.java",
            "method": "isSuperAdminOrSelf",
            "scope": "METHOD",
            "issue_kind": "PRIVILEGE_ESCALATION_EQUALS_CHECK",
            "expected_role": "security_validation",
            "explanation": "Permission verifier uses 'targetUserId != null || isSuperAdmin' allowing any non-null target user ID to access target profile without authorization.",
            "evidence": ["return targetUserId != null || isSuperAdmin;"],
            "before_code": """package com.nexus.role.permission;

import org.springframework.stereotype.Component;

@Component
public class AdminRoleVerifier {
    public boolean isSuperAdminOrSelf(String requesterId, String targetUserId, boolean isSuperAdmin) {
        return isSuperAdmin || (requesterId != null && requesterId.equals(targetUserId));
    }
}
""",
            "after_code": """package com.nexus.role.permission;

import org.springframework.stereotype.Component;

@Component
public class AdminRoleVerifier {
    public boolean isSuperAdminOrSelf(String requesterId, String targetUserId, boolean isSuperAdmin) {
        return targetUserId != null || isSuperAdmin;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Unchecked targetUserId presence allows any authenticated user to perform administrative actions on any existing user profile.",
                    "failure_scenario": "An unprivileged standard user can modify any other user account simply by supplying targetUserId.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "requesterId parameter is completely ignored in authorization check.",
                    "failure_scenario": "Broken requester validation logic.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-030",
            "split": "HOLDOUT",
            "cat": "SEMANTIC",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/reward/loyalty/PointsExpiryPolicy.java",
            "method": "calculateExpiredPoints",
            "scope": "METHOD",
            "issue_kind": "WRONG_CALCULATION_OPERATION",
            "expected_role": "correctness_logic",
            "explanation": "Expired points calculation multiplies earned points by multiplier instead of subtracting redeemed points, computing inflated expired values.",
            "evidence": ["return earnedPoints * 2;"],
            "before_code": """package com.nexus.reward.loyalty;

import org.springframework.stereotype.Component;

@Component
public class PointsExpiryPolicy {
    public int calculateExpiredPoints(int earnedPoints, int redeemedPoints) {
        int remaining = earnedPoints - redeemedPoints;
        return Math.max(0, remaining);
    }
}
""",
            "after_code": """package com.nexus.reward.loyalty;

import org.springframework.stereotype.Component;

@Component
public class PointsExpiryPolicy {
    public int calculateExpiredPoints(int earnedPoints, int redeemedPoints) {
        return earnedPoints * 2;
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Incorrect mathematical calculation returns double earned points instead of remaining unused points.",
                    "failure_scenario": "Loyalty balance calculations will falsely expire double the earned points.",
                    "expected": "ACCEPT",
                    "reason": "true_finding",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Unused parameter redeemedPoints.",
                    "failure_scenario": "Method signature maintains unused argument.",
                    "expected": "REJECT",
                    "reason": "role_leakage",
                    "difficulty": "MEDIUM"
                }
            ]
        },

        # =========================================================================
        # 4. CLEAN / HARD-NEGATIVE PR'S (BV2-031 .. BV2-040)
        # =========================================================================
        {
            "id": "BV2-031",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/utility/sanitizer/PathSanitizer.java",
            "method": "normalizeSafeSubpath",
            "scope": "METHOD",
            "issue_kind": "CLEAN_TERNARY_NULL_GUARD",
            "expected_role": None,
            "explanation": "Clean PR: correctly implements ternary null guard returning empty string on null and sanitized subpath otherwise.",
            "evidence": ["return rawPath == null ? \"\" : rawPath.trim().replace(\"..\", \"\");"],
            "before_code": """package com.nexus.utility.sanitizer;

public class PathSanitizer {
    public String normalizeSafeSubpath(String rawPath) {
        return rawPath.replace("..", "");
    }
}
""",
            "after_code": """package com.nexus.utility.sanitizer;

public class PathSanitizer {
    public String normalizeSafeSubpath(String rawPath) {
        return rawPath == null ? "" : rawPath.trim().replace("..", "");
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Potential NullPointerException when calling trim() on null rawPath string.",
                    "failure_scenario": "If rawPath is null, calling trim() throws NullPointerException.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "Incomplete path traversal sanitization allows bypass using encoded dots.",
                    "failure_scenario": "Path traversal check can be bypassed with URL encoding.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Ternary operator is redundant and can be replaced with rawPath.trim().",
                    "failure_scenario": "Simplifying ternary expression improves readability.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-032",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/io/safe/AutoClosingResourceHandler.java",
            "method": "loadConfigurationBytes",
            "scope": "METHOD",
            "issue_kind": "CLEAN_TRY_WITH_RESOURCES",
            "expected_role": None,
            "explanation": "Clean PR: correctly refactors FileInputStream into try-with-resources statement ensuring guaranteed closure.",
            "evidence": ["try (FileInputStream fis = new FileInputStream(cfgFile)) {"],
            "before_code": """package com.nexus.io.safe;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class AutoClosingResourceHandler {
    public byte[] loadConfigurationBytes(File cfgFile) throws IOException {
        FileInputStream fis = new FileInputStream(cfgFile);
        return fis.readAllBytes();
    }
}
""",
            "after_code": """package com.nexus.io.safe;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class AutoClosingResourceHandler {
    public byte[] loadConfigurationBytes(File cfgFile) throws IOException {
        try (FileInputStream fis = new FileInputStream(cfgFile)) {
            return fis.readAllBytes();
        }
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "FileInputStream is not closed after reading configuration bytes.",
                    "failure_scenario": "Resource leak on unclosed file stream.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                },
                {
                    "reviewer": "security_validation",
                    "problem": "File path traversal vulnerability when opening configuration file.",
                    "failure_scenario": "Arbitrary file disclosure via cfgFile parameter.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-033",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/auth/display/UserRoleDisplayHelper.java",
            "method": "formatRoleBadge",
            "scope": "LINE",
            "issue_kind": "CLEAN_DISPLAY_CONSTANT",
            "expected_role": None,
            "explanation": "Clean PR: updates UI badge display label for admin role to 'ADMINISTRATOR'. Not a credential or secret.",
            "evidence": ["return \"ROLE_BADGE_ADMINISTRATOR\";"],
            "before_code": """package com.nexus.auth.display;

import org.springframework.stereotype.Component;

@Component
public class UserRoleDisplayHelper {
    public String formatRoleBadge(boolean isAdmin) {
        return isAdmin ? "ADMIN" : "MEMBER";
    }
}
""",
            "after_code": """package com.nexus.auth.display;

import org.springframework.stereotype.Component;

@Component
public class UserRoleDisplayHelper {
    public String formatRoleBadge(boolean isAdmin) {
        return isAdmin ? "ROLE_BADGE_ADMINISTRATOR" : "ROLE_BADGE_MEMBER";
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Hardcoded security credential 'ROLE_BADGE_ADMINISTRATOR' exposed in source code.",
                    "failure_scenario": "Exposing administrator role string allows attackers to forge security credentials.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Magic string should be moved to message bundle.",
                    "failure_scenario": "Internationalization support is impaired.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-034",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/access/rbac/MembershipPermissionGuard.java",
            "method": "isAuthorizedMember",
            "scope": "METHOD",
            "issue_kind": "CLEAN_CORRECT_AUTH_CHECK",
            "expected_role": None,
            "explanation": "Clean PR: implements safe and correct RBAC check ensuring membership is active AND matching teamId.",
            "evidence": ["return membership.isActive() && membership.getTeamId().equals(targetTeamId);"],
            "before_code": """package com.nexus.access.rbac;

import org.springframework.stereotype.Component;

@Component
public class MembershipPermissionGuard {
    public boolean isAuthorizedMember(TeamMembership membership, String targetTeamId) {
        return membership.getTeamId().equals(targetTeamId);
    }
}
""",
            "after_code": """package com.nexus.access.rbac;

import org.springframework.stereotype.Component;

@Component
public class MembershipPermissionGuard {
    public boolean isAuthorizedMember(TeamMembership membership, String targetTeamId) {
        return membership != null && membership.isActive() && targetTeamId != null && targetTeamId.equals(membership.getTeamId());
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Inverted membership authorization condition permits deactivated users.",
                    "failure_scenario": "Inactive team members can access protected team resources.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Potential NullPointerException on membership.getTeamId() invocation.",
                    "failure_scenario": "If getTeamId() returns null, calling equals throws NullPointerException.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-035",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/collections/defensive/ImmutableListHelper.java",
            "method": "copyElementsSafely",
            "scope": "METHOD",
            "issue_kind": "CLEAN_DEFENSIVE_COPY",
            "expected_role": None,
            "explanation": "Clean PR: implements defensive copy using List.copyOf handling null check appropriately.",
            "evidence": ["return inputList == null ? List.of() : List.copyOf(inputList);"],
            "before_code": """package com.nexus.collections.defensive;

import java.util.List;

public class ImmutableListHelper {
    public <T> List<T> copyElementsSafely(List<T> inputList) {
        return inputList;
    }
}
""",
            "after_code": """package com.nexus.collections.defensive;

import java.util.List;

public class ImmutableListHelper {
    public <T> List<T> copyElementsSafely(List<T> inputList) {
        return inputList == null ? List.of() : List.copyOf(inputList);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Null pointer exception if inputList is null when passing to List.copyOf.",
                    "failure_scenario": "Calling List.copyOf with null argument causes NullPointerException.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Ternary operator is redundant and can be replaced with Collections.unmodifiableList.",
                    "failure_scenario": "Reduces readability.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-036",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/payment/gateway/WebhookSignatureValidator.java",
            "method": "isSignatureValid",
            "scope": "METHOD",
            "issue_kind": "CLEAN_CONSTANT_TIME_EQUALS",
            "expected_role": None,
            "explanation": "Clean PR: replaces standard string equals with MessageDigest.isEqual for timing-attack-safe comparison.",
            "evidence": ["return MessageDigest.isEqual(sigA.getBytes(StandardCharsets.UTF_8), sigB.getBytes(StandardCharsets.UTF_8));"],
            "before_code": """package com.nexus.payment.gateway;

import org.springframework.stereotype.Component;

@Component
public class WebhookSignatureValidator {
    public boolean isSignatureValid(String expectedSig, String incomingSig) {
        return expectedSig != null && expectedSig.equals(incomingSig);
    }
}
""",
            "after_code": """package com.nexus.payment.gateway;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.stereotype.Component;

@Component
public class WebhookSignatureValidator {
    public boolean isSignatureValid(String expectedSig, String incomingSig) {
        if (expectedSig == null || incomingSig == null) {
            return false;
        }
        return MessageDigest.isEqual(expectedSig.getBytes(StandardCharsets.UTF_8), incomingSig.getBytes(StandardCharsets.UTF_8));
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Timing attack vulnerability due to byte array comparison in signature validation.",
                    "failure_scenario": "Attackers can measure microsecond differences during signature validation to forge signatures.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "NullPointerException if expectedSig or incomingSig is null.",
                    "failure_scenario": "Calling getBytes on null string throws NPE.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                }
            ]
        },
        {
            "id": "BV2-037",
            "split": "DEV",
            "cat": "CLEAN",
            "diff": "MEDIUM",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/text/parser/NumericTokenParser.java",
            "method": "parsePositiveInteger",
            "scope": "METHOD",
            "issue_kind": "CLEAN_OPTIONAL_PARSER",
            "expected_role": None,
            "explanation": "Clean PR: correctly parses positive integer returning Optional.empty on non-numeric or negative values.",
            "evidence": ["try { int val = Integer.parseInt(text.trim()); return val > 0 ? Optional.of(val) : Optional.empty(); } catch (NumberFormatException e) { return Optional.empty(); }"],
            "before_code": """package com.nexus.text.parser;

import java.util.Optional;

public class NumericTokenParser {
    public Optional<Integer> parsePositiveInteger(String text) {
        return Optional.of(Integer.parseInt(text));
    }
}
""",
            "after_code": """package com.nexus.text.parser;

import java.util.Optional;

public class NumericTokenParser {
    public Optional<Integer> parsePositiveInteger(String text) {
        if (text == null || text.isBlank()) {
            return Optional.empty();
        }
        try {
            int val = Integer.parseInt(text.trim());
            return val > 0 ? Optional.of(val) : Optional.empty();
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Uncaught NumberFormatException when parsing invalid integer string.",
                    "failure_scenario": "Invalid numeric strings will crash the thread with unhandled exception.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Empty catch block swallows NumberFormatException without logging.",
                    "failure_scenario": "Swallowing exceptions makes debugging parsing issues difficult.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-038",
            "split": "HOLDOUT",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "spring",
            "file": "src/main/java/com/nexus/crypto/envelope/EnvelopeKeyDecryptor.java",
            "method": "decryptEnvelopeKey",
            "scope": "METHOD",
            "issue_kind": "CLEAN_ENCRYPTED_KEY_HANDLER",
            "expected_role": None,
            "explanation": "Clean PR: securely decrypts envelope data key using KMS client; label string 'alias/nexus-data-key' is a KMS key alias, not a secret.",
            "evidence": ["return kmsClient.decrypt(encryptedDataKey, \"alias/nexus-data-key\");"],
            "before_code": """package com.nexus.crypto.envelope;

import org.springframework.stereotype.Service;

@Service
public class EnvelopeKeyDecryptor {
    private final KmsClient kmsClient;

    public EnvelopeKeyDecryptor(KmsClient kmsClient) {
        this.kmsClient = kmsClient;
    }

    public byte[] decryptEnvelopeKey(byte[] encryptedDataKey) {
        return kmsClient.decrypt(encryptedDataKey, "default-alias");
    }
}
""",
            "after_code": """package com.nexus.crypto.envelope;

import org.springframework.stereotype.Service;

@Service
public class EnvelopeKeyDecryptor {
    private final KmsClient kmsClient;

    public EnvelopeKeyDecryptor(KmsClient kmsClient) {
        this.kmsClient = kmsClient;
    }

    public byte[] decryptEnvelopeKey(byte[] encryptedDataKey) {
        if (encryptedDataKey == null || encryptedDataKey.length == 0) {
            return new byte[0];
        }
        return kmsClient.decrypt(encryptedDataKey, "alias/nexus-data-key");
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Hardcoded encryption key 'alias/nexus-data-key' exposed in decryptEnvelopeKey.",
                    "failure_scenario": "Exposing KMS key alias in source code allows attackers to compromise encrypted envelope data.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "Empty byte array return on null input can mask encryption failure.",
                    "failure_scenario": "Callers receive empty array instead of IllegalArgumentException.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-039",
            "split": "HOLDOUT",
            "cat": "CLEAN",
            "diff": "HARD",
            "framework": "plain-java",
            "file": "src/main/java/com/nexus/cache/lru/BoundedLruCache.java",
            "method": "getOrCompute",
            "scope": "METHOD",
            "issue_kind": "CLEAN_THREAD_SAFE_CACHE",
            "expected_role": None,
            "explanation": "Clean PR: correctly synchronizes map lookups and computes value under lock safely.",
            "evidence": ["synchronized (lock) { return map.computeIfAbsent(key, mappingFunction); }"],
            "before_code": """package com.nexus.cache.lru;

import java.util.Map;
import java.util.HashMap;
import java.util.function.Function;

public class BoundedLruCache<K, V> {
    private final Map<K, V> map = new HashMap<>();

    public V getOrCompute(K key, Function<K, V> mappingFunction) {
        return map.computeIfAbsent(key, mappingFunction);
    }
}
""",
            "after_code": """package com.nexus.cache.lru;

import java.util.Map;
import java.util.HashMap;
import java.util.function.Function;

public class BoundedLruCache<K, V> {
    private final Map<K, V> map = new HashMap<>();
    private final Object lock = new Object();

    public V getOrCompute(K key, Function<K, V> mappingFunction) {
        if (key == null) {
            return null;
        }
        synchronized (lock) {
            return map.computeIfAbsent(key, mappingFunction);
        }
    }
}
""",
            "candidates": [
                {
                    "reviewer": "correctness_logic",
                    "problem": "Race condition and concurrency hazard when accessing HashMap across threads.",
                    "failure_scenario": "Concurrent access can corrupt internal HashMap bucket structure.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "maintainability",
                    "problem": "Use ConcurrentHashMap instead of manual synchronized lock block.",
                    "failure_scenario": "ConcurrentHashMap provides higher throughput.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "MEDIUM"
                }
            ]
        },
        {
            "id": "BV2-040",
            "split": "HOLDOUT",
            "cat": "CLEAN",
            "diff": "MEDIUM",
            "framework": "spring",
            "file": "src/main/java/com/nexus/audit/trail/EventAuditRecorder.java",
            "method": "recordAuditEvent",
            "scope": "METHOD",
            "issue_kind": "CLEAN_DEFENSIVE_LOGGING",
            "expected_role": None,
            "explanation": "Clean PR: correctly sanitizes newlines from log inputs to prevent log injection.",
            "evidence": ["String safeMessage = eventMessage.replace('\\n', '_').replace('\\r', '_');"],
            "before_code": """package com.nexus.audit.trail;

import org.springframework.stereotype.Component;

@Component
public class EventAuditRecorder {
    public void recordAuditEvent(String eventType, String eventMessage) {
        System.out.println("AUDIT [" + eventType + "]: " + eventMessage);
    }
}
""",
            "after_code": """package com.nexus.audit.trail;

import org.springframework.stereotype.Component;

@Component
public class EventAuditRecorder {
    public void recordAuditEvent(String eventType, String eventMessage) {
        if (eventType == null || eventMessage == null) {
            return;
        }
        String safeMessage = eventMessage.replace('\\n', '_').replace('\\r', '_');
        System.out.println("AUDIT [" + eventType + "]: " + safeMessage);
    }
}
""",
            "candidates": [
                {
                    "reviewer": "security_validation",
                    "problem": "Log forging / CRLF log injection vulnerability in audit event logging.",
                    "failure_scenario": "Malicious eventMessage containing newline characters can forge audit entries.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                },
                {
                    "reviewer": "correctness_logic",
                    "problem": "NullPointerException if eventMessage is null when calling replace.",
                    "failure_scenario": "Calling replace on null string throws NPE.",
                    "expected": "REJECT",
                    "reason": "clean_pr_false_positive",
                    "difficulty": "HARD"
                }
            ]
        }
    ]

    # Generate records, unified diffs, and save fixtures
    for sc in scenario_defs:
        sc_id = sc["id"]
        split = sc["split"]
        cat = sc["cat"]
        diff_level = sc["diff"]
        fw = sc["framework"]
        file_p = sc["file"]
        meth = sc["method"]
        scope = sc["scope"]
        has_issue = (cat != "CLEAN")
        exp_role = sc["expected_role"]

        # 1. Create fixture files
        fix_dir = FIXTURES_DIR / sc_id
        b_dir = fix_dir / "before"
        a_dir = fix_dir / "after"
        b_dir.mkdir(parents=True, exist_ok=True)
        a_dir.mkdir(parents=True, exist_ok=True)

        target_fname = Path(file_p).name
        (b_dir / target_fname).write_text(sc["before_code"], encoding="utf-8")
        (a_dir / target_fname).write_text(sc["after_code"], encoding="utf-8")

        # Create synthetic diff
        import difflib
        b_lines = sc["before_code"].splitlines(keepends=True)
        a_lines = sc["after_code"].splitlines(keepends=True)
        udiff = "".join(difflib.unified_diff(b_lines, a_lines, fromfile=f"a/{file_p}", tofile=f"b/{file_p}"))
        (fix_dir / "diff.patch").write_text(udiff, encoding="utf-8")

        # Find changed lines in after_code
        changed_line_nums = []
        for idx, line in enumerate(a_lines, start=1):
            if line not in b_lines:
                changed_line_nums.append(idx)
        if not changed_line_nums:
            changed_line_nums = [1]

        # Scenario object
        sc_obj = {
            "scenario_id": sc_id,
            "split": split,
            "provenance": "synthetic",
            "source_url": None,
            "license": None,
            "language": "java",
            "framework": fw,
            "category": cat,
            "difficulty": diff_level,
            "issue_kind": sc["issue_kind"],
            "expected_role": exp_role,
            "context_scope_required": scope,
            "file_path": file_p,
            "changed_method": meth,
            "changed_lines": changed_line_nums,
            "ground_truth_has_issue": has_issue,
            "ground_truth_explanation": sc["explanation"],
            "ground_truth_evidence": sc["evidence"]
        }
        scenarios.append(sc_obj)
        splits[split].append(sc_id)

        # Ground truth entry
        ground_truth["scenarios"][sc_id] = {
            "category": cat,
            "has_issue": has_issue,
            "expected_role": exp_role,
            "explanation": sc["explanation"],
            "evidence": sc["evidence"]
        }

        # Candidates
        for c_idx, cand in enumerate(sc["candidates"]):
            c_id = f"{sc_id}-{cand['reviewer']}-cand-{c_idx}"
            exp_verdict = cand["expected"]
            exp_supported = (exp_verdict == "ACCEPT")
            c_obj = {
                "candidate_id": c_id,
                "scenario_id": sc_id,
                "source_reviewer": cand["reviewer"],
                "problem": cand["problem"],
                "failure_scenario": cand["failure_scenario"],
                "expected": exp_verdict,
                "expected_finding_supported": exp_supported,
                "reason_type": cand["reason"],
                "difficulty": cand["difficulty"]
            }
            candidates.append(c_obj)

    # Save all JSON datasets
    (BASE_DIR / "scenarios.json").write_text(json.dumps(scenarios, indent=2, ensure_ascii=False), encoding="utf-8")
    (BASE_DIR / "candidates.json").write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")
    (BASE_DIR / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")
    (BASE_DIR / "splits.json").write_text(json.dumps(splits, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Benchmark V2 Built Successfully!")
    print(f"Total Scenarios : {len(scenarios)} (DEV: {len(splits['DEV'])}, HOLDOUT: {len(splits['HOLDOUT'])})")
    print(f"Total Candidates: {len(candidates)}")
    accept_c = sum(1 for c in candidates if c["expected"] == "ACCEPT")
    reject_c = sum(1 for c in candidates if c["expected"] == "REJECT")
    print(f"  ACCEPT        : {accept_c}")
    print(f"  REJECT        : {reject_c}")


if __name__ == "__main__":
    build_all_scenarios_and_candidates()
