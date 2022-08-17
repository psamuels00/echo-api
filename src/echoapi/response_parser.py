from .rule import Rule
from .rules_adjuster import RulesAdjuster

import re


class ResponseParser:
    def __init__(self, rule_source, status_code, delay, after):
        """
        :param rule_source:
            file that rule comes from, or "" if directly from _echo_response param value.
            used to identify a rule for match counting in support of sequenced content
        :param status_code:
            default status code (global default, inherited, or preceding any rules)
        :param delay:
            default status code (global default, inherited, or preceding any rules)
        """
        self.rule_source = rule_source  # will not change
        self.status_code = status_code  # will be updated if rule-specific value is parsed
        self.delay = delay  # will be updated if rule-specific value is parsed
        self.after = after  # will be updated if rule-specific value is parsed
        self.lines = None  # used by parse() to support parsing elements at beginning of line
        self.is_sequenced = False  # used by parse() to know if text is part of sequenced content
        self.rules = []  # returned by parse(), this is the primary product of parsing
        self.global_scope = True

    def parse(self, text):
        self.lines = self.parse_response_into_lines(text)

        while self.lines:
            line = self.lines.pop(0)
            self.parse_line(line)

        is_from_file = False if self.rule_source == "" else True
        rulesAdjuster = RulesAdjuster(is_from_file, self.rules)
        rulesAdjuster.adjust()

        return self.status_code, self.delay, self.rules

    def parse_response_into_lines(self, text):
        # remove one of [|@>] from beginning of text to avoid creating an extra blank line
        # by the sub() command below
        m = re.match(r"[|@>]\s*(.*)", text, re.DOTALL)
        if m:
            text = m.group(1)

        # replace one of [|@>] with newline if it precedes a selector type or location specifier
        multiline = re.sub(r"[|@>]\s*((HEADER|PATH|PARAM|JSON|BODY|text|file):)", r"\n\1", text)

        return multiline.splitlines(keepends=True)

    def parse_line(self, line):
        # comments are completely ignored, period
        if self.is_comment(line):
            pass

        # a match here implies there is no sequenced content yet
        elif self.global_scope and self.begins_with_status_code(line):
            pass
        elif self.global_scope and self.begins_with_delay(line):
            pass
        elif self.global_scope and self.begins_with_after(line):
            pass
        elif self.begins_with_separator(line):
            self.global_scope = False

        # a match here ends parsing of sequenced content and begins a new rule
        elif self.is_matching_header_rule(line):
            pass
        elif self.is_matching_path_rule(line):
            pass
        elif self.is_matching_param_rule(line):
            pass
        elif self.is_matching_json_rule(line):
            pass
        elif self.is_matching_body_rule(line):
            pass

        # a match here begins sequenced content and creates a rule if there are none yet
        elif self.begins_with_sequence_marker(line):
            pass

        # a match here creates a new rule or (if part of sequenced content) starts a new element in the current sequence
        elif self.is_matching_rule_with_explicit_location(line):
            pass

        # a match here adds to an existing text rule, whether part of sequenced content or not
        elif self.currently_processing_a_text_rule():
            # add to the currently being parsed element of sequenced content
            # any extra text is appended to value here, and further parsed by RulesAdjuster later
            self.rules[-1].values[-1].append(line)

        # blank lines are ignored before any rules or after a file rule
        elif self.is_blank(line):
            pass

        # a match here creates a new rule or (if part of sequenced content) starts a new element in the current sequence
        else:
            self.add_rule_with_implied_text_location(line)

        if self.rules:
            self.global_scope = False

    def currently_processing_a_text_rule(self):
        return (
            self.rules
            and len(self.rules[-1].location)
            and len(self.rules[-1].location[-1])
            and self.rules[-1].location[-1][-1] == "text"
        )

    def add_rule(self, selector_type, selector_target, pattern, status_code, delay, after, location, value):
        rule_source = self.rule_source
        selector_target = "" if selector_target is None else selector_target
        status_code = self.status_code if status_code is None else int(status_code)
        delay = self.delay if delay is None else int(delay)
        after = self.after if after is None else int(after)
        location = [[location or "text"]]  # a list to support sequenced content
        headers = []  # RulesAdjuster moves entries from values to headers, a list to support sequenced content
        content = [value]  # content is stored as a list of values, here initialized with the first value
        values = [content]  # to support sequenced content, we wrap the first content value in a list

        rule = Rule(
            rule_source,  # file that rule comes from, or "" if directly from _echo_response param value
            after,  # integer representing milliseconds
            selector_type,  # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,  # any regular expression
            status_code,  # integer HTTP response code
            delay,  # integer representing milliseconds
            location,  # a list of values, each one of { text, file }
            headers,  # dictionary of header values for multiple response content
            values,
        )  # arbitrary text, may include multiple response content values
        # if location is file, then the text will be the file path
        self.rules.append(rule)

    def add_if_match(self, line, pattern, groups, reset_sequence=True):
        m = re.match(pattern, line, re.DOTALL)
        if m:
            if reset_sequence:
                self.is_sequenced = False

            args = [m.group(n) if n else None for n in groups]

            if not self.is_sequenced:
                self.add_rule(*args)
            elif self.rules:
                _, _, _, _, _, _, location, value = args
                rule = self.rules[-1]
                rule.location[-1].append(location or "text")
                rule.values[-1].append(value)

            return True
        return False

    def is_comment(self, line):
        return re.match(r"\s*#", line)

    def is_blank(self, line):
        return re.match(r"\s*$", line)

    def begins_with_separator(self, line):
        # match 2 or more hyphens, not followed by "[ N ]--" (since "--[ N ]--" is how we start sequenced content
        m = re.match(r"\s*-{2,}(?!\[\s*\d+\s*\]--)\s*(.*)", line, re.DOTALL)
        if m:
            if len(m.group(1)) > 0:
                self.lines.insert(0, m.group(1))
            return True
        return False

    def begins_with_status_code(self, line):
        m = re.match(r"\s*(\d{3})\b\s*(.*)", line, re.DOTALL)
        if m:
            self.status_code = int(m.group(1))
            if len(m.group(2)) > 0:
                self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_delay(self, line):
        m = re.match(r"\s*delay\s*=(\d+)ms\b\s*(.*)", line, re.DOTALL)
        if m:
            self.delay = int(m.group(1))
            if len(m.group(2)) > 0:
                self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_after(self, line):
        m = re.match(r"\s*after\s*=(\d+)ms\b\s*(.*)", line, re.DOTALL)
        if m:
            self.after = int(m.group(1))
            if len(m.group(2)) > 0:
                self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_sequence_marker(self, line):
        m = re.match(r"\s*--\[\s*(\d*)\s*\]--\s*(.*)", line, re.DOTALL)
        if not m:
            return False

        if self.is_sequenced:
            self.rules[-1].location.append([])
            self.rules[-1].values.append([])
        else:
            if not self.rules:
                self.add_rule(None, None, None, None, None, None, "text", "")
            self.rules[-1].location.clear()
            self.rules[-1].location.append([])
            self.rules[-1].values.clear()  # TODO warn if we are tossing away content
            self.rules[-1].values.append([])
            self.is_sequenced = True

        if len(m.group(2)) > 0:
            self.lines.insert(0, m.group(2))

        return True

    # fmt: off

    def is_matching_header_rule(self, line):
        return self.add_if_match(line,
            r"\s*(HEADER):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?((text|file):)?\s*(.*)",
            (    1,          2,      3,             5,                   7,                 9,           11,              12  ))

    def is_matching_param_rule(self, line):
        return self.add_if_match(line,
            r"\s*(PARAM):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?((text|file):)?\s*(.*)",
            (    1,         2,      3,             5,                   7,                 9,           11,              12  ))

    def is_matching_json_rule(self, line):
        return self.add_if_match(line,
            r"\s*(JSON):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?((text|file):)?\s*(.*)",
            (    1,        2,      3,             5,                   7,                 9,           11,              12  ))

    def is_matching_path_rule(self, line):
        return self.add_if_match(line,
            r"\s*(PATH):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?((text|file):)?\s*(.*)",
            (    1,     0, 2,             4,                   6,                 8,           10,              11  ))

    def is_matching_body_rule(self, line):
        return self.add_if_match(line,
            r"\s*(BODY):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?((text|file):)?\s*(.*)",
            (    1,     0, 2,             4,                   6,                 8,           10,              11  ))

    def is_matching_rule_with_explicit_location(self, line):
        return self.add_if_match(line,
            r"\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(after=(\d+)ms\s*)?(text|file):\s*(.*)",
            (0,0,0,2,                  4,                 6,          7,             8   ),
            reset_sequence=False)

    def add_rule_with_implied_text_location(self, line):
        return self.add_if_match(line,
            r"(\s*(\d{3})\b)?(\s*delay=(\d+)ms)?(\s*after=(\d+)ms)?(.*)",
            (0,0,0,2,                  4,                 6,    0, 7   ),
            reset_sequence=False)

    # fmt: on
