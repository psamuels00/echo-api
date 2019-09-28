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
# TODO Response Variation
#     Possibly allow variation in the response by defining a list of options to be selected in order by a stateful echo server.
#
# TODO
# - add error checking
# - possibly add option to simulate errors, like HTTP status code 400, 500


from flask import Flask, request
import os
import re


app = Flask(__name__)


param_pat = re.compile('^(\w+):(.*)$')


def parse_path(path):
    params = {}
    parts = path.split('/')
    for part in parts:
        m = param_pat.search(part)
        if m:
            name, value = m.group(1), m.group(2)
            params[name] = value
    return params


def parse_response(response_param):
    if ' ' not in response_param:
        status_code, location, value = response_param, 'text', ''
    else:
        status_code, response = re.split('\s+', response_param, 1)
        location, value = re.split(':', response, 1)
    return location, value, int(status_code)


def double_braces(string, double=True):
    if double:
        string = re.sub(r'{([^\w])', r'{{\1', string)
        string = re.sub(r'([^\w])}', r'\1}}', string)
    else:
        string = re.sub(r'{{([^\w])', r'{\1', string)
        string = re.sub(r'([^\w])}}', r'\1}', string)
    return string


def render_params(content, params):
    if params:
        # single braces need to be doubled up or format() will have a fit; revert the braces when done
        content = double_braces(content, True)
        content = content.format(**params)
        content = double_braces(content, False)
    return content


def load_file(file):
    path = os.path.join('responses', file)
    with open(path, 'r') as fh:
        content = fh.read()
    return content


def build_response(location, value, params):
    content = value
    if location == 'file':
        value = render_params(value, params)
        content = load_file(value)
    return render_params(content, params)


# see https://stackoverflow.com/questions/16611965/allow-all-method-types-in-flask-route
@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    response_param = request.args.get('_response', '')
    location, value, status_code = parse_response(response_param)
    params = parse_path(text)
    content = build_response(location, value, params)
    return content, status_code


if __name__ == '__main__':
    app.run()

