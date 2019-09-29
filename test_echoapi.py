#!/usr/bin/env python

from echoapi import Template
import json
import requests


def test(url, expected_status_code, expected_response):
    json = {
        'version': 23,
        'color': 'blue',
        'pet': {
            'dog': {
                'name': 'Fido',
            },
        }
    }
    params = {
        'color': 'green',
        'age': 7,
    }
    r = requests.get(url, json=json, params=params)

    response = r.content.decode("utf-8")
    print(f'{r.status_code} {response}')
    assert r.status_code == expected_status_code
    assert response == expected_response


# Static Response
test('http://127.0.0.1:5000/labs/Illuminati?_response=201 text:{ "id": 4 }',
    201, '{ "id": 4 }')
test('http://127.0.0.1:5000/samples/45?_response=200 text:{ "id": 45, "validation_date": null }',
    200, '{ "id": 45, "validation_date": null }')
test("http://127.0.0.1:5000/labs/Illuminati?_response=200 text:Doesn't need to be json.\nCould be multi-line.",
    200, "Doesn't need to be json.\nCould be multi-line.")
test('http://127.0.0.1:5000/labs/Illuminati?_response=622', 622, '')

# Named Path Parameters
test('http://127.0.0.1:5000/samples/id:73/material:wood?_response=200 text:{ "id": {id}, "validation_date": null, "material": "{material}" }',
    200, '{ "id": 73, "validation_date": null, "material": "wood" }')

# Response File
test('http://127.0.0.1:5000/samples/id:74/material:wood?_response=200 file:samples/get/{id}.json',
    200, Template(file='samples/get/74.json').resolve(dict(id=74, material='wood')))

# Other URL Parameters
test('http://127.0.0.1:5000/samples/id:75/material:wood?_response=200 text:{ "id": {id}, "color": "{color}", "material": "{material}" }',
    200, '{ "id": 75, "color": "green", "material": "wood" }')
test('http://127.0.0.1:5000/samples/id:76?_response=200 file:samples/get/color/{color}.json',
    200, Template(file='samples/get/color/green.json').resolve(dict(id=76, color='green', age=7)))

