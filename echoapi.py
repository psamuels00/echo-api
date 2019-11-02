#!/usr/bin/env python

from box import Box
from flask import Flask, request, Response

import os
import re
import time
import typing


app = Flask(__name__)


class Rule(typing.NamedTuple):

    rule_source: str       # '' if directly from _echo_response, or name of file otherwise
    selector_type: str     # one of { PATH, HEADER, PARAM, JSON, BODY }
    selector_target: str   # name of header, parameter, or json field
    pattern: str           # eg: /test/ or /Test/i or !/test/
    status_code: int       # eg: 200
    delay: int             # eg: 200, represents number of milliseconds to delay
    location: list         # list of values, each one of { file, text }
    headers: list          # [ {},... ]
    values: list           # [ [...],... ]

    def unique_id(self, request_path):
        selector_type = '' if self.selector_type is None else self.selector_type
        selector_target = '' if self.selector_target is None else self.selector_target
        pattern = '' if self.pattern is None else self.pattern
        return ':'.join((request_path, self.rule_source, selector_type, selector_target, pattern))

    def rule4location(self, offset, location, values):
        return Rule(
            self.rule_source,
            self.selector_type,
            self.selector_target,
            self.pattern,
            self.status_code,
            self.delay,
            location,
            self.headers[offset],
            values
        )

    def at_offset(self, offset):
        locations = self.location[offset]
        values = self.values[offset]

        rules = []
        while locations and locations[0] == 'file':
            rule = self.rule4location(offset, locations.pop(0), values.pop(0))
            rules.append(rule)

        if values:
            rule = self.rule4location(offset, [['text']], values)
            rules.append(rule)

        return rules


class Rules:

    rule_match_count = {}

    def __init__(self, request_path, rule_source, text, default_status_code, default_delay):
        self.request_path = request_path
        responseParser = ResponseParser(rule_source, default_status_code, default_delay)
        self.status_code, self.delay, self.rules = responseParser.parse(text)

    def num_rules(self):
        return len(self.rules)

    def matches(self, text, rule_pattern):
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

            if apply_rule:
                # we get a list of rules here since there could be multiple locations in sequenced content
                rules = self.select_content_from_list(rule)
                # once a match is made on one rule, we can stop checking for more rules so all
                # the rules will not necessarily be yielded or "pulled through" via next()
                for rule in rules:
                    yield rule


class ResponseParser:
    def __init__(self, rule_source, status_code, delay):
        """
        :param rule_source:
            file that rule comes from, or '' if directly from _echo_response param value.
            used to identify a rule for match counting in support of sequenced content
        :param status_code:
            default status code (global default, inherited, or preceding any rules)
        :param delay:
            default status code (global default, inherited, or preceding any rules)
        """
        self.rule_source = rule_source  # will not change
        self.status_code = status_code  # will be updated if rule-specific value is parsed
        self.delay = delay              # will be updated if rule-specific value is parsed
        self.lines = None               # used by parse() to support parsing elements at beginning of line
        self.is_sequenced = False       # used by parse() to know if text is part of sequenced content
        self.rules = []                 # returned by parse(), this is the primary product of parsing

    def parse(self, text):
        self.lines = self.parse_response_into_lines(text)

        while self.lines:
            line = self.lines.pop(0)
            self.parse_line(line)

        is_from_file = False if self.rule_source == '' else True
        rulesAdjuster = RulesAdjuster(is_from_file, self.rules)
        rulesAdjuster.adjust()

        return self.status_code, self.delay, self.rules

    def parse_response_into_lines(self, text):
        # remove one of [|@>] from beginning of text to avoid creating an extra blank line
        # by the sub() command below
        m = re.match(r'[|@>]\s*(.*)', text, re.DOTALL)
        if m:
            text = m.group(1)

        # replace one of [|@>] with newline if it precedes a selector type or location specifier
        multiline = re.sub(r'[|@>]\s*((HEADER|PATH|PARAM|JSON|BODY|text|file):)', r'\n\1', text)

        return multiline.splitlines(keepends=True)

    def parse_line(self, line):
        # comments are completely ignored, period
        if self.is_comment(line):
            pass

        # a match here implies there is no sequenced content yet
        elif not self.rules and self.begins_with_status_code(line):
            pass
        elif not self.rules and self.begins_with_delay(line):
            pass

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
        elif self.rules \
                and len(self.rules[-1].location) \
                and len(self.rules[-1].location[-1]) \
                and self.rules[-1].location[-1][-1] == 'text':
            # add to the content of the most recent rule, which is a text rule
            # add to the currently being parsed element of sequenced content
            # any extra text is appended to value here, and further parsed by RulesAdjuster later
            self.rules[-1].values[-1].append(line)

        # blank lines are ignored before any rules or after a file rule
        elif self.is_blank(line):
            pass

        # a match here creates a new rule or (if part of sequenced content) starts a new element in the current sequence
        else:
            self.add_rule_with_implied_text_location(line)

    def add_rule(self, selector_type, selector_target, pattern, status_code, delay, location, value):
        rule_source = self.rule_source
        selector_target = '' if selector_target is None else selector_target
        status_code = self.status_code if status_code is None else int(status_code)
        delay = self.delay if delay is None else int(delay)
        location = [ [location or 'text'] ] # a list to support sequenced content
        headers = [] # RulesAdjuster moves entries from values to headers, a list to support sequenced content
        content = [value] # content is stored as a list of values, here initialized with the first value
        values = [content] # to support sequenced content, we wrap the first content value in a list

        rule = Rule(
            rule_source,      # file that rule comes from, or '' if directly from _echo_response param value
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            status_code,      # integer HTTP response code
            delay,            # integer representing milliseconds
            location,         # a list of values, each one of { text, file }
            headers,          # dictionary of header values for multiple response content
            values)           # arbitrary text, may include multiple response content values
                              # if location is file, then the text will be the file path
        self.rules.append(rule)

    def add_if_match(self, line, pattern, groups, reset_sequence=True):
        m = re.match(pattern, line, re.DOTALL)
        if m:
            if reset_sequence:
                self.is_sequenced = False

            args = [ m.group(n) if n else None
                     for n in groups ]

            if not self.is_sequenced:
                self.add_rule(*args)
            elif self.rules:
                _, _, _, _, _, location, value = args
                rule = self.rules[-1]
                rule.location[-1].append(location or 'text')
                rule.values[-1].append(value)

            return True
        return False

    def is_comment(self, line):
        return re.match(r'\s*#', line)

    def is_blank(self, line):
        return re.match(r'\s*$', line)

    def begins_with_status_code(self, line):
        m = re.match(r'\s*(\d{3})\b\s*(.*)', line, re.DOTALL)
        if m:
            self.status_code = int(m.group(1))
            if len(m.group(2)) > 0:
                self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_delay(self, line):
        m = re.match(r'\s*delay\s*=(\d+)ms\b\s*(.*)', line, re.DOTALL)
        if m:
            self.delay = int(m.group(1))
            if len(m.group(2)) > 0:
                self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_sequence_marker(self, line):
        m = re.match(r'\s*--\[\s*(\d*)\s*\]--\s*(.*)', line, re.DOTALL)
        if not m:
            return False

        if self.is_sequenced:
            self.rules[-1].location.append([])
            self.rules[-1].values.append([])
        else:
            if not self.rules:
                self.add_rule(None, None, None, None, None, 'text', '')
            self.rules[-1].location.clear()
            self.rules[-1].location.append([])
            self.rules[-1].values.clear()  # TODO warn if we are tossing away content
            self.rules[-1].values.append([])
            self.is_sequenced = True

        if len(m.group(2)) > 0:
            self.lines.insert(0, m.group(2))

        return True

    def is_matching_header_rule(self, line):
        return self.add_if_match(line,
            r'\s*(HEADER):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,          2,      3,             5,                   7,           9,               10  ))

    def is_matching_path_rule(self, line):
        return self.add_if_match(line,
            r'\s*(PATH):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0, 2,             4,                   6,           8,               9   ))

    def is_matching_param_rule(self, line):
        return self.add_if_match(line,
            r'\s*(PARAM):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,         2,      3,             5,                   7,           9,               10  ))

    def is_matching_json_rule(self, line):
        return self.add_if_match(line,
            r'\s*(JSON):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,        2,      3,             5,                   7,           9,               10  ))

    def is_matching_body_rule(self, line):
        return self.add_if_match(line,
            r'\s*(BODY):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0, 2,             4,                   6,           8,               9   ))

    def is_matching_rule_with_explicit_location(self, line):
        return self.add_if_match(line,
            r'\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(text|file):\s*(.*)',
            (0,0,0,2,                  4,          5,             6  ),
            reset_sequence=False)

    def add_rule_with_implied_text_location(self, line):
        return self.add_if_match(line,
            r'(\s*(\d{3})\b)?(\s*delay=(\d+)ms)?(.*)',
            (0,0,0,2,                  4,    0, 5   ),
            reset_sequence=False)


class RulesAdjuster:

    # eg: HEADER: Accept: compressed
    header_line_pat = re.compile(r'\s*HEADER:\s*(.+)\s*:\s*(.*)')

    def __init__(self, is_from_file, rules):
        self.is_from_file = is_from_file
        self.rules = rules

    def adjust(self):
        for rule in self.rules:
            self.adjust_rule(rule)

    def adjust_rule(self, rule):
        values = rule.values.copy()
        rule.values.clear()
        rule.headers.clear() # it should already be empty

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


class RulesTemplate:

    def __init__(self, request_path='', text=''):
        self.request_path = request_path
        self.text = text

    def resolve_value(self, value, headers, params, json):
        def double_braces(string):
            string = re.sub(r'{([^\w])', r'{{\1', string) # { not followed by word char is converted to {{
            string = re.sub(r'([^\w])}', r'\1}}', string) # } not preceded by word char is converted to }}
            return string
        def single_braces(string):
            string = re.sub(r'{{([^\w])', r'{\1', string) # {{ not followed by word char is converted to {
            string = re.sub(r'([^\w])}}', r'\1}', string) # }} not preceded by word char is converted to }
            return string
        if headers or params or json:
            p = params.copy()
            p['json'] = json
            p['header'] = headers
            value = double_braces(value)
            value = value.format(**p)
            value = single_braces(value)
        return value

    def load_file(self, file):
        path = os.path.join('responses', file)
        with open(path, 'r') as fh:
            text = fh.read()
        return text

    def resolve(self, headers, params, json):
        default_status_code = 200
        default_delay = 0
        text = self.resolve_value(self.text, headers, params, json)
        return self.select_content('', text, default_status_code, default_delay, headers, params, json)

    def resolve_file(self, file, default_status_code, default_delay, headers, params, json, level):
        text = self.load_file(file)
        if not file.endswith('.echo'):
            return default_delay, {}, default_status_code, text
        text = self.resolve_value(text, headers, params, json)
        return self.select_content(file, text, default_status_code, default_delay, headers, params, json, level)

    def select_content(self, rule_source, text, default_status_code, default_delay, headers, params, json, level=0):
        rules = Rules(self.request_path, rule_source, text, default_status_code, default_delay)
        rule_selector = rules.rule_selector_generator(headers, params, json)

        delay = rules.delay
        headers = {}
        status = rules.status_code
        content = ''

        if rules.num_rules() == 0:
            return delay, headers, status, content

        content = None

        while content is None:
            try:
                rule = next(rule_selector)
            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return '' instead of None
                if level == 0:
                    content = ''
                break

            delay = rule.delay
            headers = rule.headers
            status = rule.status_code
            content = ''.join(rule.values)

            if rule.location == 'file':
                file = content.strip()
                delay, headers, status, content = self.resolve_file(
                    file, status, delay, headers, params, json, level + 1)

        return delay, headers, status, content


class EchoServer:

    param_pat = re.compile('^(\w+):(.*)$')
    param_value_pat = re.compile(':\w+')

    def __init__(self, path):
        self.request_path = re.sub(self.param_value_pat, '', path)
        self.parse_headers()
        self.parse_request_path(path)
        self.parse_response_parameter()
        self.parse_json_body()

    def parse_headers(self):
        self.headers = None  # Box of request headers
        headers = {}
        for header in request.headers.keys():
            headers[header] = request.headers.get(header)
        self.headers = Box(headers)

    def parse_request_path(self, path):
        self.path = path         # the request path
        self.path_params = {}    # params parsed from path

        parts = path.split('/')
        for part in parts:
            m = self.param_pat.search(part)
            if m:
                name, content = m.group(1), m.group(2)
                self.path_params[name] = content

    def parse_response_parameter(self):
        echo_response = request.args.get('_echo_response', '')
        self.content = echo_response.lstrip()

    def parse_json_body(self):
        self.json = None  # Box of json object from the request body
        json = request.get_json() or {}
        self.json = Box(json)

    def all_params(self):
        params = { k: v for k, v in request.args.items() }
        return { **self.path_params, **params }

    def response(self):
        content = self.content
        headers = self.headers
        params = self.all_params()
        json = self.json

        template = RulesTemplate(self.request_path, content)
        delay, headers, status, content = template.resolve(headers, params, json)
        resp = Response(content, headers=headers, status=status)

        return delay, resp


@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    delay, resp = server.response()
    if delay:
        time.sleep(delay/1000)
    return resp


@app.route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def root_path():
    return all_routes('/')


@app.route('/_echo_reset', methods=['GET'])
def reset():
    Rules.rule_match_count.clear()
    return 'ok'


@app.route('/_echo_list_rules', methods=['GET'])
def list_rules(): # for debugging
    keys = Rules.rule_match_count.keys()
    for k in sorted(keys):
        v = Rules.rule_match_count[k]
        print(f'@@@ {v:5} {k}')
    return 'ok'


if __name__ == '__main__':
    app.run()

