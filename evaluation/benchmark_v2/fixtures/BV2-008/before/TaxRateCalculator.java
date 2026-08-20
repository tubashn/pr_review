package com.nexus.pricing.policy;

public class TaxRateCalculator {
    public boolean isVatExempt(String countryCode) {
        return "US".equalsIgnoreCase(countryCode);
    }
}
