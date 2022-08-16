from .rules_template import RulesTemplate

from box import Box
from flask import request, Response

import re


class EchoServer:

    param_pat = re.compile(r'^(\w+):(.*)$')
    param_value_pat = re.compile(r':\w+')

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

        try:
            json = request.get_json()
        except Exception:
            json = {}

        self.json = Box(json)

    def all_params(self):
        params = {
            k: v for k, v in request.args.items()
        }
        return {
            **self.path_params,
            **params
        }

    def response(self):
        content = self.content
        headers = self.headers
        params = self.all_params()
        json = self.json

        template = RulesTemplate(self.request_path, content)
        delay, status, headers, content = template.resolve(headers, params, json)
        resp = Response(content, headers=headers, status=status)

        return delay, resp
