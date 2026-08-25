package com.example.xml;

public class DomTreeBuilder {
    public String buildTree() {
        StringBuilder sb = new StringBuilder();
        // 25 lines of node concatenation
        sb.append("<root>");
        sb.append("<child1/>");
        sb.append("<child2/>");
        sb.append("<child3/>");
        sb.append("<child4/>");
        sb.append("<child5/>");
        sb.append("<child6/>");
        sb.append("<child7/>");
        sb.append("<child8/>");
        sb.append("<child9/>");
        sb.append("<child10/>");
        sb.append("</root>");
        return sb.toString();
    }
}
