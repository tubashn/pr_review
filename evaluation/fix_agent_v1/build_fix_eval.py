import json
import os
from pathlib import Path

PR_REVIEW_DIR = Path(r"C:\Users\Lenovo\Documents\GitHub\pr_review")
EVAL_DIR = PR_REVIEW_DIR / "evaluation" / "fix_agent_v1"
FIXTURES_DIR = EVAL_DIR / "fixtures"

os.makedirs(FIXTURES_DIR, exist_ok=True)
os.makedirs(EVAL_DIR / "results", exist_ok=True)
os.makedirs(EVAL_DIR / "reports", exist_ok=True)

# -----------------------------------------------------------------------------
# 30 Synthetic Scenarios Definitions
# -----------------------------------------------------------------------------
SCENARIOS_DATA = [
    # ------------------ DEV SPLIT: ELIGIBLE (15) ------------------
    # Maintainability (8 DEV)
    {
        "scenario_id": "FA-001",
        "title": "Redundant boolean comparison == true",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/payments/PaymentValidator.java",
        "line": 6,
        "problem": "Redundant boolean comparison in expression: `isAuthorized == true`.",
        "evidence": "if (isAuthorized == true) {",
        "difficulty": "EASY",
        "notes": "Direct simplification from `isAuthorized == true` to `isAuthorized`.",
        "before_code": """package com.example.payments;

public class PaymentValidator {
    public boolean validateTransaction(boolean isAuthorized, double amount) {
        if (amount <= 0) {
            return false;
        }
        if (isAuthorized == true) {
            return true;
        }
        return false;
    }
}
""",
        "after_code": """package com.example.payments;

public class PaymentValidator {
    public boolean validateTransaction(boolean isAuthorized, double amount) {
        if (amount <= 0) {
            return false;
        }
        if (isAuthorized) {
            return true;
        }
        return false;
    }
}
"""
    },
    {
        "scenario_id": "FA-002",
        "title": "Redundant boolean comparison == false",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/auth/UserAccessController.java",
        "line": 6,
        "problem": "Redundant boolean comparison in expression: `isBlocked == false`.",
        "evidence": "if (isBlocked == false) {",
        "difficulty": "EASY",
        "notes": "Simplify `isBlocked == false` to `!isBlocked`.",
        "before_code": """package com.example.auth;

public class UserAccessController {
    public boolean canAccessResource(boolean isBlocked, boolean isVerified) {
        if (isBlocked == false) {
            return isVerified;
        }
        return false;
    }
}
""",
        "after_code": """package com.example.auth;

public class UserAccessController {
    public boolean canAccessResource(boolean isBlocked, boolean isVerified) {
        if (!isBlocked) {
            return isVerified;
        }
        return false;
    }
}
"""
    },
    {
        "scenario_id": "FA-003",
        "title": "Unused local variable debugCount",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/reporting/ReportGenerator.java",
        "line": 5,
        "problem": "Unused local variable `debugCount` is declared and assigned but never used in method scope.",
        "evidence": "int debugCount = 0;",
        "difficulty": "EASY",
        "notes": "Remove unused local declaration.",
        "before_code": """package com.example.reporting;

public class ReportGenerator {
    public String generateSummary(String title, int totalRecords) {
        int debugCount = 0;
        return "Report: " + title + " (" + totalRecords + " records)";
    }
}
""",
        "after_code": """package com.example.reporting;

public class ReportGenerator {
    public String generateSummary(String title, int totalRecords) {
        return "Report: " + title + " (" + totalRecords + " records)";
    }
}
"""
    },
    {
        "scenario_id": "FA-004",
        "title": "Unused StringBuilder allocation",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/utils/StringFormatter.java",
        "line": 5,
        "problem": "Unused local variable `builder` is declared and assigned but never used in method scope.",
        "evidence": "StringBuilder builder = new StringBuilder();",
        "difficulty": "MEDIUM",
        "notes": "Remove dead object instantiation.",
        "before_code": """package com.example.utils;

public class StringFormatter {
    public String formatHeader(String prefix, String name) {
        StringBuilder builder = new StringBuilder();
        return prefix.trim() + " - " + name.trim();
    }
}
""",
        "after_code": """package com.example.utils;

public class StringFormatter {
    public String formatHeader(String prefix, String name) {
        return prefix.trim() + " - " + name.trim();
    }
}
"""
    },
    {
        "scenario_id": "FA-005",
        "title": "Redundant double negation",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/features/FeatureToggleService.java",
        "line": 5,
        "problem": "Redundant double negation `!(!enabled)` in boolean expression.",
        "evidence": "return !(!enabled);",
        "difficulty": "EASY",
        "notes": "Simplify `!(!enabled)` to `enabled`.",
        "before_code": """package com.example.features;

public class FeatureToggleService {
    public boolean isFeatureActive(boolean enabled) {
        return !(!enabled);
    }
}
""",
        "after_code": """package com.example.features;

public class FeatureToggleService {
    public boolean isFeatureActive(boolean enabled) {
        return enabled;
    }
}
"""
    },
    {
        "scenario_id": "FA-006",
        "title": "Unnecessary string concatenation in char lookup",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/currency/CurrencyConverter.java",
        "line": 5,
        "problem": "Redundant boolean comparison in expression: `isSupported == true`.",
        "evidence": "if (isSupported == true) {",
        "difficulty": "MEDIUM",
        "notes": "Simplify boolean check.",
        "before_code": """package com.example.currency;

public class CurrencyConverter {
    public double convert(double amount, double rate, boolean isSupported) {
        if (isSupported == true) {
            return amount * rate;
        }
        return 0.0;
    }
}
""",
        "after_code": """package com.example.currency;

public class CurrencyConverter {
    public double convert(double amount, double rate, boolean isSupported) {
        if (isSupported) {
            return amount * rate;
        }
        return 0.0;
    }
}
"""
    },
    {
        "scenario_id": "FA-007",
        "title": "Unused local variable lastError",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/session/SessionManager.java",
        "line": 5,
        "problem": "Unused local variable `lastError` is declared and assigned but never used in method scope.",
        "evidence": "String lastError = \"\";",
        "difficulty": "MEDIUM",
        "notes": "Remove unused local variable declaration.",
        "before_code": """package com.example.session;

public class SessionManager {
    public boolean isValidSession(String sessionId) {
        String lastError = "";
        return sessionId != null && sessionId.length() == 32;
    }
}
""",
        "after_code": """package com.example.session;

public class SessionManager {
    public boolean isValidSession(String sessionId) {
        return sessionId != null && sessionId.length() == 32;
    }
}
"""
    },
    {
        "scenario_id": "FA-008",
        "title": "Redundant boolean comparison in expression",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/security/PermissionEvaluator.java",
        "line": 5,
        "problem": "Redundant boolean comparison in expression: `hasPermission == true`.",
        "evidence": "return hasPermission == true;",
        "difficulty": "HARD",
        "notes": "Simplify `hasPermission == true` to `hasPermission`.",
        "before_code": """package com.example.security;

public class PermissionEvaluator {
    public boolean evaluate(boolean hasPermission) {
        return hasPermission == true;
    }
}
""",
        "after_code": """package com.example.security;

public class PermissionEvaluator {
    public boolean evaluate(boolean hasPermission) {
        return hasPermission;
    }
}
"""
    },

    # Correctness (7 DEV)
    {
        "scenario_id": "FA-009",
        "title": "Inverted comparison operator in discount calculation",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/pricing/DiscountCalculator.java",
        "line": 5,
        "problem": "Incorrect comparison operator: items count comparison uses `<` instead of `>=` for discount qualification threshold.",
        "evidence": "if (itemCount < 10) {",
        "difficulty": "EASY",
        "notes": "Change `itemCount < 10` to `itemCount >= 10`.",
        "before_code": """package com.example.pricing;

public class DiscountCalculator {
    public double applyVolumeDiscount(double subtotal, int itemCount) {
        if (itemCount < 10) {
            return subtotal * 0.90;
        }
        return subtotal;
    }
}
""",
        "after_code": """package com.example.pricing;

public class DiscountCalculator {
    public double applyVolumeDiscount(double subtotal, int itemCount) {
        if (itemCount >= 10) {
            return subtotal * 0.90;
        }
        return subtotal;
    }
}
"""
    },
    {
        "scenario_id": "FA-010",
        "title": "Off-by-one boundary comparison in buffer reader",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/io/ArrayBufferReader.java",
        "line": 5,
        "problem": "Off-by-one boundary error in array index validation: condition `index > buffer.length` should be `index >= buffer.length`.",
        "evidence": "if (index < 0 || index > buffer.length) {",
        "difficulty": "EASY",
        "notes": "Change index > buffer.length to index >= buffer.length to prevent ArrayIndexOutOfBoundsException.",
        "before_code": """package com.example.io;

public class ArrayBufferReader {
    public byte readByte(byte[] buffer, int index) {
        if (index < 0 || index > buffer.length) {
            return -1;
        }
        return buffer[index];
    }
}
""",
        "after_code": """package com.example.io;

public class ArrayBufferReader {
    public byte readByte(byte[] buffer, int index) {
        if (index < 0 || index >= buffer.length) {
            return -1;
        }
        return buffer[index];
    }
}
"""
    },
    {
        "scenario_id": "FA-011",
        "title": "Incorrect constant rate multiplier",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/finance/TaxCalculator.java",
        "line": 5,
        "problem": "Incorrect tax rate constant applied: standard VAT rate is configured as 0.20 instead of 0.25.",
        "evidence": "return baseAmount * 0.25;",
        "difficulty": "MEDIUM",
        "notes": "Replace wrong constant 0.25 with 0.20.",
        "before_code": """package com.example.finance;

public class TaxCalculator {
    public double calculateStandardTax(double baseAmount) {
        return baseAmount * 0.25;
    }
}
""",
        "after_code": """package com.example.finance;

public class TaxCalculator {
    public double calculateStandardTax(double baseAmount) {
        return baseAmount * 0.20;
    }
}
"""
    },
    {
        "scenario_id": "FA-012",
        "title": "Inverted boolean return value in stock checker",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/inventory/StockAvailabilityService.java",
        "line": 5,
        "problem": "Inverted logic: method returns false when stock is sufficient and true when out of stock.",
        "evidence": "return availableCount < requestedCount;",
        "difficulty": "MEDIUM",
        "notes": "Invert condition to availableCount >= requestedCount.",
        "before_code": """package com.example.inventory;

public class StockAvailabilityService {
    public boolean isAvailable(int availableCount, int requestedCount) {
        return availableCount < requestedCount;
    }
}
""",
        "after_code": """package com.example.inventory;

public class StockAvailabilityService {
    public boolean isAvailable(int availableCount, int requestedCount) {
        return availableCount >= requestedCount;
    }
}
"""
    },
    {
        "scenario_id": "FA-013",
        "title": "Swapped dimensions in rectangle calculation",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/geometry/RectangleAreaCalculator.java",
        "line": 5,
        "problem": "Incorrect subtraction in perimeter formula: `2 * (width - height)` instead of `2 * (width + height)`.",
        "evidence": "return 2 * (width - height);",
        "difficulty": "MEDIUM",
        "notes": "Fix arithmetic operator `-` to `+`.",
        "before_code": """package com.example.geometry;

public class RectangleAreaCalculator {
    public double calculatePerimeter(double width, double height) {
        return 2 * (width - height);
    }
}
""",
        "after_code": """package com.example.geometry;

public class RectangleAreaCalculator {
    public double calculatePerimeter(double width, double height) {
        return 2 * (width + height);
    }
}
"""
    },
    {
        "scenario_id": "FA-014",
        "title": "Wrong status string comparison",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/orders/TransactionStatusChecker.java",
        "line": 5,
        "problem": "Wrong status comparison: checks against status \"FAILED\" instead of \"SUCCESS\" for positive confirmation.",
        "evidence": "return \"FAILED\".equalsIgnoreCase(status);",
        "difficulty": "EASY",
        "notes": "Replace \"FAILED\" with \"SUCCESS\".",
        "before_code": """package com.example.orders;

public class TransactionStatusChecker {
    public boolean isSuccessful(String status) {
        return "FAILED".equalsIgnoreCase(status);
    }
}
""",
        "after_code": """package com.example.orders;

public class TransactionStatusChecker {
    public boolean isSuccessful(String status) {
        return "SUCCESS".equalsIgnoreCase(status);
    }
}
"""
    },
    {
        "scenario_id": "FA-015",
        "title": "Integer division truncation in percentage calculation",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/math/PercentageFormatter.java",
        "line": 5,
        "problem": "Integer division causes unintended zero truncation before floating conversion: `(part / total) * 100.0`.",
        "evidence": "return (part / total) * 100.0;",
        "difficulty": "HARD",
        "notes": "Cast part to double: `((double) part / total) * 100.0`.",
        "before_code": """package com.example.math;

public class PercentageFormatter {
    public double calculatePercentage(int part, int total) {
        if (total == 0) return 0.0;
        return (part / total) * 100.0;
    }
}
""",
        "after_code": """package com.example.math;

public class PercentageFormatter {
    public double calculatePercentage(int part, int total) {
        if (total == 0) return 0.0;
        return ((double) part / total) * 100.0;
    }
}
"""
    },

    # ------------------ DEV SPLIT: INELIGIBLE (7) ------------------
    {
        "scenario_id": "FA-016",
        "title": "Hardcoded gateway API secret key",
        "split": "DEV",
        "role": "security_validation",
        "finding_type": "security",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "security_findings_not_auto_fixed",
        "file_path": "src/main/java/com/example/gateway/ExternalGatewayClient.java",
        "line": 5,
        "problem": "Hardcoded secret api key token literal committed to source code.",
        "evidence": "private String apiKey = \"secret_gateway_token_9988776655443322\";",
        "difficulty": "EASY",
        "notes": "Security findings must be skipped by eligibility gate in V1.",
        "before_code": """package com.example.gateway;

public class ExternalGatewayClient {
    private String apiKey = "secret_gateway_token_9988776655443322";
    public String getKey() { return apiKey; }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-017",
        "title": "SQL Injection vulnerability through raw query concatenation",
        "split": "DEV",
        "role": "security_validation",
        "finding_type": "security",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "security_findings_not_auto_fixed",
        "file_path": "src/main/java/com/example/db/UserAccountRepository.java",
        "line": 5,
        "problem": "SQL injection vulnerability: unescaped user input concatenated into SQL query string.",
        "evidence": "String query = \"SELECT * FROM users WHERE email = '\" + email + \"'\";",
        "difficulty": "MEDIUM",
        "notes": "Security vulnerabilities are strictly excluded from automated patch generation.",
        "before_code": """package com.example.db;

public class UserAccountRepository {
    public String findQuery(String email) {
        return "SELECT * FROM users WHERE email = '" + email + "'";
    }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-018",
        "title": "Unclosed FileInputStream resource leak",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "absence",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "absence_type_not_auto_fixed",
        "file_path": "src/main/java/com/example/archive/FileArchiveReader.java",
        "line": 6,
        "problem": "Unclosed resource: `new FileInputStream(filePath)` opened without try-with-resources or close() cleanup.",
        "evidence": "FileInputStream fis = new FileInputStream(filePath);",
        "difficulty": "EASY",
        "notes": "Absence-type findings must be skipped in V1.",
        "before_code": """package com.example.archive;
import java.io.*;

public class FileArchiveReader {
    public int readFirstByte(String filePath) throws IOException {
        FileInputStream fis = new FileInputStream(filePath);
        return fis.read();
    }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-019",
        "title": "Missing null check guard",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "absence",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "absence_type_not_auto_fixed",
        "file_path": "src/main/java/com/example/mappers/CustomerProfileMapper.java",
        "line": 5,
        "problem": "Missing null check: customer parameter lacks defensive null validation before dereferencing.",
        "evidence": "return customer.getName().trim();",
        "difficulty": "EASY",
        "notes": "Absence / missing check findings are excluded.",
        "before_code": """package com.example.mappers;

public class CustomerProfileMapper {
    public String getCustomerName(Customer customer) {
        return customer.getName().trim();
    }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-020",
        "title": "Cross-file synchronization requirement",
        "split": "DEV",
        "role": "correctness_logic",
        "finding_type": "multi_file",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "multi_file_not_supported",
        "file_path": "src/main/java/com/example/controllers/OrderController.java",
        "line": 5,
        "problem": "State inconsistency across files: OrderController and InventoryService must be updated simultaneously.",
        "evidence": "inventoryService.deductStock(order.getId());",
        "difficulty": "MEDIUM",
        "notes": "Multi-file changes are not supported in V1.",
        "before_code": """package com.example.controllers;

public class OrderController {
    public void submit(Order order) {
        inventoryService.deductStock(order.getId());
    }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-021",
        "title": "Build XML configuration file unsupported",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "unsupported_type",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "unsupported_file_type",
        "file_path": "pom.xml",
        "line": 10,
        "problem": "Unused dependency configuration in pom.xml.",
        "evidence": "<artifactId>unused-lib</artifactId>",
        "difficulty": "EASY",
        "notes": "Non-Java files are not eligible in V1.",
        "before_code": """<project>
    <dependencies>
        <dependency><artifactId>unused-lib</artifactId></dependency>
    </dependencies>
</project>
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-022",
        "title": "Large architectural refactoring exceeding limits",
        "split": "DEV",
        "role": "maintainability",
        "finding_type": "large_patch",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "expected_patch_too_large",
        "file_path": "src/main/java/com/example/legacy/LegacyDataMigrator.java",
        "line": 1,
        "problem": "Class complexity smell: refactor entire class to decouple database connection management.",
        "evidence": "public class LegacyDataMigrator { ... }",
        "difficulty": "HARD",
        "notes": "Expected changes > 20 lines are excluded by eligibility gate.",
        "before_code": """package com.example.legacy;

public class LegacyDataMigrator {
    public void migrate() {
        // complex 40 lines of legacy code
    }
}
""",
        "after_code": None
    },

    # ------------------ HOLDOUT SPLIT: ELIGIBLE (5) ------------------
    # Maintainability (2 HOLDOUT)
    {
        "scenario_id": "FA-023",
        "title": "Redundant boolean comparison != true",
        "split": "HOLDOUT",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/subscriptions/SubscriptionChecker.java",
        "line": 5,
        "problem": "Redundant boolean comparison in expression: `isExpired == false`.",
        "evidence": "return isExpired == false;",
        "difficulty": "EASY",
        "notes": "Simplify `isExpired == false` to `!isExpired`.",
        "before_code": """package com.example.subscriptions;

public class SubscriptionChecker {
    public boolean isActive(boolean isExpired) {
        return isExpired == false;
    }
}
""",
        "after_code": """package com.example.subscriptions;

public class SubscriptionChecker {
    public boolean isActive(boolean isExpired) {
        return !isExpired;
    }
}
"""
    },
    {
        "scenario_id": "FA-024",
        "title": "Unused local token list variable",
        "split": "HOLDOUT",
        "role": "maintainability",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/parsers/TokenParser.java",
        "line": 5,
        "problem": "Unused local variable `tempTokens` is declared and assigned but never used in method scope.",
        "evidence": "StringBuilder tempTokens = new StringBuilder();",
        "difficulty": "MEDIUM",
        "notes": "Remove unused local variable.",
        "before_code": """package com.example.parsers;

public class TokenParser {
    public int countSegments(String raw) {
        StringBuilder tempTokens = new StringBuilder();
        return raw == null ? 0 : raw.split(":").length;
    }
}
""",
        "after_code": """package com.example.parsers;

public class TokenParser {
    public int countSegments(String raw) {
        return raw == null ? 0 : raw.split(":").length;
    }
}
"""
    },

    # Correctness (3 HOLDOUT)
    {
        "scenario_id": "FA-025",
        "title": "Inverted rate limit threshold",
        "split": "HOLDOUT",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/throttling/RateLimiter.java",
        "line": 5,
        "problem": "Incorrect threshold check: request is rejected when currentRequests < maxRequests instead of currentRequests >= maxRequests.",
        "evidence": "if (currentRequests < maxRequests) {",
        "difficulty": "EASY",
        "notes": "Invert `<` to `>=`.",
        "before_code": """package com.example.throttling;

public class RateLimiter {
    public boolean isLimitExceeded(int currentRequests, int maxRequests) {
        if (currentRequests < maxRequests) {
            return true;
        }
        return false;
    }
}
""",
        "after_code": """package com.example.throttling;

public class RateLimiter {
    public boolean isLimitExceeded(int currentRequests, int maxRequests) {
        if (currentRequests >= maxRequests) {
            return true;
        }
        return false;
    }
}
"""
    },
    {
        "scenario_id": "FA-026",
        "title": "Off-by-one array index access in queue processor",
        "split": "HOLDOUT",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/queues/QueueProcessor.java",
        "line": 6,
        "problem": "Off-by-one error accessing last item: index `items.length` causes ArrayIndexOutOfBoundsException; should be `items.length - 1`.",
        "evidence": "return items[items.length];",
        "difficulty": "MEDIUM",
        "notes": "Replace items.length with items.length - 1.",
        "before_code": """package com.example.queues;

public class QueueProcessor {
    public String getLastItem(String[] items) {
        if (items == null || items.length == 0) return null;
        return items[items.length];
    }
}
""",
        "after_code": """package com.example.queues;

public class QueueProcessor {
    public String getLastItem(String[] items) {
        if (items == null || items.length == 0) return null;
        return items[items.length - 1];
    }
}
"""
    },
    {
        "scenario_id": "FA-027",
        "title": "Missing parentheses in shipping cost calculation",
        "split": "HOLDOUT",
        "role": "correctness_logic",
        "finding_type": "presence",
        "eligibility_expected": True,
        "expected_fix_status": "generated",
        "expected_skip_reason_category": None,
        "file_path": "src/main/java/com/example/shipping/ShippingCostCalculator.java",
        "line": 5,
        "problem": "Incorrect subtraction in base rate addition: `baseRate - weight * ratePerKg` instead of `baseRate + weight * ratePerKg`.",
        "evidence": "return baseRate - weight * ratePerKg;",
        "difficulty": "HARD",
        "notes": "Fix `-` operator to `+`.",
        "before_code": """package com.example.shipping;

public class ShippingCostCalculator {
    public double computeCost(double baseRate, double weight, double ratePerKg) {
        return baseRate - weight * ratePerKg;
    }
}
""",
        "after_code": """package com.example.shipping;

public class ShippingCostCalculator {
    public double computeCost(double baseRate, double weight, double ratePerKg) {
        return baseRate + weight * ratePerKg;
    }
}
"""
    },

    # ------------------ HOLDOUT SPLIT: INELIGIBLE (3) ------------------
    {
        "scenario_id": "FA-028",
        "title": "Hardcoded JWT signature key",
        "split": "HOLDOUT",
        "role": "security_validation",
        "finding_type": "security",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "security_findings_not_auto_fixed",
        "file_path": "src/main/java/com/example/jwt/JwtTokenProvider.java",
        "line": 5,
        "problem": "Hardcoded private secret token for cryptographic signing in source file.",
        "evidence": "private String jwtSecret = \"private_jwt_secret_token_99\";",
        "difficulty": "EASY",
        "notes": "Security finding must be skipped.",
        "before_code": """package com.example.jwt;

public class JwtTokenProvider {
    private String jwtSecret = "private_jwt_secret_token_99";
    public String getSecret() { return jwtSecret; }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-029",
        "title": "Unhandled IOException in socket channel manager",
        "split": "HOLDOUT",
        "role": "correctness_logic",
        "finding_type": "absence",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "absence_type_not_auto_fixed",
        "file_path": "src/main/java/com/example/network/SocketChannelManager.java",
        "line": 5,
        "problem": "Missing error handling: SocketChannel open operation unhandled exception lacks recovery block.",
        "evidence": "channel.connect(address);",
        "difficulty": "MEDIUM",
        "notes": "Absence of error handling is excluded.",
        "before_code": """package com.example.network;
import java.net.SocketAddress;
import java.nio.channels.SocketChannel;

public class SocketChannelManager {
    public void init(SocketChannel channel, SocketAddress address) throws Exception {
        channel.connect(address);
    }
}
""",
        "after_code": None
    },
    {
        "scenario_id": "FA-030",
        "title": "Cross-file event bus contract change",
        "split": "HOLDOUT",
        "role": "correctness_logic",
        "finding_type": "multi_file",
        "eligibility_expected": False,
        "expected_fix_status": "skipped",
        "expected_skip_reason_category": "multi_file_not_supported",
        "file_path": "src/main/java/com/example/events/EventPublisher.java",
        "line": 5,
        "problem": "Event schema mismatch across files: publisher and subscriber types drifted.",
        "evidence": "eventBus.publish(new LegacyEvent(payload));",
        "difficulty": "HARD",
        "notes": "Cross-file refactoring is excluded in V1.",
        "before_code": """package com.example.events;

public class EventPublisher {
    public void publish(String payload) {
        eventBus.publish(new LegacyEvent(payload));
    }
}
""",
        "after_code": None
    }
]

# Write scenarios and fixtures
scenarios_list = []
dev_ids = []
holdout_ids = []

for sc in SCENARIOS_DATA:
    sid = sc["scenario_id"]
    fix_dir = FIXTURES_DIR / sid
    os.makedirs(fix_dir, exist_ok=True)

    before_path = fix_dir / "before.java"
    before_path.write_text(sc["before_code"].strip() + "\n", encoding="utf-8")

    expected_after_rel = None
    if sc["after_code"]:
        after_path = fix_dir / "expected_after.java"
        after_path.write_text(sc["after_code"].strip() + "\n", encoding="utf-8")
        expected_after_rel = f"fixtures/{sid}/expected_after.java"

    scenario_entry = {
        "scenario_id": sid,
        "title": sc["title"],
        "split": sc["split"],
        "role": sc["role"],
        "finding_type": sc["finding_type"],
        "eligibility_expected": sc["eligibility_expected"],
        "expected_fix_status": sc["expected_fix_status"],
        "expected_skip_reason_category": sc["expected_skip_reason_category"],
        "file_path": sc["file_path"],
        "line": sc["line"],
        "problem": sc["problem"],
        "evidence": sc["evidence"],
        "source_fixture": f"fixtures/{sid}/before.java",
        "expected_after_fixture": expected_after_rel,
        "difficulty": sc["difficulty"],
        "notes": sc["notes"]
    }
    scenarios_list.append(scenario_entry)

    if sc["split"] == "DEV":
        dev_ids.append(sid)
    else:
        holdout_ids.append(sid)

# Write scenarios.json
scenarios_file = EVAL_DIR / "scenarios.json"
scenarios_file.write_text(json.dumps({"scenarios": scenarios_list}, indent=2), encoding="utf-8")
print(f"Written: {scenarios_file} ({len(scenarios_list)} scenarios)")

# Write splits.json
splits_data = {
    "DEV": dev_ids,
    "HOLDOUT": holdout_ids,
    "metadata": {
        "total_scenarios": len(scenarios_list),
        "dev_count": len(dev_ids),
        "holdout_count": len(holdout_ids),
        "policy": "HOLDOUT is strictly reserved for final evaluation. Do NOT tune prompts or eligibility rules on HOLDOUT."
    }
}
splits_file = EVAL_DIR / "splits.json"
splits_file.write_text(json.dumps(splits_data, indent=2), encoding="utf-8")
print(f"Written: {splits_file}")

# -----------------------------------------------------------------------------
# Write schema.json
# -----------------------------------------------------------------------------
schema_data = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FixAgentEvaluationSchema",
    "type": "object",
    "properties": {
        "scenario_id": {"type": "string"},
        "split": {"type": "string", "enum": ["DEV", "HOLDOUT"]},
        "role": {"type": "string", "enum": ["correctness_logic", "maintainability", "security_validation"]},
        "finding_type": {"type": "string"},
        "eligibility_expected": {"type": "boolean"},
        "expected_fix_status": {"type": "string", "enum": ["generated", "skipped"]},
        "expected_skip_reason_category": {"type": ["string", "null"]},
        "file_path": {"type": "string"},
        "line": {"type": "integer"},
        "problem": {"type": "string"},
        "evidence": {"type": "string"},
        "source_fixture": {"type": "string"},
        "expected_after_fixture": {"type": ["string", "null"]},
        "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD"]}
    },
    "required": ["scenario_id", "split", "role", "finding_type", "eligibility_expected", "expected_fix_status", "file_path", "line", "problem", "source_fixture", "difficulty"]
}
(EVAL_DIR / "schema.json").write_text(json.dumps(schema_data, indent=2), encoding="utf-8")
print("Written: schema.json")
