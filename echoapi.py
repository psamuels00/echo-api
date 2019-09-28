#!/usr/bin/env python

# Echo Server - receive a request and return a response defined in the request.
#
# Static Response
#     Return the same static response to all requests
#     eg: http://127.0.0.1:5000/samples/45?_response=200 text:{ "id": 45, "validation_date": null }
#
# Named Parameters
#     Recognize multiple, named parameters in the url and render them in the response
#     eg: http://127.0.0.1:5000/samples/id:{id}/other:{other}?_response=200 text:{ "id": {id}, "validation_date": null, "other": "{other}" }
#
# Response Files
#     Allow response to come from a file (or URL?) treated as a template wrt the named parameters.
#     str.format(**data) may be sufficient as the templating system.
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/response.json
#
# Map of Responses
#     Allow response file to be selected by one or more named parameters.
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/{id}.json
#
# TODO Other Parameters
#     Add a way to capture parameters other than those in the request path that can be used to select and/or resolve the response
#     template.  This includes URL parameters supplied in addition to _response and values inside json in the request body.
#
#     Use these prefixes, where ellipses indicate a regex and the inline text for "text:" ends on the first blank line.
#         json.pet.dog.name[...](text|file):...
#         param.foo[...](text|file):...
#         path[...](text|file):...
#         (text|file):...
#
#     If a match is made on json.pet.dog.name, the response can include {pet.dog.name}.
#     If a match is made on param.foo, the response can include {foo}.
#     In both cases, the parameters may be used to select a file using "file:".
#
# TODO
# - add error checking
# - possibly add option to simulate errors, like HTTP status code 400, 500
# - possibly allow variation in the response by defining a list of options to be selected in order by a stateful echo server.


from flask import Flask, request
import os
import re


app = Flask(__name__)


param_pat = re.compile('^(\w+):(.*)$')


class Template:

    def __init__(self, text=None, file=None):
        self.text = text
        self.file = file

    def double_braces(self, string, reverse=False):
        if reverse:
            string = re.sub(r'{{([^\w])', r'{\1', string)
            string = re.sub(r'([^\w])}}', r'\1}', string)
        else:
            string = re.sub(r'{([^\w])', r'{{\1', string)
            string = re.sub(r'([^\w])}', r'\1}}', string)
        return string

    def resolve_value(self, value, params):
        if params:
            value = self.double_braces(value)
            value = value.format(**params)
            value = self.double_braces(value, reverse=True)
        return value

    def load_file(self, file):
        path = os.path.join('responses', file)
        with open(path, 'r') as fh:
            text = fh.read()
        return text

    def resolve(self, params):
        if self.file:
            file = self.resolve_value(self.file, params)
            text = self.load_file(file)
        else:
            text = self.text
        return self.resolve_value(text, params)


class EchoServer:

    def __init__(self, path):
        self.parse_request_path(path)
        self.parse_response_parameter()

    def parse_request_path(self, path):
        self.path = path         # the request path
        self.params = {}         # parsed from path

        parts = path.split('/')
        for part in parts:
            m = param_pat.search(part)
            if m:
                name, value = m.group(1), m.group(2)
                self.params[name] = value

    def parse_response_parameter(self):
        self._response = None    # input _response parameter
        self.location = 'text'   # parsed from _response: 'text' or 'file'
        self.value = ''          # parsed from _response: content or name of file with content
        self.status_code = 200   # parsed from _response: integer value

        self._response = request.args.get('_response', '')
        if ' ' in self._response:
            status_code, response = re.split('\s+', self._response, 1)
            self.status_code = int(status_code)
            self.location, self.value = re.split(':', response, 1)
        else:
            self.status_code = int(self._response)

    def response(self):
        args = { self.location: self.value }
        temp = Template(**args)
        content = temp.resolve(self.params)
        return content, self.status_code


# see https://stackoverflow.com/questions/16611965/allow-all-method-types-in-flask-route
@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    return server.response()


if __name__ == '__main__':
    app.run()

