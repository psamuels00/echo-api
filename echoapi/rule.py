import typing


class Rule(typing.NamedTuple):

    rule_source: str       # '' if directly from _echo_response, or name of file otherwise
    after: int             # eg: 200, represents number of milliseconds after start/reset of echo server
    selector_type: str     # one of { PATH, HEADER, PARAM, JSON, BODY }
    selector_target: str   # name of header, parameter, or json field
    pattern: str           # eg: /test/ or /Test/i or !/test/
    status_code: int       # eg: 200
    delay: int             # eg: 200, represents number of milliseconds to delay
    location: list         # list of values, each one of { file, text }
    headers: list          # [ {},... ]
    values: list           # [ [...],... ]

    def unique_id(self, request_path):
        after = str(self.after or 0)
        selector_type = '' if self.selector_type is None else self.selector_type
        selector_target = '' if self.selector_target is None else self.selector_target
        pattern = '' if self.pattern is None else self.pattern
        return ':'.join((request_path, self.rule_source, selector_type, selector_target, pattern, after))

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
            values
        )

    def at_offset(self, offset):
        locations = self.location[offset]
        values = self.values[offset]

        rules = []
        while locations and locations[0] == 'file':
            headers = self.headers[offset]
            rule = self.rule4location(locations.pop(0), headers, values.pop(0))
            rules.append(rule)

        if values:
            headers = self.headers[offset]
            rule = self.rule4location(locations.pop(0), headers, values)
            rules.append(rule)

        return rules
