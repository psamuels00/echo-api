from .response_parser import ResponseParser

from flask import request

import re
import time


class Rules:

    last_reset_time_in_millis = 0
    rule_match_count = {}

    def __init__(self, request_path, rule_source, text, default_status_code, default_delay, default_after):
        self.request_path = request_path
        response_parser = ResponseParser(rule_source, default_status_code, default_delay, default_after)
        self.status_code, self.delay, self.rules = response_parser.parse(text)

    @staticmethod
    def current_time_in_millis():
        return int(round(time.time() * 1000))

    def num_rules(self):
        return len(self.rules)

    @staticmethod
    def matches(text, rule_pattern):
        # set case-sensitive flag
        flags = 0
        if rule_pattern[-1] == 'i':
            flags = re.IGNORECASE

        # determine match polarity
        is_positive = True
        if rule_pattern[0] == '!':
            is_positive = False

        # parse pattern text from pattern spec, eg: parse "dog" from "!/dog/i"
        pattern = re.sub(r'.*/(.*)/.*', r'\1', rule_pattern)

        got_match = False
        text_match = re.search(pattern, text, flags)
        if is_positive and text_match:
            got_match = True
        elif not is_positive and not text_match:
            got_match = True

        return got_match

    def select_content_from_list(self, rule):
        rule_id = rule.unique_id(self.request_path)
        match_count = self.rule_match_count.get(rule_id, 0)
        self.rule_match_count[rule_id] = match_count + 1

        offset = match_count % len(rule.values)
        return rule.at_offset(offset)

    def rule_selector_generator(self, headers, params, json):
        for rule in self.rules:
            apply_rule = False
            if rule.selector_type is None:
                apply_rule = True
            else:
                text = None
                if rule.selector_type == 'HEADER':
                    header_name = rule.selector_target
                    text = headers.get(header_name, '')

                elif rule.selector_type == 'PATH':
                    text = request.path

                elif rule.selector_type == 'PARAM':
                    param_name = rule.selector_target
                    text = params.get(param_name, '')

                elif rule.selector_type == 'JSON':
                    json_path = rule.selector_target
                    fmt = '{json.' + json_path + '}'
                    text = fmt.format(json=json)

                elif rule.selector_type == 'BODY':
                    body = request.get_data().decode()
                    text = body

                if self.matches(text, rule.pattern):
                    apply_rule = True

            millis_since_reset = Rules.current_time_in_millis() - self.last_reset_time_in_millis
            if millis_since_reset <= int(rule.after or 0):
                apply_rule = False

            if apply_rule:
                # we get a list of rules here since there could be multiple locations in sequenced content
                rules = self.select_content_from_list(rule)
                # once a match is made on one rule, we can stop checking for more rules so all
                # the rules will not necessarily be yielded or "pulled through" via next()
                for _ in rules:
                    yield _
