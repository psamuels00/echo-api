#!/usr/bin/env python

from box import Box
from collections import namedtuple
from flask import Flask, request, Response

import os
import re
import time


app = Flask(__name__)


Rule = namedtuple('Rule', [
    'rule_source',
    'selector_type',
    'selector_target',
    'pattern',
    'status_code',
    'delay',
    'location',
    'headers',
    'value'
])


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
        selector_type = '' if rule.selector_type is None else rule.selector_type
        selector_target = '' if rule.selector_target is None else rule.selector_target
        pattern = '' if rule.pattern is None else rule.pattern

        rule_id = ':'.join((self.request_path, rule.rule_source, selector_type, selector_target, pattern))
        match_count = self.rule_match_count.get(rule_id, 0)
        offset = match_count % len(rule.value)
        self.rule_match_count[rule_id] = match_count + 1
        print(f'\n@@@  {offset}  [{rule_id}]')

        return Rule(
            rule.rule_source,      # file that rule comes from, or '' if directly from _response param value
            selector_type,         # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,       # eg: id, or sample.location.name
            pattern,               # any regular expression
            rule.status_code,      # integer HTTP response code
            rule.delay,            # integer representing milliseconds
            rule.location,         # one of { text, file }
            rule.headers[offset],  # dictionary of header values for a single response content
            rule.value[offset])    # arbitrary text, a single response content value

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
                rule = self.select_content_from_list(rule)
                yield rule


class ResponseParser:
    def __init__(self, rule_source, status_code, delay):
        self.rule_source = rule_source  # file that rule comes from, or '' if directly from _response param value
        self.status_code = status_code  # default status code (global default, inherited, or preceding any rules)
        self.delay = delay              # default status code (global default, inherited, or preceding any rules)
        self.lines = None               # used by parse() for elements at beginning of line
        self.rules = []                 # returned by parse()

    def parse(self, text):
        self.lines = self.parse_response_into_lines(text)

        while self.lines:
            line = self.lines.pop(0)
            self.parse_line(line)

        rulesAdjuster = RulesAdjuster()
        rulesAdjuster.adjust(self.rules)

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
        if self.is_comment(line):
            pass
        elif not self.rules and self.begins_with_status_code(line):
            pass
        elif not self.rules and self.begins_with_delay(line):
            pass
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
        elif self.is_matching_rule_with_explicit_location(line):
            pass
        elif self.rules and self.rules[-1].location == 'text':
            # add to the content of the most recent rule, which is a text rule
            rule = self.rules[-1]
            # any extra text is appended to value here, but further parsed by RulesAdjuster later
            rule.value.append(line)
        elif self.is_blank(line):
            # ignore blank lines before any rules or after a file rule
            pass
        else:
            self.add_rule_with_implied_text_location(line)

    def add_rule(self, selector_type, selector_target, pattern, status_code, delay, location, value):
        rule_source = self.rule_source
        status_code = self.status_code if status_code is None else int(status_code)
        delay = self.delay if delay is None else int(delay)
        location = location or 'text'
        headers = []  # RulesAdjuster moves entries from value to headers

        if selector_target is None:
            selector_target = ''

        rule = Rule(
            rule_source,      # file that rule comes from, or '' if directly from _response param value
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            status_code,      # integer HTTP response code
            delay,            # integer representing milliseconds
            location,         # one of { text, file }
            headers,          # dictionary of header values for multiple response content
            [value])          # arbitrary text, may include multiple response content values, will be parsed by RulesAdjuster
        self.rules.append(rule)

    def add_rule_if_match(self, line, pattern, groups):
        m = re.match(pattern, line, re.DOTALL)
        if m:
            args = [ m.group(n) if n else None
                     for n in groups ]
            self.add_rule(*args)
            return True
        return False

    def is_comment(self, line):
        return re.match(r'\s*#', line)

    def begins_with_status_code(self, line):
        m = re.match(r'\s*(\d{3})\b\s*(.*)', line, re.DOTALL)
        if m:
            self.status_code = int(m.group(1))
            self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_delay(self, line):
        m = re.match(r'\s*delay\s*=(\d+)ms\b\s*(.*)', line, re.DOTALL)
        if m:
            self.delay = int(m.group(1))
            self.lines.insert(0, m.group(2))
            return True
        return False

    def is_matching_header_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(HEADER):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,          2,      3,             5,                   7,           9,               10  ))

    def is_matching_path_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PATH):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0, 2,             4,                   6,           8,               9   ))

    def is_matching_param_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PARAM):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,         2,      3,             5,                   7,           9,               10  ))

    def is_matching_json_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(JSON):\s*(.+?)\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,        2,      3,             5,                   7,           9,               10  ))

    def is_matching_body_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(BODY):\s*(!?/.*?/i?)\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0, 2,             4,                   6,           8,               9   ))

    def is_matching_rule_with_explicit_location(self, line):
        return self.add_rule_if_match(line,
            r'\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?(text|file):\s*(.*)',
            (0,0,0,2,                  4,          5,             6  ))

    def add_rule_with_implied_text_location(self, line):
        return self.add_rule_if_match(line,
            r'\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?\s*(.*)',
            (0,0,0,2,                  4,          0, 5   ))

    def is_blank(self, line):
        return re.match(r'\s*$', line)


class RulesAdjuster:

    blank_line_pat = re.compile(r'\s*$')
    content_selector_pat = re.compile(r'\s*--\[\s*(\d*)\s*\]--\s*$')
    header_line_pat = re.compile(r'\s*HEADER:\s*(.+)\s*:\s*(.*)')

    def adjust(self, rules):
        for rule in rules:
            self.adjust_rule(rule)

    def adjust_rule(self, rule):
        lines = rule.value.copy()
        headers = {}
        content = []
        rule.headers.clear()
        rule.headers.append(headers)  # [headers1, headers2,...]
        rule.value.clear()
        rule.value.append(content)    # [content1, content2,...]

        # remove whitespace before first line of content
        if len(lines) > 0:
            lines[0] = lines[0].lstrip()

        blanks_only = True
        for line in lines:
            if self.is_content_selector(line):
                content = []
                headers = {}

                if blanks_only:
                    # if we've only seen blank lines so far, replace them
                    rule.value[-1] = content
                    rule.headers[-1] = headers
                else:
                    rule.value.append(content)
                    rule.headers.append(headers)

                blanks_only = True
            elif self.is_header_line(line, headers):
                blanks_only = False
            elif blanks_only and self.is_blank_line(line):
                pass
            else:
                content.append(line)
                blanks_only = False

    def is_blank_line(self, line):
        return re.match(self.blank_line_pat, line)

    def is_content_selector(self, line):
        return re.match(self.content_selector_pat, line)

    def is_header_line(self, line, headers):
        m = re.match(self.header_line_pat, line)
        if m:
            headers[m.group(1)] = m.group(2)
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
            content = ''.join(rule.value)

            if rule.location == 'file':
                file = content.strip()
                delay, headers, status, content = self.resolve_file(
                    file, status, delay, headers, params, json, level + 1)

        return delay, headers, status, content


class EchoServer:

    param_pat = re.compile('^(\w+):(.*)$')

    def __init__(self, path):
        self.request_path = path
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
        self._response = request.args.get('_response', '')
        self.content = self._response.lstrip()

    def parse_json_body(self):
        self.json = None  # Box of json object from the request body
        json = request.get_json()
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


if __name__ == '__main__':
    app.run()

