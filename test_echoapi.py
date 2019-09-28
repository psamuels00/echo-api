#!/usr/bin/env python

import requests

def test(url, expected_status_code, expected_response):
    r = requests.get(url)
    response = r.content.decode("utf-8")
    print(f'{r.status_code} {response}')
    assert r.status_code == expected_status_code
    assert response == expected_response

test('http://127.0.0.1:5000/samples/45?_response=200 { "id": 45, "validation_date": null }',
    200, '{ "id": 45, "validation_date": null }')
test('http://127.0.0.1:5000/labs/Illuminati?_response=201 { "id": 4 }',
    201, '{ "id": 4 }')
test("http://127.0.0.1:5000/labs/Illuminati?_response=200 Doesn't need to be json.\nCould be multi-line.",
    200, "Doesn't need to be json.\nCould be multi-line.")
test('http://127.0.0.1:5000/labs/Illuminati?_response=622', 622,'')

# TODO
#test('http://127.0.0.1:5000/samples/<id>/<other>?_response=200 { "id": <id>, "validation_date": null, "other": "<other>" }',
#    200, '{ "id": <id>, "validation_date": null, "other": "<other>" }')

# TODO
#test('http://127.0.0.1:5000/samples/<id>/<other>?_response_file=200 path/to/file.json',
#    200, resolved_template('path/to/file.json'))

