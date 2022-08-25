from flask import request

import re
import typing


class Rule(typing.NamedTuple):

    rule_source: str  # "" if directly from _echo_response, or name of file otherwise
    after: int  # eg: 200, represents number of milliseconds after start/reset of echo server
    selector_type: str  # one of { PATH, HEADER, PARAM, JSON, BODY }
    selector_target: str  # name of header, parameter, or json field
    pattern: str  # eg: /test/ or /Test/i or !/test/
    status_code: int  # eg: 200
    delay: int  # eg: 200, represents number of milliseconds to delay
    location: list  # list of values, each one of { file, text }
    headers: list  # [ {},... ]
    values: list  # [ [...],... ]

    def unique_id(self, request_path):
        after = str(self.after or 0)
        selector_type = "" if self.selector_type is None else self.selector_type
        selector_target = "" if self.selector_target is None else self.selector_target
        pattern = "" if self.pattern is None else self.pattern
        return ":".join((request_path, self.rule_source, selector_type, selector_target, pattern, after))

    def rule4location(self, location, headers, values):
        return Rule(
            self.rule_source,
            self.after,
            self.selector_type,
            self.selector_target,
            self.pattern,
            self.status_code,
            self.delay,
            location,
            headers,
            values,
        )

    def at_offset(self, offset):
        locations = self.location[offset]
        values = self.values[offset]

        rules = []
        while locations and locations[0] == "file":
            headers = self.headers[offset]
            rule = self.rule4location(locations.pop(0), headers, values.pop(0))
            rules.append(rule)

        if values:
            headers = self.headers[offset]
            rule = self.rule4location(locations.pop(0), headers, values)
            rules.append(rule)

        return rules

    def _text(self, headers, params, json):
        value = None

        if self.selector_type == "HEADER":
            header_name = self.selector_target
            value = headers.get(header_name, "")

        elif self.selector_type == "PATH":
            value = request.path

        elif self.selector_type == "PARAM":
            param_name = self.selector_target
            value = params.get(param_name, "")

        elif self.selector_type == "JSON":
            json_path = self.selector_target
            fmt = "{json." + json_path + "}"
            value = fmt.format(json=json)

        elif self.selector_type == "BODY":
            body = request.get_data().decode()
            value = body

        return value

    def _matches(self, text):
        # set case-sensitive flag
        flags = 0
        if self.pattern[-1] == "i":
            flags = re.IGNORECASE

        # determine match polarity
        is_positive = True
        if self.pattern[0] == "!":
            is_positive = False

        # parse pattern text from pattern spec, eg: parse "dog" from "!/dog/i"
        pattern = re.sub(r".*/(.*)/.*", r"\1", self.pattern)

        got_match = False
        text_match = re.search(pattern, text, flags)
        if is_positive and text_match:
            got_match = True
        elif not is_positive and not text_match:
            got_match = True

        return got_match

    def apply(self, headers, params, json, millis_since_reset):
        if self.selector_type is None:
            value = True
        else:
            text = self._text(headers, params, json)
            value = self._matches(text)

        if millis_since_reset <= int(self.after or 0):
            value = False

        return value

