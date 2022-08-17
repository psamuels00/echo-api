from .rules import Rules

import os
import re


class RulesTemplate:
    def __init__(self, request_path="", text=""):
        self.request_path = request_path
        self.text = text

    @staticmethod
    def resolve_value(value, headers, params, json):
        def double_braces(string):
            string = re.sub(r"{([^\w])", r"{{\1", string)  # "{" not followed by word char is converted to "{{"
            string = re.sub(r"([^\w])}", r"\1}}", string)  # "}" not preceded by word char is converted to "}}"
            return string

        def single_braces(string):
            string = re.sub(r"{{([^\w])", r"{\1", string)  # "{{" not followed by word char is converted to "{"
            string = re.sub(r"([^\w])}}", r"\1}", string)  # "}}" not preceded by word char is converted to "}"
            return string

        if headers or params or json:
            p = params.copy()
            p["json"] = json
            p["header"] = headers
            value = double_braces(value)
            value = value.format(**p)
            value = single_braces(value)
        return value

    @staticmethod
    def load_file(file):
        path = os.path.join("responses", file)
        with open(path, "r") as fh:
            text = fh.read()
        return text

    def resolve(self, headers, params, json):
        default_status_code = 200
        default_delay = 0
        default_after = 0
        text = self.resolve_value(self.text, headers, params, json)
        return self.select_content("", text, default_status_code, default_delay, default_after, headers, params, json)

    def resolve_file(self, file, default_status_code, default_delay, default_after, headers, params, json, level):
        text = self.load_file(file)
        if not file.endswith(".echo"):
            return default_delay, default_status_code, {}, text
        text = self.resolve_value(text, headers, params, json)
        return self.select_content(
            file, text, default_status_code, default_delay, default_after, headers, params, json, level
        )

    def select_content(
        self, rule_source, text, default_status_code, default_delay, default_after, headers, params, json, level=0
    ):
        rules = Rules(self.request_path, rule_source, text, default_status_code, default_delay, default_after)
        rule_selector = rules.rule_selector_generator(headers, params, json)

        delay = rules.delay
        headers = {}
        status = rules.status_code
        content = ""

        if rules.num_rules() == 0:
            return delay, status, headers, content

        content = None

        while content is None:
            try:
                rule = next(rule_selector)
            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return "" instead of None
                if level == 0:
                    content = ""
                break

            delay = rule.delay
            after = rule.after
            headers = rule.headers
            status = rule.status_code
            content = "".join(rule.values)

            if rule.location == "file":
                file = content.strip()
                delay, status, headers, content = self.resolve_file(
                    file, status, delay, after, headers, params, json, level + 1
                )

        return delay, status, headers, content
