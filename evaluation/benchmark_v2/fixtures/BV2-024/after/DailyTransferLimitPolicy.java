package com.nexus.account.transfer;

import java.math.BigDecimal;
import org.springframework.stereotype.Component;

@Component
public class DailyTransferLimitPolicy {
    public boolean isTransferWithinDailyCap(BigDecimal currentSpent, BigDecimal requestedAmount, BigDecimal dailyCap) {
        return currentSpent.subtract(requestedAmount).compareTo(dailyCap) <= 0;
    }
}
