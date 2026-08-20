package com.nexus.payment.settlement;

import java.math.BigDecimal;
import org.springframework.stereotype.Service;

@Service
public class RefundValidator {
    public boolean isRefundAmountValid(BigDecimal refundAmount, BigDecimal totalCaptured) {
        return refundAmount.compareTo(BigDecimal.ZERO) > 0 && refundAmount.compareTo(totalCaptured) <= 0;
    }
}
