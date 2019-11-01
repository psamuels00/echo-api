#!/usr/bin/env python

from box import Box
from echoapi import RulesTemplate

import requests
import sys
import timeit
import unittest


def setUpModule():
    # reset the echo server, needed by TestMultipleResponses
    try:
        requests.get('http://127.0.0.1:5000/_echo_reset')
    except requests.exceptions.ConnectionError:
        print('Error connecting to Echo Server.', file=sys.stderr)
        print('Are you sure it is running?', file=sys.stderr)
        sys.exit(1)

setUpModule()


class TestEchoServer(unittest.TestCase):
    def setUp(self):
        # These values are included with every request.  In most cases, they are ignored, but certain tests rely on
        # certain headers, json, or params to be set, and it is easier to simply include them all with each test.
        self.headers = {
            'authorization': 'Bearer Tutti-Frutti',
            'team': 'Pirates',
        }
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

    def case(self, url, expected_status_code, expected_content, expected_headers=None, alt_color=None):
        params = self.params.copy()
        if alt_color is not None:
            params['color'] = alt_color

        r = requests.get(url, headers=self.headers, json=self.json, params=params)
        content = r.content.decode("utf-8")

        self.assertEqual(r.status_code, expected_status_code, '(status code)')
        self.assertEqual(content, expected_content, '(content)')
        if expected_headers:
            for k, v in expected_headers.items():
                self.assertEqual(r.headers[k], v)


class TestSimpleResponse(TestEchoServer):
    def test_minimal(self):
        self.case('http://127.0.0.1:5000/?_echo_response=', 200, '')

    def test_content_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_echo_response={ "id": 4 }',
            200, '{ "id": 4 }')

    def test_content_only_after_newline(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=
                     { "id": 4 }''',
            200, '{ "id": 4 }')

    def test_status_code_only(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_echo_response=622', 622, '')

    def test_status_code_only_after_newline(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=
                     622''',
            622, '')

    def test_status_code_and_content(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_echo_response=201 { "id": 4 }',
            201, '{ "id": 4 }')

    def test_status_code_and_content_after_newline(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=
                     200
                     { "id": 4 }''',
            200, '{ "id": 4 }')

    def test_extra_fields(self):
        self.case('http://127.0.0.1:5000/samples/45?_echo_response=200 { "id": 45, "date": null }&pet=dog',
            200, '{ "id": 45, "date": null }')

    def test_plain_text_response(self):
        text = r"Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_echo_response=200 {text}",
            200, text)


class TestResponseTextExplicit(TestEchoServer):
    def test_text_content(self):
        self.case('http://127.0.0.1:5000/labs/Illuminati?_echo_response=201 text:{ "id": 4 }',
            201, '{ "id": 4 }')

    def test_text_content_after_newline(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=201
                     text:{ "id": 4 }''',
            201, '{ "id": 4 }')

    def test_text_content_multiline(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=201
                     text:{ "id": 4
                     }''',
            201, '{ "id": 4\n                     }')

    def test_text_content_explicit_new_rule(self):
        self.case('''http://127.0.0.1:5000/labs/Illuminati?_echo_response=201
                     { "id": 4 }
                     text:Start new rule here''',
            201, '{ "id": 4 }\n')


class TestResponseFile(TestEchoServer):
    def test_file_content(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/ok.txt',
            200, RulesTemplate().load_file('test/ok.txt'))

    def test_file_content_with_trailing_newlines(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/trail_nl.txt',
            200, RulesTemplate().load_file('test/trail_nl.txt'))

    def test_file_then_implicit_text(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     file:test/no_match.echo
                     ok''',
                  200, 'ok')


class TestParameters(TestEchoServer):
    def test_named_path_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:73/material:wood?_echo_response=200 text:{ "id": {id}, "material": "{material}" }',
            200, '{ "id": 73, "material": "wood" }')

    def test_other_url_parameters(self):
        self.case('http://127.0.0.1:5000/samples/id:75?_echo_response=200 text:{ "id": {id}, "color": "{color}" }',
            200, '{ "id": 75, "color": "green" }')

    def test_json_value(self):
        self.case('http://127.0.0.1:5000/samples/id:77?_echo_response=200 text:{ "id": {id}, "dog": "{json.pet.dog.name}" }',
            200, '{ "id": 77, "dog": "Fido" }')


class TestParametersInFileName(TestEchoServer):
    def setUp(self):
        super().setUp()
        file = 'file:test/samples/get/green/Fido/74.json'
        delay, headers, status, content = RulesTemplate('', file).resolve(
            headers=dict(),
            params=dict(id=74, color='green', age=7),
            json=Box({'pet': {'dog': {'name': 'Fido'}}})
        )
        self.expected_delay = delay
        self.expected_headers = headers
        self.expected_status_code = status
        self.expected_content = content

    def test_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_echo_response=200 file:test/samples/get/green/Fido/{id}.json',
            200, self.expected_content)

    def test_other_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_echo_response=200 file:test/samples/get/{color}/Fido/74.json',
            200, self.expected_content)

    def test_json_parameterized_file_name(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_echo_response=200 file:test/samples/get/green/{json.pet.dog.name}/74.json',
            200, self.expected_content)

    def test_all_types_of_param(self):
        self.case('http://127.0.0.1:5000/samples/id:74?_echo_response=200 file:test/samples/get/{color}/{json.pet.dog.name}/{id}.json',
            200, self.expected_content)


class TestSelectionRules(TestEchoServer):
    def test_no_criteria(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=200 { "name": "foo" }',
            200, '{ "name": "foo" }')

    def test_rule_with_file_content(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=200 PARAM:color/green/file:test/ok.txt',
            200, RulesTemplate().load_file('test/ok.txt'))

    def test_whitespace_in_rules(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=200 PARAM:color/green/Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_echo_response=200 PARAM:color/green/text:Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_echo_response=200  PARAM: color /green/ Good', 200, 'Good')
        self.case('http://127.0.0.1:5000/it?_echo_response=200  PARAM: color /green/ text: Good', 200, 'Good')

    def test_whitespace_not_allowed_in_selector(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=200 PARAM :color /green/ text:Good',
            200, 'PARAM :color /green/ text:Good')

    def test_match_first_param(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:color /green/ { "color": "green" }
                     PARAM:color /blue/  { "color": "blue" }''',
            200, '{ "color": "green" }\n')

    def test_match_second_param(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:color /blue/  { "color": "blue" }
                     PARAM:color /green/ { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_match_path_param(self):
        self.case('''http://127.0.0.1:5000/shape:square?_echo_response=200
                     PARAM:shape /circle/  { "shape": "circle" }
                     PARAM:shape /square/  { "shape": "square" }''',
            200, '{ "shape": "square" }')

    def test_match_path(self):
        self.case('''http://127.0.0.1:5000/insect/ant?_echo_response=200
                     PATH: /insect.fly/  { "type": "fly" }
                     PATH: /insect.ant/  { "type": "ant" }''',
            200, '{ "type": "ant" }')

    def test_match_json(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     JSON:pet.dog.name /Spot/  { "pet": "Spot" }
                     JSON:pet.dog.name /^Fi/  { "pet": "{json.pet.dog.name}" }''',
            200, '{ "pet": "Fido" }')

    def test_match_body(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     BODY: /Rocky/ { "pet": "moose" }
                     BODY: /Fido/  { "pet": "dog" }''',
            200, '{ "pet": "dog" }')

    def test_variety_of_rule_types(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:shape        /circle/     { "shape": "circle" }
                     PATH:              /insect.fly/ { "type": "fly" }
                     JSON:pet.dog.name  /Spot/       { "pet": "Spot" }
                     BODY:              /Rocky/      { "pet": "moose" }
                     PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_default_rule(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:color /red/  { "color": "red" }
                     PARAM:color /blue/ { "color": "blue" }
                     text: { "color": "none" }''',
            200, '{ "color": "none" }')

    def test_implied_text_on_default_rule_not_allowed(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:color /red/   { "color": "red" }
                     PARAM:color /green/ { "color": "green" }
                     { "color": "none" }''',
            200, '{ "color": "green" }\n                     { "color": "none" }')

    def test_no_matching_rule(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                     PARAM:color /red/  { "color": "red" }
                     PARAM:color /blue/ { "color": "blue" }''',
            200, '')


class TestRuleMarkers(TestEchoServer):
    def test_vertical_bar(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                  |  PATH:              /insect.fly/ { "type": "fly" }
                  |  PARAM:shape        /circle/     { "shape": "circle" }
                  |  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_vertical_bar2(self):
        text = "Doesn't need to be json.\nCould be multi-line."
        self.case(f"http://127.0.0.1:5000/labs/Illuminati?_echo_response=200 @ text:{text}",
            200, text)

    def test_at(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                  @  PATH:              /insect.fly/ { "type": "fly" }
                  @  PARAM:shape        /circle/     { "shape": "circle" }
                  @  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')

    def test_gt(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=200
                  >  PATH:              /insect.fly/ { "type": "fly" }
                  >  PARAM:shape        /circle/     { "shape": "circle" }
                  >  PARAM:color        /green/      { "color": "green" }''',
            200, '{ "color": "green" }')


class TestParameterizeEverything(TestEchoServer):
    def test_response_status_code_evaluated(self):
        self.case('''http://127.0.0.1:5000/code:210?_echo_response={code}
                     text:gorilla''',
            210, 'gorilla')

    def test_selector_type_evaluated(self):
        self.case('''http://127.0.0.1:5000/type:PARAM?_echo_response=200
                     {type}:color /green/ Yes, green''',
            200, 'Yes, green')

    def test_selector_target_evaluated(self):
        self.case('''http://127.0.0.1:5000/param:color?_echo_response=200
                     PARAM:{param} /green/ Yes, green''',
            200, 'Yes, green')

    def test_match_pattern_evaluated(self):
        self.case('''http://127.0.0.1:5000/alt:light-green?_echo_response=200
                     PARAM:alt /light-{color}/ Yes, lightgreen''',
            200, 'Yes, lightgreen')


class TestNestedFiles(TestEchoServer):
    def test_simple_nested_response_files(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/kingdom/animalia.echo',
            200, "I'm a dog!\n")

    def test_match_param_on_nested_file(self):
        self.case('http://127.0.0.1:5000/samples/id:72?_echo_response=200 file:test/match_param.echo',
            200, '{ "color": "green" }\n')

    def test_double_hop_matching(self):
        self.case('http://127.0.0.1:5000/samples/id:72?_echo_response=200 file:test/match_json.echo',
            200, '{ "color": "green" }\n')

    def test_continue_after_no_match_on_nested_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/continue_after_no_match.echo',
            200, '{ "color": "green" }\n')

    def test_continue_after_no_match_on_nested_file_no_selector(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/no_match_file_first.echo',
            200, 'ok\n')

    def test_no_rule_selected(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/no_match.echo',
            200, '')

    def test_no_rule_selected_twice(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     file:test/no_match.echo
                     file:test/still_no_match.echo
                     text:no matches''',
            200, 'no matches')


class TestBlankLines(TestEchoServer):
    def test_blank_line_before_rules(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200

                     file:test/no_match.echo
                     text:ok''',
            200, 'ok')

    def test_blank_line_before_implied_text_rule(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200

                     ok''',
            200, 'ok')

    def test_one_blank_line_after_file(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     file:test/no_match.echo

                     text:ok''',
            200, 'ok')

    def test_two_blank_lines_after_file(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     file:test/no_match.echo


                     text:ok''',
            200, 'ok')

    def test_one_blank_line_after_text(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     PARAM:color /green/ Apple

                     text:default''',
            200, 'Apple\n\n')

    def test_two_blank_lines_after_text(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     Apple


                     text:default''',
            200, 'Apple\n\n\n')


class TestComments(TestEchoServer):
    def test_comment_before_rules(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     %23 the sky is pretty
                     the sky is blue''',
            200, 'the sky is blue')

    def test_comment_after_file_rule(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     file:test/no_match.echo
                     %23 no match so far
                     text: got match?''',
            200, 'got match?')

    def test_comment_after_text_rule(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     Bananas are fun.
                     %23 go bananas!
                     text: unreachable rule''',
            200, 'Bananas are fun.\n')

    def test_comment_in_middle_of_text_rule(self):
        self.case('''http://127.0.0.1:5000/samples?_echo_response=200
                     Bananas are fun.
                     %23 go bananas!
                     Peaches are fun too!''',
            200, 'Bananas are fun.\n                     Peaches are fun too!')


class TestCommentsInFiles(TestEchoServer):
    def test_comments_in_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/comments.echo',
            200, 'porcupine\n')

    def test_comment_before_rules_in_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/comment_before_rules.echo',
            200, 'the sky is blue\n')

    def test_comment_after_file_rule_in_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/comment_after_file.echo',
            200, 'got match?\n')

    def test_comment_after_text_rule_in_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/comment_after_text.echo',
            200, 'Bananas are fun.\n')

    def test_comment_in_middle_of_text_rule_in_file(self):
        self.case('http://127.0.0.1:5000/samples?_echo_response=200 file:test/comment_in_middle_of_text.echo',
            200, 'Bananas are fun.\nPeaches are fun too!\n')


class TestDefineHeadersInResponse(TestEchoServer):
    def test_header_default_content_type(self):
        expected_headers = { 'content-type': 'text/html; charset=utf-8' }
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     { "id": 4 }''',
            200, '{ "id": 4 }', expected_headers)

    def test_header_in_response(self):
        expected_headers = { 'content-type': 'plain/text' }
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     HEADER: content-type: plain/text
                     { "id": 4 }''',
            200, '{ "id": 4 }', expected_headers)

    def test_headers_in_response(self):
        expected_headers = {
            'content-type': 'plain/text',
            'Genre': 'Classical',
        }
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     HEADER: content-type: plain/text
                     HEADER: Genre: Classical
                     { "id": 4 }''',
            200, '{ "id": 4 }', expected_headers)

    def test_header_in_selected_response(self):
        expected_headers = { 'Genre': 'Classical' }
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     PARAM:color /green/ HEADER: Genre: Classical
                     { "id": 4 }''',
            200, '{ "id": 4 }', expected_headers)

    def test_header_in_selected_response_not_first(self):
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     PARAM:color /blue/ HEADER: Genre: Classical
                     { "id": 4 }
                     PARAM:color /green/ HEADER: Genre: Reggae
                     { "id": 5 }''',
            200, '{ "id": 5 }', { 'Genre': 'Reggae' })


class TestSelectRuleByHeader(TestEchoServer):
    def test_selection_by_header(self):
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     HEADER:Content-Type /binary/ no, binary
                     HEADER:Content-Type /application.json/ yes, json response format''',
            200, 'yes, json response format')


class TestHeaderInResponseContent(TestEchoServer):
    def test_include_header_in_response(self):
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     The "team" header is "{header.Team}"''',
            200, 'The "team" header is "Pirates"')

    def test_include_header_with_punctuation_in_response(self):
        self.case('''http://127.0.0.1:5000/hdr?_echo_response=200
                     The "team" header is "{header.Content_Type}"''',
            200, 'The "team" header is "application/json"')


class TestDelay(TestEchoServer):
    def delay_case(self, expected_delay, *args):
        fun = lambda: self.case(*args)
        duration = int(timeit.timeit(fun, number=1) * 1000)
        self.assertGreaterEqual(duration, expected_delay)
        self.assertLessEqual(duration, expected_delay + 50)

    def test_global_delay_only(self):
        self.delay_case(500, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms PARAM:color /green/ fig''', 200, 'fig')

    def test_rule_specific_delay_only(self):
        self.delay_case(300, '''http://127.0.0.1:5000?_echo_response=
            PARAM:color /green/ delay=300ms fig''', 200, 'fig')

    def test_global_and_rule_specific_delay(self):
        self.delay_case(300, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms PARAM:color /green/ delay=300ms fig''', 200, 'fig')

    def test_rule_specific_with_file_contents(self):
        self.delay_case(300, '''http://127.0.0.1:5000?_echo_response=
            PARAM:color /green/ delay=300ms file:test/delay/simple.echo''', 200, 'fig\n')

    def test_global_delay_override_by_nested_rule(self):
        self.delay_case(200, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms file:test/delay/override.echo''', 200, 'mango\n')

    def test_rule_specific_delay_override_by_nested_rule(self):
        self.delay_case(200, '''http://127.0.0.1:5000?_echo_response=
            PARAM:color /green/ delay=500ms file:test/delay/override.echo''', 200, 'mango\n')

    def test_override_nested_first_line(self):
        self.delay_case(200, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms file:test/delay/override_first_line.echo''', 200, 'mango\n')

    def test_override_nested_global_for_selection(self):
        self.delay_case(100, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms file:test/delay/global_for_selection.echo''', 200, 'mango\n')

    def test_override_in_selection(self):
        self.delay_case(200, '''http://127.0.0.1:5000?_echo_response=
            delay=500ms file:test/delay/override_in_selection.echo''', 200, 'mango\n')

    def test_override_of_non_matching_rules(self):
        self.delay_case(100, '''http://127.0.0.1:5000?_echo_response=
            delay=100ms PARAM:color /blue/ delay=300ms fig
            text:cherry''', 200, 'cherry')


class TestStatusCodeOverrides(TestEchoServer):
    def test_override_default_status_code_in_selection(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=PARAM:color /green/ 201 mouse', 201, 'mouse')

    def test_override_status_code_in_selection(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=404 PARAM:color /green/ 201 mouse', 201, 'mouse')

    def test_override_default_status_code_and_delay_in_selection(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=PARAM:color /green/ 201 delay=10ms  mouse', 201, 'mouse')

    def test_override_status_code_and_delay_in_selection(self):
        self.case('http://127.0.0.1:5000/it?_echo_response=404 delay=10ms PARAM:color /green/ 201 mouse', 201, 'mouse')

    def test_override_status_code_in_nested_file(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=
                     file:test/delay/override_status_code.echo''', 201, 'turkey\n')

    def test_override_status_code_in_nested_file_selection(self):
        self.case('''http://127.0.0.1:5000/it?_echo_response=
                     file:test/delay/override_status_code_in_selection.echo''', 201, 'turkey\n')


class TestMatchingOptions(TestEchoServer):
    def test_case_sensitive_match(self):
        self.case('''http://127.0.0.1:5000/?_echo_response=200
                     PARAM:color /GREEN/ case-insensitive match
                     PARAM:color /green/ case-sensitive match''',
            200, 'case-sensitive match')

    def test_case_insensitive_match(self):
        self.case('''http://127.0.0.1:5000/?_echo_response=200
                     PARAM:color /GREEN/i case-insensitive match
                     PARAM:color /green/ case-sensitive match''',
            200, 'case-insensitive match\n')

    def test_positive_match(self):
        self.case('''http://127.0.0.1:5000/?_echo_response=200
                     PARAM:color /blue/ blue birds
                     PARAM:color /green/ bingo''',
            200, 'bingo')

    def test_negative_match(self):
        self.case('''http://127.0.0.1:5000/?_echo_response=200
                     PARAM:color !/e/    not e
                     PARAM:color !/blue/ blue birds
                     PARAM:color /green/ never get here''',
            200, 'blue birds\n')


class TestSpaceRemoval(TestEchoServer):
    def test_space_removal_on_first_line_of_text_content(self):
        self.case('''http://127.0.0.1:5000/?_echo_response=200
                     trimmed, like hedges''',
            200, 'trimmed, like hedges')

    def test_retain_space_on_first_line_of_file_content(self):
        self.case('http://127.0.0.1:5000/?_echo_response=200 file:test/beginning_with_space.echo',
            200, '    Four spaces.\nThen none.\n')


class TestMultipleResponses(TestEchoServer):
    def test_two_responses_alternating(self):
        url = '''http://127.0.0.1:5000/test/case/1/?_echo_response=200
                 --[ 1 ]--
                 peanuts
                 --[ 2 ]--
                 cashews'''
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews')
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews')

    def test_three_responses_alternating_any_sequence_number(self):
        url = '''http://127.0.0.1:5000/test/case/2/?_echo_response=200
                 --[ 0 ]--
                 insect
                 --[ 0 ]--
                 bird
                 --[ 0 ]--
                 fish'''
        self.case(url, 200, 'insect\n')
        self.case(url, 200, 'bird\n')
        self.case(url, 200, 'fish')
        self.case(url, 200, 'insect\n')

    def test_multiple_response_selected_content(self):
        url = '''http://127.0.0.1:5000/test/case/3/?_echo_response=200
                 PARAM:color /green/
                     --[ 1 ]--
                     alpha
                     --[ 2 ]--
                     beta
                 PARAM:color /purple/
                      --[ 1 ]--
                     gamma
                     --[ 2 ]--
                     delta'''
        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'gamma\n', alt_color='purple')
        self.case(url, 200, 'delta', alt_color='purple')

        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'gamma\n', alt_color='purple')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'delta', alt_color='purple')

    def test_multiple_response_selected_content_by_path_param(self):
        url = '''http://127.0.0.1:5000/test/case/4/kolor:{}?_echo_response=200
                 PARAM:kolor /green/
                     --[ 1 ]--
                     alpha
                     --[ 2 ]--
                     beta
                 PARAM:kolor /beige/
                     --[ 1 ]--
                     gamma
                     --[ 2 ]--
                     delta'''
        green_url = url.format('green')
        beige_url = url.format('beige')
        self.case(green_url, 200, 'alpha\n')
        self.case(green_url, 200, 'beta\n')
        self.case(beige_url, 200, 'gamma\n')
        self.case(beige_url, 200, 'delta')

        self.case(green_url, 200, 'alpha\n')
        self.case(beige_url, 200, 'gamma\n')
        self.case(green_url, 200, 'beta\n')
        self.case(green_url, 200, 'alpha\n')
        self.case(green_url, 200, 'beta\n')
        self.case(beige_url, 200, 'delta')

    def test_multiple_response_from_file(self):
        url = 'http://127.0.0.1:5000/test/case/5/?_echo_response=200 file:test/multi_content.echo'
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews\n')
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews\n')

    def test_multiple_response_selected_content_from_file(self):
        url = 'http://127.0.0.1:5000/test/case/5/?_echo_response=200 file:test/multi_select_content.echo'
        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'gamma\n', alt_color='purple')
        self.case(url, 200, 'delta\n', alt_color='purple')

        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'gamma\n', alt_color='purple')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'alpha\n')
        self.case(url, 200, 'beta\n')
        self.case(url, 200, 'delta\n', alt_color='purple')

    def test_cycle_through_files(self):
        url = '''http://127.0.0.1:5000/test/seq/1/?_echo_response=200
                 --[ 0 ]--
                 file:test/seq/1.json
                 --[ 0 ]--
                 file:test/seq/2.json'''
        self.case(url, 200, '{ "value": 1 }\n')
        self.case(url, 200, '{ "value": 2 }\n')

    def test_cycle_through_files_compact_syntax(self):
        url = '''http://127.0.0.1:5000/test/seq/2/?_echo_response=200
                 --[ 0 ]-- file:test/seq/1.json
                 --[ 0 ]-- file:test/seq/2.json'''
        self.case(url, 200, '{ "value": 1 }\n')
        self.case(url, 200, '{ "value": 2 }\n')

    def test_explicit_text_label(self):
        url = '''http://127.0.0.1:5000/test/case/6/?_echo_response=200
                 --[ 0 ]--
                 peanuts
                 --[ 0 ]--
                 text:peanuts
                 --[ 0 ]--
                 text:cashews'''
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews')

    def test_file_and_text_implicit_and_explicit(self):
        url = '''http://127.0.0.1:5000/test/case/7/?_echo_response=200
                 --[ 0 ]--
                 file:test/seq/1.json
                 --[ 0 ]--
                 text:non-label-free
                 --[ 0 ]--
                 label-free'''
        self.case(url, 200, '{ "value": 1 }\n')
        self.case(url, 200, 'non-label-free\n')
        self.case(url, 200, 'label-free')

    def test_no_matching_content(self):
        url = '''http://127.0.0.1:5000/test/case/9/?_echo_response=200
                 --[ 0 ]--
                 file:test/no_match.echo
                 --[ 0 ]--
                 '''
        self.case(url, 200, '')
        self.case(url, 200, '')

    def test_explicit_text_label_multiple_lines(self):
        url = '''http://127.0.0.1:5000/test/case/10/?_echo_response=200
                 --[ 0 ]--
                 text:peanuts
                 and popcorn
                 --[ 0 ]--
                 text:cashews'''
        self.case(url, 200, 'peanuts\n                 and popcorn\n')
        self.case(url, 200, 'cashews')

    def test_multiple_response_selected_content_from_file_by_path_param(self):
        url = '''http://127.0.0.1:5000/test/case/4/kolor:{}?_echo_response=200
                 PARAM:kolor /green/
                     --[ 1 ]--
                     file:test/seq/1.json
                     --[ 2 ]--
                     file:test/seq/2.json
                 PARAM:kolor /beige/
                     --[ 1 ]--
                     file:test/seq/1.json
                     --[ 2 ]--
                     text:aardvark'''
        green_url = url.format('green')
        beige_url = url.format('beige')
        self.case(green_url, 200, '{ "value": 1 }\n')
        self.case(green_url, 200, '{ "value": 2 }\n')
        self.case(beige_url, 200, '{ "value": 1 }\n')
        self.case(beige_url, 200, 'aardvark')

    def test_header_in_response(self):
        expected_headers = [
            { 'content-type': 'plain/text' },
            { 'content-type': 'json' },
            {},
        ]
        url = '''http://127.0.0.1:5000/hdr/2?_echo_response=200
                 --[ 1 ]--
                 HEADER: content-type: plain/text
                 text: { "id": 5 }
                 --[ 1 ]--
                 HEADER: content-type: json
                 text: { "id": 6 }
                 --[ 1 ]--
                 no header'''
        self.case(url, 200, '{ "id": 5 }\n', expected_headers[0])
        self.case(url, 200, '{ "id": 6 }\n', expected_headers[1])
        self.case(url, 200, 'no header', expected_headers[2])

    def test_content_before_first_marker(self):
        url = '''http://127.0.0.1:5000/test/case/8/?_echo_response=200
                 suspicious text. this will be ignored.
                 --[ 0 ]--
                 text:peanuts
                 --[ 0 ]--
                 text:cashews'''
        self.case(url, 200, 'peanuts\n')
        self.case(url, 200, 'cashews')

    def test_ignore_lines_after_file_rule(self):
        url = '''http://127.0.0.1:5000/test/case/9/?_echo_response=200
                 --[ 0 ]--
                 file:test/seq/1.json
                 this line ignored
                 --[ 0 ]--
                 file:test/seq/2.json
                 this line ignored also
                 '''
        self.case(url, 200, '{ "value": 1 }\n')
        self.case(url, 200, '{ "value": 2 }\n')

    def test_multiple_locations_in_content(self):
        url = '''http://127.0.0.1:5000/test/case/9/?_echo_response=200
                 --[ 0 ]--
                 file:test/no_match.echo
                 file:test/still_no_match.echo
                 text:no matches
                 --[ 0 ]--
                 file:test/no_match.echo
                 no match again'''
        self.case(url, 200, 'no matches\n')
        self.case(url, 200, '                 no match again')

