#!/usr/bin/env python

from echoapi import Template

import json
import requests
import unittest


class TestEchoServer(unittest.TestCase):
    def setUp(self):
        self.json = {
            'version': 23,
            'color': 'blue',
            'pet': {
                'dog': {
                    'name': 'Fido',
                },
            }
        }
        self.params = {
            'color': 'green',
            'age': 7,
        }

    def case(self, url, expected_status_code, expected_content, label):
        r = requests.get(url, json=self.json, params=self.params)
        content = r.content.decode("utf-8")
        print(f'{r.status_code} {content}')
        assert r.status_code == expected_status_code, f'{label} (status code)'
        assert content == expected_content, f'{label} (content)'

    def test_static_response(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=201 text:{ "id": 4 }',
            201, '{ "id": 4 }',
            'Simple static response')
        self.case('http://127.0.0.1:5000/samples/45?_response=200 text:{ "id": 45, "validation_date": null }',
            200, '{ "id": 45, "validation_date": null }',
            'Static response with extra fields')
        self.case("http://127.0.0.1:5000/labs/Illuminati?_response=200 text:Doesn't need to be json.\nCould be multi-line.",
            200, "Doesn't need to be json.\nCould be multi-line.",
            'Static response with arbitrary text')
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=622', 622, '',
            'Static response with status code only, no content')

    def test_named_path_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:73/material:wood?_response=200 text:{ "id": {id}, "validation_date": null, "material": "{material}" }',
            200, '{ "id": 73, "validation_date": null, "material": "wood" }',
            'Named path parameters in response')

    def test_response_file(self):
        self.case('http://127.0.0.1:5000/samples/id:74/material:wood?_response=200 file:samples/get/{id}.json',
            200, Template(file='samples/get/74.json').resolve(dict(id=74, material='wood')),
            'Content from resolved template file')

    def test_other_url_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:75/material:wood?_response=200 text:{ "id": {id}, "color": "{color}", "material": "{material}" }',
            200, '{ "id": 75, "color": "green", "material": "wood" }',
            'Other URL parameters in resolved content')
        self.case('http://127.0.0.1:5000/samples/id:76?_response=200 file:samples/get/color/{color}.json',
            200, Template(file='samples/get/color/green.json').resolve(dict(id=76, color='green', age=7)),
            'Other URL parameters for selection of template file')

