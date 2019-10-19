#!/usr/bin/env python

from box import Box
from collections import namedtuple
from flask import Flask, request, Response

import os
import re


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

    def __init__(self, text):
        responseParser = ResponseParser()
        self.status_code, self.delay, self.rules = responseParser.parse(text)

        ruleParser = RulesParser()
        ruleParser.parse(self.rules)

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
    def __init__(self):
        self.status_code = 200   # global status code (preceding any rules)
        self.delay = 0           # global delay (preceding any rules)
        self.lines = None        # used by parse() for elements at beginning of line
        self.rules = []          # returned by parse()

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

    def add_rule(self, selector_type, selector_target, pattern, location, value):
        location = location or 'text'
        status_code = self.status_code
        delay = self.delay
        headers = {}  # RulesParser moves entries from value to headers

        rule = Rule(
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            status_code,      # integer value
            delay,            # integer representing seconds
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
            # create a new implied text rule
            self.add_rule(None, None, None, 'text', line)

    def is_comment(self, line):
        return re.match(r'\s*#', line)

    def begins_with_status_code(self, line):
        m = re.match(r'\s*(\d{3})\b\s*(.*)', line)
        if m:
            self.status_code = int(m.group(1))
            self.lines.insert(0, m.group(2))
            return True
        return False

    def begins_with_delay(self, line):
        m = re.match(r'\s*delay\s*=(\d+)sec\b\s*(.*)', line)
        if m:
            self.delay = int(m.group(1))
            self.lines.insert(0, m.group(2))
            return True
        return False

    def is_matching_header_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(HEADER):\s*(.+?)\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (    1,          2,       3,        5,               6   ))

    def is_matching_path_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PATH):\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (    1,     0,  2,        4,               5   ))

    def is_matching_param_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(PARAM):\s*(.+?)\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (    1,         2,       3,        5,               6   ))

    def is_matching_json_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(JSON):\s*(.+?)\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (    1,        2,       3,        5,               6   ))

    def is_matching_body_rule(self, line):
        return self.add_rule_if_match(line,
            r'\s*(BODY):\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (    1,     0,  2,        4,               5   ))

    def is_matching_rule_with_explicit_location(self, line):
        return self.add_rule_if_match(line,
            r'\s*(text|file):\s*(.*)',
            (0,0,0,1,           2  ))

    def is_blank(self, line):
        return re.match(r'\s*$', line)


class RulesParser:
    def parse(self, rules):
        for rule in rules:
            self.parse_rule(rule)

    def parse_rule(self, rule):
        self.parse_rule_meta(rule)
        self.parse_rule_content(rule)

    def parse_rule_meta(self, rule):
        while rule.value:
            if not rule.headers and self.rule_begins_with_status_code(rule):
                pass
            elif not rule.headers and self.rule_begins_with_delay(rule):
                pass
            elif self.rule_is_response_header(rule):
                pass
            else:
                break

    def parse_rule_content(self, rule):
        if rule.value:
            rule.value[0] = rule.value[0].lstrip()

    def rule_begins_with_status_code(self, rule):
        m = re.match(r'\s*(\d{3})\b\s*(.*)', rule.value[0])
        if m:
            rule.status_code = int(m.group(1))
            rule.value[0] = m.group(2)
            return True
        return False

    def rule_begins_with_delay(self, rule):
        m = re.match(r'\s*delay\s*=(\d+)sec\b\s*(.*)', rule.value[0])
        if m:
            rule.delay = int(m.group(1))
            rule.value[0] = m.group(2)
            return True
        return False

    def rule_is_response_header(self, rule):
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
        text = self.resolve_value(self.text, headers, params, json)
        return self.select_content(text, headers, params, json, level=0)

    def resolve_file(self, headers, params, json, file, level):
        text = self.load_file(file)
        text = self.resolve_value(text, headers, params, json)
        return self.select_content(text, headers, params, json, level)

    def select_content(self, text, headers, params, json, level):
        rules = Rules(text)
        rule_selector = rules.rule_selector_generator(headers, params, json)

        headers = {}
        status = None
        content = None

        if rules.num_rules() == 0:
            status = rules.status_code
            content = ''
            # TODO return rules.delay
            return headers, status, content

        while content is None:
            try:
                rule = next(rule_selector)

                if rule.location == 'file':
                    file = rule.value[0].strip()
                    headers, status, content = self.resolve_file(headers, params, json, file, level + 1)
                else:
                    headers = rule.headers
                    status = rule.status_code
                    content = ''.join(rule.value)

            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return '' instead of None
                if level == 0:
                    content = ''
                break

        # TODO return the most recently parsed rule.delay
        return headers, status, content


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
        headers = self.headers
        content = self.content
        params = self.all_params()
        json = self.json

        template = RulesTemplate(content)
        headers, status, content = template.resolve(headers, params, json)
        resp = Response(content, headers=headers, status=status)

        return resp


@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    # TODO implement the delay functionality
    return server.response()


if __name__ == '__main__':
    app.run()
