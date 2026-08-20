package com.nexus.subscription.renewal;

import java.time.LocalDate;
import org.springframework.stereotype.Service;

@Service
public class GracePeriodEvaluator {
    public boolean isAccountInGracePeriod(LocalDate now, LocalDate expiryDate, int graceDays) {
        return now.isAfter(expiryDate) && now.isBefore(expiryDate);
    }
}
