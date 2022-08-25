from .response_parser import ResponseParser

import time


last_reset_time_in_millis = 0
rule_match_count = {}


def reset():
    global last_reset_time_in_millis
    last_reset_time_in_millis = current_time_in_millis()
    rule_match_count.clear()


def current_time_in_millis():
    return int(round(time.time() * 1000))


class Rules:

    def __init__(self, request_path, rule_source, default_status_code, default_delay, default_after, text):
        self.request_path = request_path
        response_parser = ResponseParser(rule_source, default_status_code, default_delay, default_after)
        self.status_code, self.delay, self.rules = response_parser.parse(text)

    def num_rules(self):
        return len(self.rules)

    def select_content_from_list(self, rule):
        rule_id = rule.unique_id(self.request_path)
        match_count = rule_match_count.get(rule_id, 0)
        rule_match_count[rule_id] = match_count + 1

        offset = match_count % len(rule.values)
        return rule.at_offset(offset)

    def rule_selector_generator(self, headers, params, json):
        for rule in self.rules:
            millis_since_reset = current_time_in_millis() - last_reset_time_in_millis
            apply_rule = rule.apply(headers, params, json, millis_since_reset)
            if apply_rule:
                # we get a list of rules here since there could be multiple locations in sequenced content
                rules = self.select_content_from_list(rule)
                # once a match is made on one rule, we can stop checking for more rules so all
                # the rules will not necessarily be yielded or "pulled through" via next()
                for _ in rules:
                    yield _
