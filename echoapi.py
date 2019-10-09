#!/usr/bin/env python

# Echo Server - receive a request and return a response defined by parameters of the request.
#
# Here is a list of features and examples...
#
#
# Static Response
#
#     Return the same static response to all requests
#
#     eg: http://127.0.0.1:5000/samples?_response=200 text:{ "id": 45, "validation_date": null }
#
# Named Path Parameters
#
#     Recognize multiple, named parameters in the url path and render them in the response
#
#     eg: http://127.0.0.1:5000/samples/id:{id}/other:{other}?_response=200 text:{ "id": {id}, "other": "{other}" }
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
#     Blank lines are ignored and spaces may be added to the rules to make them more readable.
#     For example:
#
#         http://127.0.0.1:5000/samples?_response="200
#             PATH:       /\b100\d{3}/   file:samples/get/100xxx.json
#
#             PARAM:name         /bob/   file:samples/get/bob.json
#             PARAM:name         /sue/   file:samples/get/sue.json

#             JSON:pet.dog.name  /Fido/  file:samples/get/fido.json
#             JSON:pet.pig.name  /Sue/   file:samples/get/piggie.json
#
#                                        file:samples/get/response.json"
#
# TODO
# - finish testing selection rules, rule markers, and nested files
# - allow override of status code with each rule
# - add error checking everywhere
# - optimization: precompile the static regular expressions
# - optimization: cache file contents and maybe resolved instances
#
# TODO maybe
# - add wildcard support for parameters and JSON fields ("PARAM:*" and "JSON:*")
# - allow variation through a list of responses to be selected in order, round-robin, by a stateful echo server


from box import Box
from collections import namedtuple
from flask import Flask, jsonify, request

import os
import re


app = Flask(__name__)


Rule = namedtuple('Rule', ['selector_type', 'selector_target', 'pattern', 'location', 'value', 'lines'])


class Rules:

    def __init__(self, text):
        self.rules = []
        self.parse(text)

    def get_response_lines(self, text):
        # replace one of [|@>] with newline if it precedes a selector type or location specifier
        multiline = re.sub(r'[|@>]\s*((PATH|PARAM|JSON|BODY|text|file):)', r'\n\1', text)
        lines = multiline.split('\n')
        return lines

    def parse(self, text):
        lines = self.get_response_lines(text)
        for line in lines:
            if self.is_status_code(line) and not self.rules:
                self.status_code = int(line.strip())
            elif self.is_blank(line):
                pass
            elif self.is_matching_path_rule(line):
                pass
            elif self.is_matching_param_rule(line):
                pass
            elif self.is_matching_json_rule(line):
                pass
            elif self.is_matching_body_rule(line):
                pass
            elif self.is_matching_rule(line):
                pass
            elif self.rules:
                # add to the content of the most recent rule
                rule = self.rules[-1]
                # TODO this is silly to maintain 2 lists of lines
                rule.lines.append(line)
                rule.value.append(line)
            else:
                self.add_rule(None, None, None, 'text', line, line)

    def rule_selector_generator(self, params, json):
        for rule in self.rules:
            if rule.selector_type is None:
                yield rule

            text = None
            if rule.selector_type == 'PARAM':
                param_name = rule.selector_target
                text = params.get(param_name, '')
            elif rule.selector_type == 'JSON':
                json_path = rule.selector_target
                fmt = '{' + json_path + '}'
                text = fmt.format(json=json)
            elif rule.selector_type == 'BODY':
                body = request.get_data()
                text = body

            if re.search(rule.pattern, text):
                yield rule

    def add_rule(self, selector_type, selector_target, pattern, location, value, line):
        rule = Rule(
            selector_type,    # one of { PATH, PARAM, JSON, BODY, None }
            selector_target,  # eg: id, or sample.location.name
            pattern,          # any regular expression
            location,         # one of { text, file }
            [value],          # arbitrary text
            [line])
        self.rules.append(rule)

    def is_blank(self, line):
        return re.match('\s*$', line)

    def is_status_code(self, line):
        return re.match('\s*\d{3}\s*$', line)

    def is_matching_path_rule(self, line):
        m = re.match(r'\s*(PATH):\s*/(.*?)/\s*(text|file):\s*(.*)', line)
        if m:
            self.add_rule(m.group(1), None, m.group(2), m.group(3), m.group(4), line)
            return True
        return False

    def is_matching_param_rule(self, line):
        m = re.match(r'\s*(PARAM):(.+?)\s*/(.*?)/\s*(text|file):\s*(.*)', line)
        if m:
            self.add_rule(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), line)
            return True
        return False

    def is_matching_json_rule(self, line):
        m = re.match(r'\s*(JSON):(.+?)\s*/(.*?)/\s*(text|file):\s*(.*)', line)
        if m:
            self.add_rule(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), line)
            return True
        return False

    def is_matching_body_rule(self, line):
        m = re.match(r'\s*(BODY):\s*/(.*?)/\s*(text|file):\s*(.*)', line)
        if m:
            self.add_rule(m.group(1), None, m.group(2), m.group(3), m.group(4), line)
            return True
        return False

    def is_matching_rule(self, line):
        m = re.match(r'\s*(text|file):\s*(.*)', line)
        if m:
            self.add_rule(None, None, None, m.group(1), m.group(2), line)
            return True
        return False


class RulesTemplate:

    def __init__(self, text=None, file=None):
        self.text = text
        self.file = file

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

    def get_text_to_resolve(self, file, params, json):
        text = None

        if file:
            # the text is loaded from a file in a recursive call to resolve()
            file = self.resolve_value(file, params, json)
            text = self.load_file(file)
        else:
            # the initial text is either supplied or loaded from a file
            if self.file:
                file = self.resolve_value(self.file, params, json)
                text = self.load_file(file)
            else:
                text = self.text

        return text

    # TODO rewrite this without file arg and using separate resolve_file() and a 3rd function w/ common code
    def resolve(self, params, json, file=None):
        text = self.get_text_to_resolve(file, params, json)

        # first, resolve text or filename as a template
        text = self.resolve_value(text, params, json)

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
                    content = self.resolve(params, json, file=rule.value[0])
                else:
                    content = '\n'.join(rule.value)

            except StopIteration:
                # there are no more matching rules
                # if this is the top-level call, return '' instead of None
                if file is None:
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
                name, value = m.group(1), m.group(2)
                self.path_params[name] = value

    def parse_response_parameter(self):
        self._response = None    # input _response parameter
        self.location = 'text'   # parsed from _response: 'text' or 'file'
        self.value = ''          # parsed from _response: content or name of file with content
        self.status_code = 200   # parsed from _response: integer value

        self._response = request.args.get('_response', '')
        m = re.search('^\s*(\d{3})\s*(.*)$', self._response, re.DOTALL)
        if m:
            self.status_code = int(m.group(1))
            self.value = m.group(2)
        else:
            self.value = self._response.lstrip()

        m = re.search('^(file|text):\s*(.*)', self.value)
        if m:
            self.location = m.group(1)
            self.value = m.group(2).lstrip()

    def parse_json_body(self):
        self.json = None  # Box of json object from the request body
        json = request.get_json()
        self.json = Box(json)

    def all_params(self):
        params = { k: v for k, v in request.args.items() }
        return { **self.path_params, **params }

    def response(self):
        args = { self.location: self.value }
        template = RulesTemplate(**args)
        params = self.all_params()
        content = template.resolve(params, self.json)
        return content, self.status_code


@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    return server.response()


if __name__ == '__main__':
    app.run()

