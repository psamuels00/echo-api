#!/usr/bin/env python

from box import Box
from echoapi import RulesTemplate

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

    def case(self, url, expected_status_code, expected_content):
        r = requests.get(url, json=self.json, params=self.params)
        content = r.content.decode("utf-8")
        self.assertEqual(r.status_code, expected_status_code, '(status code)')
        self.assertEqual(content, expected_content, '(content)')


class TestSimpleResponse(TestEchoServer):
    def test_content_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response={ "id": 4 }',
            200, '{ "id": 4 }')

    def test_status_code_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=622', 622, '')

    def test_content_with_status_code(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=201 { "id": 4 }',
            201, '{ "id": 4 }')

    def test_extra_fields(self):
        self.case('http://127.0.0.1:5000/samples/45?_response=200 { "id": 45, "date": null }&pet=dog',
            200, '{ "id": 45, "date": null }')

    def test_plain_text_response(self):
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 {text}",
            200, text)


class TestResponseTextExplicit(TestEchoServer):
    def test_text_content(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_response=201 text:{ "id": 4 }',
            201, '{ "id": 4 }')


class TestResponseFile(TestEchoServer):
    def test_file_content(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:ok.txt',
            200, RulesTemplate().load_file('ok.txt'))

    def test_file_content_with_trailing_newlines(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:trail_nl.txt',
            200, RulesTemplate().load_file('trail_nl.txt'))


class TestParameters(TestEchoServer):
    def test_named_path_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:73/material:wood?_response=200 text:{ "id": {id}, "material": "{material}" }',
            200, '{ "id": 73, "material": "wood" }')

    def test_other_url_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:75?_response=200 text:{ "id": {id}, "color": "{color}" }',
            200, '{ "id": 75, "color": "green" }')

    def test_json_value(self):
        self.case('http://127.0.0.1:5000/samples/id:77?_response=200 text:{ "id": {id}, "dog": "{json.pet.dog.name}" }',
            200, '{ "id": 77, "dog": "Fido" }')


class TestParametersInFileName(TestEchoServer):
    def setUp(self):
        super().setUp()
        self.expected_content = RulesTemplate(file='samples/get/green/Fido/74.json').resolve(
            params=dict(id=74, color='green', age=7),
            json=Box({'pet': {'dog': {'name': 'Fido'}}})
        )

    def test_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_response=200 file:samples/get/green/Fido/{id}.json',
            200, self.expected_content)

    def test_other_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_response=200 file:samples/get/{color}/Fido/74.json',
            200, self.expected_content)

    def test_json_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_response=200 file:samples/get/green/{json.pet.dog.name}/74.json',
            200, self.expected_content)

    def test_all_types_of_param(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_response=200 file:samples/get/{color}/{json.pet.dog.name}/{id}.json',
            200, self.expected_content)


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
            200, text)

    def test_at(self):
        # TODO change this test to put @ before PARAM:
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 @ text:{text}",
            200, text)

    def test_gt(self):
        # TODO change this test to put @ before PATH:
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 > text:{text}",
            200, text)


class TestNestedFiles(TestEchoServer):
    def test_simple_nested_response_files(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:kingdom/animalia.echo',
            200, "I'm a dog!\n")

    def test_no_rule_selected(self):
        pass # TODO

    def test_continue_after_no_match_on_nested_file(self):
        pass # TODO

    def test_nested_response_files(self):
        pass # TODO

