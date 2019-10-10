#!/usr/bin/env python

from box import Box
from echoapi import RulesTemplate

import requests
import unittest


#TODO make all request paths generic
#TODO update all test labels


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
        self.assertEqual(r.status_code, expected_status_code, f'{label} (status code)')
        self.assertEqual(content, expected_content, f'{label} (content)')


class TestSimpleResponse(TestEchoServer):
    def test_content_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response={ "id": 4 }',
            200, '{ "id": 4 }',
            'Simple static response, default status_code and location')

    def test_status_code_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=622', 622, '',
            'Static response with status code only, no content')

    def test_content_with_status_code(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=201 { "id": 4 }',
            201, '{ "id": 4 }',
            'Simple static response, default location')

    def test_extra_fields(self):
        self.case('http://127.0.0.1:5000/samples/45?_response=200 { "id": 45, "date": null }&pet=dog',
            200, '{ "id": 45, "date": null }',
            'Static response with extra fields')

    def test_plain_text_response(self):
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 {text}",
            200, text,
            'Static response with arbitrary text')


class TestResponseText(TestEchoServer):
    def test_text_content(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=201 text:{ "id": 4 }',
            201, '{ "id": 4 }',
            'Simple static text response')


class TestResponseFile(TestEchoServer):
    def test_file_content(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:ok.txt',
            200, RulesTemplate().load_file('ok.txt'),
            'Simple static file response')

    # TODO ensure trailing newline is not lost, then include this test
    def test_file_content_with_trailing_newlines(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:trail_nl.txt',
            200, RulesTemplate().load_file('trail_nl.txt'),
            'Simple static file response with trailing newlines')


class TestParameters(TestEchoServer):
    def test_named_path_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:73/material:wood?_response=200 text:{ "id": {id}, "material": "{material}" }',
            200, '{ "id": 73, "material": "wood" }',
            'Named path parameters in response')

    def test_other_url_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:75/material:wood?_response=200 text:{ "id": {id}, "color": "{color}" }',
            200, '{ "id": 75, "color": "green" }',
            'Other URL parameters in resolved content')

    def test_json_value(self):
        self.case('http://127.0.0.1:5000/samples/id:73?_response=200 text:{ "id": {id}, "dog": "{json.pet.dog.name}" }',
            200, '{ "id": 73, "dog": "Fido" }',
            'Json value in response template')

    def test_other_parameterized_file_name(self):
        params = dict(id=76, color='green', age=7)
        json = Box({})
        self.case('http://127.0.0.1:5000/samples/id:76?_response=200 file:samples/get/color/{color}.json',
            200, RulesTemplate(file='samples/get/color/green.json').resolve(params, json),
            'Other URL parameters for selection of template file')

    def test_json_parameterized_file_name(self):
        pass # TODO

    def test_path_other_and_json(self):
        params = dict(id=74, color='green')
        json = Box({ 'pet' : { 'dog': { 'name': 'Fido' }}})
        self.case('http://127.0.0.1:5000/samples/id:74?_response=200 file:samples/get/{color}/{json.pet.dog.name}/{id}.json',
            200, RulesTemplate(file='samples/get/green/Fido/74.json').resolve(params, json),
            'Content from resolved template file')


class TestSelectionRules(TestEchoServer):
    def test_no_criteria(self):
        pass # TODO

    def test_match_first_param(self):
        pass # TODO

    def test_match_second_param(self):
        pass # TODO

    def test_match_path(self):
        pass # TODO

    def test_match_json(self):
        pass # TODO

    def test_default_rule(self):
        pass # TODO

    def test_no_matching_rule(self):
        pass # TODO

    def test_blank_lines(self):
        pass # TODO


class TestRuleMarkers(TestEchoServer):
    def test_vertical_bar(self):
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 |text:{text}",
            200, text,
            'Static response with arbitrary text and vertical bars')

    def test_at(self):
        # TODO change this test to put @ before PARAM:
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 @ text:{text}",
            200, text,
            'Static response with arbitrary text and vertical bars')

    def test_gt(self):
        # TODO change this test to put @ before PATH:
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 > text:{text}",
            200, text,
            'Static response with arbitrary text and vertical bars')


class TestNestedFiles(TestEchoServer):
    def test_nested_response_files(self):
        pass # TODO

    def test_continue_after_no_match_on_nested_file(self):
        pass # TODO

