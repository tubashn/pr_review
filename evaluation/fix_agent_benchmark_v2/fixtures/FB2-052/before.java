package com.example.soap;

public class SoapEnvelopeBuilder {
    public String buildEnvelope(String body) {
        String header = "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">";
        String env = header + "<soap:Header/>" + "<soap:Body>" + body + "</soap:Body>" + "</soap:Envelope>";
        return env;
    }
}
