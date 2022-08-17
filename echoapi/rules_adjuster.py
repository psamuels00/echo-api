import re


class RulesAdjuster:

    # eg: HEADER: Accept: compressed
    header_line_pat = re.compile(r"\s*HEADER:\s*(.+)\s*:\s*(.*)")

    def __init__(self, is_from_file, rules):
        self.is_from_file = is_from_file
        self.rules = rules

    def adjust(self):
        for rule in self.rules:
            self.adjust_rule(rule)

    def adjust_rule(self, rule):
        values = rule.values.copy()
        rule.values.clear()
        rule.headers.clear()  # it should already be empty

        for lines in values:
            self.adjust_rule_content(lines, rule)

    def adjust_rule_content(self, lines, rule):
        headers = {}

        # move headers from value to headers field
        while lines and self.rule_content_begins_with_header(lines, headers):
            pass

        # remove whitespace before first line of content, unless it is from a file
        if lines and not self.is_from_file:
            lines[0] = lines[0].lstrip()

        rule.values.append(lines)
        rule.headers.append(headers)

    def rule_content_begins_with_header(self, lines, headers):
        m = re.match(self.header_line_pat, lines[0])
        if m:
            headers[m.group(1)] = m.group(2)
            lines.pop(0)
            return True
        return False
