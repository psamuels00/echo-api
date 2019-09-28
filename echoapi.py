#!/usr/bin/env python

from flask import Flask, request
import re


app = Flask(__name__)


def parse_response(response_param):
    if ' ' in response_param:
        status_code, response = re.split('\\s+', response_param, 1)
    else:
        status_code, response = response_param, ''
    return response, int(status_code)


# see https://stackoverflow.com/questions/16611965/allow-all-method-types-in-flask-route
@app.route('/<path:text>', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])
def all_routes(text):
    response_param = request.args.get('_response', '')
    response, status_code = parse_response(response_param)
    return response, status_code


# TODO Named Parameters
# Recognize multiple, named parameters in the url
# eg: http://127.0.0.1:5000/samples/{id}/{other}?_response=200 { "id": {id}, "validation_date": null, "other": "{other}" }

# TODO Response Files
# Allow response to come from a file (or URL?) treated as a template wrt the named parameters.
# str.format(**data) may be sufficient as the templating system.
# eg: http://127.0.0.1:5000/samples/{id}?_response_file=200 samples/get/response.json

# TODO Map of Responses
# Allow template file to contain a map of responses keyed by the value of one or more named parameters.
# It might be better to keep the response files simple and make the recognized options explicit in the file system.
# eg: http://127.0.0.1:5000/samples/{id}?_response_file=200 samples/get/{id}/response.json

# TODO Other Parameters
# Add a way to capture parameters other than those in the request path that can be used to select and/or resolve the response
# template.  This includes URL parameters supplied in addition to _response and values inside json in the request body.

# TODO Response Variation
# Possibly allow variation in the response by defining a list of options to be selected in order by a stateful echo server.


app.run()


