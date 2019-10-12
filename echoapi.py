#!/usr/bin/env python

# Echo Server - Receive a request and return a response defined by parameters of the request.
#
# The response status code and content can be included in the request.
# TODO summarize features here.
#
# Here is a list of features and examples...
#
#
# Static Response
#
#     Return the same static response to all requests
#
#     eg: http://127.0.0.1:5000/samples?_response=200 { "id": 45, "validation_date": null }
#
# Named Path Parameters
#
#     Recognize multiple, named parameters in the url path and render them in the response
#
#     eg: http://127.0.0.1:5000/samples/id:{id}/lab:{lab}?_response=200 { "id": {id}, "lab": "{lab}" }
#
# Response Files
#
#     Allow response to come from a file (or URL?) treated as a template wrt the named parameters.
#     str.format(**data) is used as the templating system.
#
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/response.json
#
# Map of Responses
#
#     Allow response file to be selected by one or more named parameters.
#
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/{id}.json
#
# Other URL Parameters
#
#     Capture parameters in the URL other than those in the request path that may be used to
#     resolve and/or select the response template.  This includes URL parameters supplied in
#     addition to _response.
#
#     eg: http://127.0.0.1:5000/samples/{id}?_response=200 file:samples/get/color/{color}.json
#
# JSON in the Request Body
#
#     Provide access to fields in a json object in the body of the request that may be used to
#     resolve and/or select the response template.
#
#     eg: http://127.0.0.1:5000/samples/{id}?_response=200 text:{ "group": { "name": "{json.group.name}" } }
#
# Selection Rules
#
#     Allow response content to be selected based on regex matching of the path, parameters, or
#     a value in the body of a request.  Any number of selection rules may be included for a
#     response.  The rules are processed in order.  When the first match is made, processing
#     stops and a response is generated.  A final rule with no selection criteria serves as a
#     default or catch-all.  Rules look something like this:
#
#         | PATH: /.../ (text|file):...
#         | PARAM:foo /.../ (text|file):...
#         | JSON:pet.dog.name /.../ (text|file):...
#         | BODY: /.../ (text|file):...
#         | (text|file):...
#
#     The ellipses in /.../ indicate a regular expression.  The vertical bars are optional.
#     For rules beginning on a new line, the vertical bar can be omitted.  For example:
#
#         200
#         PATH: /delete/ text: error
#         PARAM:dog /fido|spot/ text: Hi {dog}
#         text: OK
#
#     The vertical bars may be included in environments where it is hard to insert newlines
#     into the value, or to define multiple rules on a single line.  The at symbol (@) and
#     greater than symbol (>) can also be used like the vertical bar.  For example, the
#     following lines are equivalent to the rules specification above:
#
#         200 | PATH: /delete/ text: error | PARAM:dog /fido|spot/ text: Hi {dog} | text: OK
#         200 > PATH: /delete/ text: error > PARAM:dog /fido|spot/ text: Hi {dog} > text: OK
#
#     Blank lines following a text rule are considered part of the response content.  Blank
#     lines following a file rule are ignored and spaces may be added to the rules to make
#     them more readable. For example:
#
#         http://127.0.0.1:5000/samples?_response="200
#             PATH:       /\b100\d{3}/   file:samples/get/100xxx.json
#
#             PARAM:name         /bob/   file:samples/get/bob.json
#             PARAM:name         /sue/   file:samples/get/sue.json
#
#             JSON:pet.dog.name  /Fido/  file:samples/get/fido.json
#             JSON:pet.pig.name  /Sue/   file:samples/get/piggie.json
#
#                                        file:samples/get/response.json"
#
# TODO
# - add support for comments following # at the beginning of a line, and complete tests
# - add error checking everywhere, and add tests
#
# TODO maybe
# - allow override of status code with each rule (eg: PARAM: name /bob/ 404 file:samples/not_found)
# - add wildcard support for parameters and JSON fields ("PARAM:*" and "JSON:*")
# - allow variation through a list of responses to be selected in order, round-robin, by a stateful echo server
# - optimization: cache file contents and maybe resolved instances
# - optimization: precompile the static regular expressions


from box import Box
from collections import namedtuple
from flask import Flask, request

import os
import re


app = Flask(__name__)


Rule = namedtuple('Rule', ['selector_type', 'selector_target', 'pattern', 'location', 'value'])


class Rules:

    def __init__(self, text):
        self.rules = []
        self.parse(text)

    def get_response_lines(self, text):
        # remove one of [|@>] from beginning of text to avoid creating an extra blank line
        # by the sub() command below
        m = re.match(r'[|@>]\s*(.*)', text, re.DOTALL)
        if m: text = m.group(1)

        # replace one of [|@>] with newline if it precedes a selector type or location specifier
        multiline = re.sub(r'[|@>]\s*((PATH|PARAM|JSON|BODY|text|file):)', r'\n\1', text)

        lines = multiline.splitlines(keepends=True)
        return lines

    def parse(self, text):
        lines = self.get_response_lines(text)
        for line in lines:
            if self.is_status_code(line) and not self.rules:
                self.status_code = int(line.strip())
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

    def rule_selector_generator(self, params, json):
        for rule in self.rules:
            if rule.selector_type is None:
                yield rule

            text = None
            if rule.selector_type == 'PATH':
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
        rule = Rule(
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            location,         # one of { text, file }
            [value])          # arbitrary text
        self.rules.append(rule)

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

    def is_matching_path_rule(self, line):
        return self.add_rule_if_match(line,
            '\s*(PATH):\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (   1,     0,  2,        4,               5   ))

    def is_matching_param_rule(self, line):
        return self.add_rule_if_match(line,
            '\s*(PARAM):\s*(.+?)\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (   1,      2,       3,        5,               6   ))

    def is_matching_json_rule(self, line):
        return self.add_rule_if_match(line,
            '\s*(JSON):\s*(.+?)\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (   1,      2,       3,        5,               6   ))

    def is_matching_body_rule(self, line):
        return self.add_rule_if_match(line,
            '\s*(BODY):\s*/(.*?)/\s*((text|file):)?\s*(.*)',
            (   1,     0,  2,        4,               5   ))

    def is_matching_rule_with_explicit_location(self, line):
        return self.add_rule_if_match(line,
            '\s*(text|file):\s*(.*)',
            (0,0,0,1,          2  ))


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

    def resolve_value(self, value, params, json):
        if params or json:
            p = params.copy()
            p['json'] = json
            value = self.double_braces(value)
            value = value.format(**p)
            value = self.double_braces(value, reverse=True)
        return value

    def load_file(self, file):
        path = os.path.join('responses', file)
        with open(path, 'r') as fh:
            text = fh.read()
        return text

    def resolve(self, params, json):
        text = self.resolve_value(self.text, params, json)
        return self.select_content(params, json, text, level=0)

    def resolve_file(self, params, json, file, level):
        # load and resolve the file contents
        text = self.load_file(file)
        text = self.resolve_value(text, params, json)

        return self.select_content(params, json, text, level)

    def select_content(self, params, json, text, level):
        rules = Rules(text)
        rule_selector = rules.rule_selector_generator(params, json)

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
                    content = self.resolve_file(params, json, file, level + 1)
                else:
                    content = ''.join(rule.value)

            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return '' instead of None
                if level == 0:
                    content = ''
                break

        return content


class EchoServer:

    param_pat = re.compile('^(\w+):(.*)$')

    def __init__(self, path):
        self.parse_request_path(path)
        self.parse_response_parameter()
        self.parse_json_body()

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
        self._response = None    # input _response parameter
        self.status_code = 200   # parsed from _response: integer value
        self.content = ''        # parsed from _response: content or name of file with content

        self._response = request.args.get('_response', '')
        m = re.search(r'^\s*(\d{3})\s*(.*)$', self._response, re.DOTALL)
        if m:
            self.status_code = int(m.group(1))
            self.content = m.group(2)
        else:
            self.content = self._response.lstrip()

    def parse_json_body(self):
        self.json = None  # Box of json object from the request body
        json = request.get_json()
        self.json = Box(json)

    def all_params(self):
        params = { k: v for k, v in request.args.items() }
        return { **self.path_params, **params }

    def response(self):
        template = RulesTemplate(self.content)
        params = self.all_params()
        content = template.resolve(params, self.json)
        return content, self.status_code


@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    return server.response()


if __name__ == '__main__':
    app.run()

