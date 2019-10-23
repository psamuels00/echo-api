# Echo API

Receive a request and return a response defined by a parameter of the request.

The response status code and content can be included in the request.  Various
type of request parameters are recognized and may be used to select from
multiple options of content to be returned.  Response content may be defined
directly in the request, or in a file referenced by the request.

The response specification is orthogonal in the sense that file content is
interpreted like content included in the request: it may contain selection
rules and nested file references.  Also, any part of the \_echo_response or
selection rules may include parameter references.  This means the status
code and selection criteria may also be parameterized.

A list of features with examples follows.


## Static Response

Return the same static response to all requests.  For example:

    http://127.0.0.1:5000/samples?_echo_response=200 { "id": 45, "validation_date": null }

## Named Path Parameters

Recognize multiple, named parameters in the url path and render them in the response.
For example:

    http://127.0.0.1:5000/samples/id:{id}/lab:{lab}?_echo_response=200 { "id": {id}, "lab": "{lab}" }

## Response Files

Allow response to come from a file treated as a template wrt the named parameters.
str.format(\*\*data) is used as the templating system.  For example:

    http://127.0.0.1:5000/samples/id:{id}?_echo_response=200 file:samples/get/response.json

## Map of Responses

Allow response file to be selected by one or more named parameters.  For example:

    http://127.0.0.1:5000/samples/id:{id}?_echo_response=200 file:samples/get/{id}.json

## Other URL Parameters

Capture parameters in the URL other than those in the request path that may be used to
resolve and/or select the response template.  This includes URL parameters supplied in
addition to \_echo_response.  For example:

    http://127.0.0.1:5000/samples/{id}?_echo_response=200 file:samples/get/color/{color}.json

## JSON in the Request Body

Provide access to fields in a json object in the body of the request that may be used to
resolve and/or select the response template.  For example:

    http://127.0.0.1:5000/samples/{id}?_echo_response=200 text:{ "group": { "name": "{json.group.name}" } }

## Selection Rules

Allow response content to be selected based on regex matching of the path, parameters, or
a value in the body of a request.  Any number of selection rules may be included for a
response.  The rules are processed in order.  When the first match is made, processing
stops and a response is generated.  A final rule with no selection criteria serves as a
default or catch-all.  Rules look something like this:

    | PATH: /.../ (text|file):...
    | HEADER:foo /.../ (text|file):...
    | PARAM:foo /.../ (text|file):...
    | JSON:pet.dog.name /.../ (text|file):...
    | BODY: /.../ (text|file):...
    | (text|file):...

The ellipses in /.../ indicate a regular expression.  The vertical bars are optional.
For rules beginning on a new line, the vertical bar can be omitted.  For example:

    200
    PATH: /delete/ text: error
    PARAM:dog /fido|spot/ text: Hi {dog}
    text: OK

## Fully Parameterized Response

In addition to being used to select rules and define the response content, parameters
and JSON fields may be used to define the status code and the selection criteria.  The
following request, for example, may be used to simulate a 404 response:

    http://127.0.0.1:5000/code:404?_echo_response={code}

The following requests all do the same thing:  when the parameter named "color"
has a value that includes the word "green", the response content is "Go":

    http://127.0.0.1:5000/type:PARAM?_echo_response=200  {type}:color  /green/ Go
    http://127.0.0.1:5000/param:color?_echo_response=200 PARAM:{param} /green/ Go
    http://127.0.0.1:5000/hue:green?_echo_response=200   PARAM:color   /{hue}/ Go


## Formatting and Whitespace

Newlines or one of the makers described above are required before any of the selectors
(HEADER, PATH, PARAM, JSON, or BODY)

The vertical bars may be included in environments where it is hard to insert newlines
into the value, or to define multiple rules on a single line.  The at symbol (@) and
greater than symbol (>) can also be used like the vertical bar.  For example, the
following lines are equivalent to the rules specification in #Selection Rules above:

    200 | PATH: /delete/ text: error | PARAM:dog /fido|spot/ text: Hi {dog} | text: OK
    200 > PATH: /delete/ text: error > PARAM:dog /fido|spot/ text: Hi {dog} > text: OK

Spaces are ignored at the beginning of any line in the rules specification with one
exception.  If the content of a rule spans multiple lines, spaces are only removed
from the first line.  They are copied verbatim on subsequent lines.

Blank lines following a text rule are considered part of the response content, whereas
blank lines following a file rule are ignored.  Spaces may be added to the rules to
make them more readable. For example:

    http://127.0.0.1:5000/samples?_echo_response=200
        PATH:       /\b100\d{3}/   file:samples/get/100xxx.json

        PARAM:name         /bob/   file:samples/get/bob.json
        PARAM:name         /sue/   file:samples/get/sue.json

        JSON:pet.dog.name  /Fido/  file:samples/get/fido.json
        JSON:pet.pig.name  /Sue/   file:samples/get/piggie.json

                                   file:samples/get/response.json

Newlines are allowed in the following places
- before and after global status code
- before and after global delay
- before text and file rules
- after file rules


## Comments

Any line beginning with '#', or whitespace followed by '#', is ignored, even if it is
included in the content of a text rule.  Consequently, there is no way to include
a comment line in the response content.  A file may look like this, for example:

    # exceptional people
    # ------------------
    PARAM:name  /bob/  file:samples/get/bob.json
    PARAM:name  /sue/  file:samples/get/sue.json

    # house plants
    # ------------
    PARAM:plant  /fern/  file:plants/get/fern.json
    PARAM:plant  /ficus/ file:plants/get/ficus.json

    # anything else
    # -------------
    PATH: /sample/ { "type": "sample" }
    PATH: /lab/    { "type": "lab" }
    #
    PARAM:id /70/  { "group": "fruit" }
    PARAM:id /71/  { "group": "vegetable" }

When included directly in the \_echo_response parameter, '#' must be encoded as %23.
For example:

    http://127.0.0.1:5000/samples?_echo_response=200
        %23 comment before rules
        PARAM:name  /bob/  file:samples/get/bob.json
        %23 another comment
        PARAM:name  /sue/  file:samples/get/sue.json"

## Limitations

- Inline \_echo_response content cannot contain '#' or '&'.  These characters must be encoded as %23 and %26 respectively.  (These characters are allowed in file content.)
- Response content cannot contain lines beginning with '#' or whitespace followed by '#'.  This is true of inline \_echo_response content as well as content stored in a file.
- The template system is based on str.format(**args), so there are limits on the use of '{' and '}' in the response content.
- Newlines not allowed in the middle of a selection rule line (see TODO below)

## TODO documentation

- update for status and delay, including nesting/override semantics
- update to include case insensitive and negation flags on the pattern
- update to describe list of response content and header to be returned in round-robin order
- streamline Formatting and Whitespace section

## TODO

 add option to reset the echo server, to clear cache, eg: _echo_cmd=reset
- add error checking everywhere (including cirular file references), and add unit tests for each condition
- make sure we do not remove space from first line of content read from a file that contains only content, and add test for this
- better testing of the multiple content option

## TODO maybe

- add support for an http location in addition to file and text
- add support for use as a library in addition to use as a service
- add option for a user id (eg: _echo_id=psamuels/healthalgo-tracking-api) to set up a shared echo server
- optimize by cacheing file contents as unresolved templates (and maybe the resolved instances too??)
- optimize by precompiling all the static regular expressions, like EchoServer.param_pat
- allow newlines anywhere in a rule (after selector type, selector target, pattern, status code, delay, or location)
- add wildcard support for parameters and JSON fields (ie: "PARAM:\*" and "JSON:\*")
- check for security of allowing any expression in the content which will be evaluated via str.format()

