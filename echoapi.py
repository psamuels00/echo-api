#!/usr/bin/env python

# Echo Server - receive a request and return a response defined in the request.
#
# Static Response
#     Return the same static response to all requests
#     eg: http://127.0.0.1:5000/samples/45?_response=200 text:{ "id": 45, "validation_date": null }
#
# Named Path Parameters
#     Recognize multiple, named parameters in the url path and render them in the response
#     eg: http://127.0.0.1:5000/samples/id:{id}/other:{other}?_response=200 text:{ "id": {id}, "date": null, "other": "{other}" }
#
# Response Files
#     Allow response to come from a file (or URL?) treated as a template wrt the named parameters.
#     str.format(**data) is used as the templating system.
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/response.json
#
# Map of Responses
#     Allow response file to be selected by one or more named parameters.
#     eg: http://127.0.0.1:5000/samples/id:{id}?_response=200 file:samples/get/{id}.json
#
# Other URL Parameters
#     Capture parameters in the URL other than those in the request path that may be used to
#     resolve and/or select the response template.  This includes URL parameters supplied in
#     addition to _response.
#     eg: http://127.0.0.1:5000/samples/{id}?_response=200 file:samples/get/color/{color}.json
#
# TODO JSON in the Request Body
#     Provide access to fields in a json object in the body of the request that may be used to
#     resolve and/or select the response template.
#     eg: http://127.0.0.1:5000/samples/{id}?_response=200 text:{ "group": { 'name': {json.group.name} } }
#
# TODO Selection Rules
#     Allow response content to be selected based on regex matching of the path, parameters, or
#     a value in the json body of a request.  This allows for more flexible response variability
#     than simple mapping of response files based on the value of a parameter being in the path
#     to the file (see Map of Responses).  Rules have the following format:
#
#         PATH: /.../ (text|file):...
#         PARAM:foo /.../ (text|file):...
#         JSON:pet.dog.name /.../ (text|file):...
#
#     The ellipses in /.../ indicate a regex.  The inline text for "text:" entries ends on
#     the first blank line following the start of the rule.  Any number of selection rules
#     may be included for a response.  Each one must begin on a new line, being preceeded
#     only by white space.  The rules are processed in order.  When the first match is made,
#     processing stops and a response is generated.  A final rule with no selection criteria
#     serves as a default or catch-all.
#
#     eg: http://127.0.0.1:5000/samples?_response=200 \
#             PATH:       /\b100\d{3}/   file:samples/get/100xxx.json \
#             PARAM:name         /bob/   file:samples/get/bob.json \
#             PARAM:name         /sue/   file:samples/get/sue.json \
#             JSON:pet.dog.name  /Fido/  file:samples/get/fido.json \
#                                        file:samples/get/response.json
#
# TODO
# - allow applcation of selection criteria to status code
# - add error checking
# - possibly allow variation in the response by defining a list of options to be selected in order by a stateful echo server.


from flask import Flask, request
import os
import re


app = Flask(__name__)


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

    param_pat = re.compile('^(\w+):(.*)$')

    def __init__(self, path):
        self.parse_request_path(path)
        self.parse_response_parameter()

    def parse_request_path(self, path):
        self.path = path         # the request path
        self.params = {}         # parsed from path

        parts = path.split('/')
        for part in parts:
            m = self.param_pat.search(part)
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

        # resolve all parameters
        params = { k: v for k, v in request.args.items() }
        all_params = { **self.params, **params }
        content = temp.resolve(all_params)

        return content, self.status_code


# see https://stackoverflow.com/questions/16611965/allow-all-method-types-in-flask-route
@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    server = EchoServer(text)
    return server.response()


if __name__ == '__main__':
    app.run()

