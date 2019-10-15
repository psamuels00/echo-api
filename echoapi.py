#!/usr/bin/env python

from box import Box
from collections import namedtuple
from flask import Flask, request, Response

import os
import re


app = Flask(__name__)


Rule = namedtuple('Rule', ['selector_type', 'selector_target', 'pattern', 'status_code', 'location', 'value'])


class Rules:

    def __init__(self, text):
        self.status_code = 200
        self.rules = []
        self.parse(text)

    def get_response_lines(self, text):
        # place newline after status code at beginning of text, if missing
        text = re.sub(r'^\s*(\d{3})\s*(.*)', r'\1\n\2', text)

        # remove one of [|@>] from beginning of text to avoid creating an extra blank line
        # by the sub() command below
        m = re.match(r'[|@>]\s*(.*)', text, re.DOTALL)
        if m:
            text = m.group(1)

        # replace one of [|@>] with newline if it precedes a selector type or location specifier
        multiline = re.sub(r'[|@>]\s*((HEADER|PATH|PARAM|JSON|BODY|text|file):)', r'\n\1', text)

        lines = multiline.splitlines(keepends=True)
        return lines

    def parse(self, text):
        lines = self.get_response_lines(text)
        for line in lines:
            if self.is_comment(line):
                pass
            elif self.is_status_code(line) and not self.rules:
                self.status_code = int(line.strip())
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
                self.add_rule(None, None, None, 'text', line)

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

    def add_rule(self, selector_type, selector_target, pattern, location, value):
        location = location or 'text'
        status_code = self.status_code
        rule = Rule(
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            status_code,      # integer value
            location,         # one of { text, file }
            [value])          # arbitrary text
        self.rules.append(rule)

    def is_comment(self, line):
        return re.match(r'\s*#', line)

    def is_blank(self, line):
        return re.match(r'\s*$', line)

    def is_status_code(self, line):
        return re.match(r'\s*\d{3}\s*$', line)

    def add_rule_if_match(self, line, pattern, groups):
        m = re.match(pattern, line, re.DOTALL)
        if m:
            args = [ m.group(n) if n else None
                     for n in groups ]
            self.add_rule(*args)
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


class RulesTemplate:

    def __init__(self, text=''):
        self.text = text

    def double_braces(self, string, reverse=False):
        if reverse:
            string = re.sub(r'{{([^\w])', r'{\1', string) # {{ not followed by word char is converted to {
            string = re.sub(r'([^\w])}}', r'\1}', string) # }} not preceded by word char is converted to }
        else:
            string = re.sub(r'{([^\w])', r'{{\1', string) # { not followed by word char is converted to {{
            string = re.sub(r'([^\w])}', r'\1}}', string) # } not preceded by word char is converted to }}
        return string

    def resolve_value(self, value, headers, params, json):
        if headers or params or json:
            p = params.copy()
            p['json'] = json
            p['header'] = headers
            value = self.double_braces(value)
            value = value.format(**p)
            value = self.double_braces(value, reverse=True)
        return value

    def load_file(self, file):
        path = os.path.join('responses', file)
        with open(path, 'r') as fh:
            text = fh.read()
        return text

    def extract_headers(self, status, content):
        headers = {}

        lines = content.splitlines(keepends=True)
        while lines:
            m = re.match('HEADER: (.*?)\s*:\s*(.*)', lines[0])
            if not m:
                break
            headers[m.group(1)] = m.group(2)
            lines.pop(0)
            if lines:
                lines[0] = lines[0].lstrip()

        content = ''.join(lines)
        return headers, status, content

    def resolve(self, headers, params, json):
        text = self.resolve_value(self.text, headers, params, json)
        status, content = self.select_content(headers, params, json, text, level=0)
        return self.extract_headers(status, content)

    def resolve_file(self, headers, params, json, file, level):
        # load and resolve the file contents
        text = self.load_file(file)
        text = self.resolve_value(text, headers, params, json)

        return self.select_content(headers, params, json, text, level)

    def select_content(self, headers, params, json, text, level):
        rules = Rules(text)
        rule_selector = rules.rule_selector_generator(headers, params, json)

        status = rules.status_code
        content = None
        while content is None:
            try:
                rule = next(rule_selector)

                # if the rule specifies a file, then recurse
                # otherwise return the content
                if not rule:
                    pass
                elif rule.location == 'file':
                    file = rule.value[0].strip()
                    status, content = self.resolve_file(headers, params, json, file, level + 1)
                else:
                    status = rule.status_code
                    content = ''.join(rule.value)

            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return '' instead of None
                if level == 0:
                    content = ''
                break

        return status, content


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
    return server.response()


if __name__ == '__main__':
    app.run()
