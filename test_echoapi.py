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
        self.case('http://127.0.0.1:5000/it?_response=200 { "name": "foo" }',
            200, '{ "name": "foo" }')

    def test_whitespace_in_rules(self):
        self.case('http://127.0.0.1:5000/it?_response=200 PARAM:color/green/Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_response=200 PARAM:color/green/text:Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_response=200  PARAM: color /green/ Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_response=200  PARAM: color /green/ text: Good', 200, 'Good')

    def test_whitespace_not_allowed_in_selector(self):
        self.case('http://127.0.0.1:5000/it?_response=200 PARAM :color /green/ text:Good',
            200, 'PARAM :color /green/ text:Good')

    def test_match_first_param(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:color /green/ { "color": "green" }
                     PARAM:color /blue/  { "color": "blue" }''',
            200, '{ "color": "green" }\n')

    def test_match_second_param(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:color /blue/  { "color": "blue" }
                     PARAM:color /green/ { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_match_path_param(self):
        self.case('''http://127.0.0.1:5000/shape:square?_response=200
                     PARAM:shape /circle/  { "shape": "circle" }
                     PARAM:shape /square/  { "shape": "square" }''',
            200, '{ "shape": "square" }')

    def test_match_path(self):
        self.case('''http://127.0.0.1:5000/insect/ant?_response=200
                     PATH: /insect.fly/  { "type": "fly" }
                     PATH: /insect.ant/  { "type": "ant" }''',
            200, '{ "type": "ant" }')

    def test_match_json(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     JSON:pet.dog.name /Spot/  { "pet": "Spot" }
                     JSON:pet.dog.name /^Fi/  { "pet": "{json.pet.dog.name}" }''',
            200, '{ "pet": "Fido" }')

    def test_match_body(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     BODY: /Rocky/ { "pet": "moose" }
                     BODY: /Fido/  { "pet": "dog" }''',
                  200, '{ "pet": "dog" }')

    def test_variety_of_rule_types(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:shape        /circle/     { "shape": "circle" }
                     PATH:              /insect.fly/ { "type": "fly" }
                     JSON:pet.dog.name  /Spot/       { "pet": "Spot" }
                     BODY:              /Rocky/      { "pet": "moose" }
                     PARAM:color        /green/      { "color": "green" }''',
                  200, '{ "color": "green" }')

    def test_default_rule(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:color /red/  { "color": "red" }
                     PARAM:color /blue/ { "color": "blue" }
                     text: { "color": "none" }''',
            200, '{ "color": "none" }')

    def test_implied_text_on_default_rule_not_allowed(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:color /red/   { "color": "red" }
                     PARAM:color /green/ { "color": "green" }
                     { "color": "none" }''',
                  200, '{ "color": "green" }\n                     { "color": "none" }')

    def test_no_matching_rule(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                     PARAM:color /red/  { "color": "red" }
                     PARAM:color /blue/ { "color": "blue" }''',
            200, '')


class TestRuleMarkers(TestEchoServer):
    def test_vertical_bar(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                  |  PATH:              /insect.fly/ { "type": "fly" }
                  |  PARAM:shape        /circle/     { "shape": "circle" }
                  |  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_vertical_bar2(self):
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_response=200 @ text:{text}",
            200, text)

    def test_at(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                  @  PATH:              /insect.fly/ { "type": "fly" }
                  @  PARAM:shape        /circle/     { "shape": "circle" }
                  @  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_gt(self):
        self.case('''http://127.0.0.1:5000/it?_response=200
                  >  PATH:              /insect.fly/ { "type": "fly" }
                  >  PARAM:shape        /circle/     { "shape": "circle" }
                  >  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')


class TestNestedFiles(TestEchoServer):
    def test_simple_nested_response_files(self):
        self.case('http://127.0.0.1:5000/samples?_response=200 file:kingdom/animalia.echo',
            200, "I'm a dog!\n")

    def test_no_rule_selected(self):
        pass # TODO

    def test_continue_after_no_match_on_nested_file(self):
        pass # TODO

    def test_match_param_on_nested_file(self):
        pass # TODO

    def test_match_param_on_nested_file_then_match_json(self):
        pass # TODO


class TestBlankLines(TestEchoServer):

    def test_one_blank_line_after_file(self):
        pass # TODO

    def test_three_blank_lines_after_file(self):
        pass # TODO

    def test_one_blank_line_after_text(self):
        pass # TODO

    def test_three_blank_lines_after_text(self):
        pass # TODO

