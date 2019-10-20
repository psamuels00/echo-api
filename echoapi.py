#!/usr/bin/env python

from box import Box
from collections import namedtuple
from flask import Flask, request, Response

import os
import re
import time


app = Flask(__name__)


Rule = namedtuple('Rule', [
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

    def __init__(self, text, default_status_code, default_delay):
        responseParser = ResponseParser(default_status_code, default_delay)
        self.status_code, self.delay, self.rules = responseParser.parse(text)

        rulesAdjuster = RulesAdjuster()
        rulesAdjuster.adjust(self.rules)

    def num_rules(self):
        return len(self.rules)

    def rule_selector_generator(self, headers, params, json):
        for rule in self.rules:
            if rule.selector_type is None:
                yield rule

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

            if text and re.search(rule.pattern, text):
                yield rule


class ResponseParser:
    def __init__(self, status_code, delay):
        self.status_code = status_code # default status code (global default, inherited, or preceding any rules)
        self.delay = delay             # default status code (global default, inherited, or preceding any rules)
        self.lines = None              # used by parse() for elements at beginning of line
        self.rules = []                # returned by parse()

    def parse(self, text):
        self.lines = self.parse_response_into_lines(text)

        while self.lines:
            line = self.lines.pop(0)
            self.parse_line(line)

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

    def add_rule(self, selector_type, selector_target, pattern, status_code, delay, location, value):
        status_code = self.status_code if status_code is None else int(status_code)
        delay = self.delay if delay is None else int(delay)
        location = location or 'text'
        headers = {}  # RulesAdjuster moves entries from value to headers

        rule = Rule(
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            status_code,      # integer HTTP response code
            delay,            # integer representing milliseconds
            location,         # one of { text, file }
            headers,          # dictionary of header values
            [value])          # arbitrary text
        self.rules.append(rule)

    def add_rule_if_match(self, line, pattern, groups):
        m = re.match(pattern, line, re.DOTALL)
        if m:
            args = [ m.group(n) if n else None
                     for n in groups ]
            self.add_rule(*args)
            return True
        return False

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
            rule.value.append(line)
        elif self.is_blank(line):
            # ignore blank lines before any rules or after a file rule
            pass
        else:
            self.add_rule_with_implied_text_location(line)

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
            r'\s*(HEADER):\s*(.+?)\s*/(.*?)/\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,          2,       3,        5,                   7,           9,               10  ))

    def is_matching_path_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PATH):\s*/(.*?)/\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0,  2,        4,                   6,           8,               9   ))

    def is_matching_param_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PARAM):\s*(.+?)\s*/(.*?)/\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,         2,       3,        5,                   7,           9,               10  ))

    def is_matching_json_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(JSON):\s*(.+?)\s*/(.*?)/\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,        2,       3,        5,                   7,           9,               10  ))

    def is_matching_body_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(BODY):\s*/(.*?)/\s*((\d{3})\b\s*)?(delay=(\d+)ms\s*)?((text|file):)?\s*(.*)',
            (    1,     0,  2,        4,                   6,           8,               9   ))

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
    def adjust(self, rules):
        for rule in rules:
            self.adjust_rule(rule)

    def adjust_rule(self, rule):
        # move headers from value to headers field
        while rule.value and self.rule_content_begins_with_header(rule):
            pass

        # remove whitespace before first line of content
        if rule.value:
            rule.value[0] = rule.value[0].lstrip()

    def rule_content_begins_with_header(self, rule):
        m = re.match(r'\s*HEADER:\s*(.+)\s*:\s*(.*)', rule.value[0])
        if m:
            rule.headers[m.group(1)] = m.group(2)
            rule.value.pop(0)
            return True
        return False


class RulesTemplate:

    def __init__(self, text=''):
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
        return self.select_content(text, default_status_code, default_delay, headers, params, json)

    def resolve_file(self, file, default_status_code, default_delay, headers, params, json, level):
        text = self.load_file(file)
        text = self.resolve_value(text, headers, params, json)
        return self.select_content(text, default_status_code, default_delay, headers, params, json, level)

    def select_content(self, text, default_status_code, default_delay, headers, params, json, level=0):
        rules = Rules(text, default_status_code, default_delay)
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

        template = RulesTemplate(content)
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

