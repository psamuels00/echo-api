# Echo API

Mock API server with dynamic response capabilities.

Responses are predefined, made available to the server through files deployed
with the server, or supplied with each request as a parameter.  Dynamic
responses are selected based on some addressable component of the request
matching a regular expression pattern, including url and path parameters,
elements of a json body, the raw body, or a request header.

The response status code and content can be included in the request.  Various
type of request parameters are recognized and may be used to select from
multiple options of content to be returned.  Response content may be defined
directly in the request, or in a file referenced by the request.

## Usage summary
```
# clone repo
git@github.com:psamuels00/echo-api.git
cd echo-api

# set up Python virtual environment
pyenv virtualenv 3.7.3 echo-api
pyenv local echo-api
pip install . .[test]

# start server
./server-run-dev.sh

# run tests
pytest  # in a different terminal

# use the service
curl http://127.0.0.1:5000/?_echo_response=red.green.blue; echo

# stop server
^C

# cleanup
rm -rf build src/echo_api.egg-info

# to really clean up
pip uninstall echo-api -y
pip freeze | xargs pip uninstall -y
```

## Usage in Docker

```
start_server() {
    docker build -t echo-api .
    container_id=`docker run -dp 5000:5000 echo-api`
    echo "container_id=${container_id:0:10}" > .container_id
    docker logs -f $container_id
}

run_tests() {
    pytest
}

run_tests_in_container() {
    eval `cat .container_id`
    docker exec $container_id pytest
}

use_service() {
    curl http://127.0.0.1:5000/?_echo_response=red.green.blue.from.Docker; echo
}
stop_server() {
    eval `cat .container_id`
    docker stop $container_id
    docker rm $container_id
    docker rmi echo-api
}

start_server
run_tests
run_tests_in_container
use_service
stop_server
```

## URL Encoding

```
urlencode() {
    python3 -c "import sys, urllib.parse as ul; print(ul.quote_plus(sys.argv[1]))" "$1"
}

curl "http://127.0.0.1:5000/?_echo_response=`urlencode 'any value'`"; echo
curl "http://127.0.0.1:5000/?color=aqua&_echo_response=`urlencode '200 { "color": "{color}" }'`"; echo

curly() {
    curl "http://127.0.0.1:5000/${3}?${2}_echo_response=`urlencode "$1"`"
    echo
}

curly 'any value'
curly '200 { "color": "{color}" }' 'color=aqua&'

```

## Features

<span style="color: orange">**TODO**</span> _Update the remainder of this section._

Mention rules specification.

The response specification is orthogonal in the sense that file content is
interpreted like content included in the request: it may contain selection
rules and nested file references.  Also, any part of the \_echo_response or
selection rules may include parameter references.  This means the status
code, delay, and selection criteria may also be parameterized.

A list of features with examples follows.  In the examples, the \_echo_response
values are shown unencoded for readability.  For actual use, they should be
uri encoded.


## Minimal Usage

The minimal usage returns 200 and empty contents:

    http://127.0.0.1:5000/?_echo_response=


## Static Content

Return the same static response to all requests.  The content to return can
be any arbitrary text.  For example:

    http://127.0.0.1:5000/?_echo_response=same ol'


## Status Code

Return a status code different than 200, the default.  For example:

    http://127.0.0.1:5000/?_echo_response=201 created ok


## Template Content

The response content is actually a template that may include named parameters or json
fields in the request body.  str.format(\*\*data) is used as the templating system.
To echo back the name of a "color" parameter, for example:

    http://127.0.0.1:5000/?color=aqua&_echo_response=200 { "color": "{color}" }


## Named Path Parameters

Recognize multiple, named parameters in the url path and render them in the response.
For example:

    http://127.0.0.1:5000/id:999/lab:the_lab?_echo_response=200 { "id": {id}, "lab": "{lab}" }


## Response Files

Allow response to come from a file, also treated as a template.  For example:

    http://127.0.0.1:5000/id:{id}?_echo_response=200 file:samples/get/response.echo

Template resolution only occurs for files with an .echo extension.  The content
of other files is taken verbatim.  For example:

    http://127.0.0.1:5000/sample/?_echo_response=200 file:samples/get/response.json


## Response Maps

Allow response file to be selected by one or more named parameters.  For example:

    http://127.0.0.1:5000/id:{id}?_echo_response=200 file:samples/get/{id}.json


## Text Content

Any content not explicitly defined as file content is assumed to be text
content, but this can be made explicit.  For example

    http://127.0.0.1:5000/?_echo_response=200 text:Explicit now

There are cases when the explicit "text:" is required.  See #After.


## Other Parameters

Capture parameters in the request other than those in the path that may be used to
resolve and/or select the response template.  This includes parameters supplied in
addition to \_echo_response.  For example:

    http://127.0.0.1:5000/?_echo_response=200 file:samples/get/color/{color}.json


## JSON in the Body

Provide access to fields in a json object in the body of the request that may be used to
resolve and/or select the response template.  For example:

    http://127.0.0.1:5000/{id}?_echo_response=200 { "group": { "name": "{json.group.name}" } }


## Selection Rules

Allow response content to be selected based on regex matching of the path, headers,
parameters, a json field, or a value in the body of a request.  Selection rules
begin with a selector type and must appear on a new line.  They look like this:

    PATH: /.../ (text|file):...
    HEADER:foo /.../ (text|file):...
    PARAM:foo /.../ (text|file):...
    JSON:pet.dog.name /.../ (text|file):...
    BODY: /.../ (text|file):...

The ellipses in /.../ indicate a regular expression.  See #Pattern Matching Flags below.

Any number of selection rules may be included for a response.  The rules are
processed in order.  When the first match is made, processing stops and a
response is generated.

A final rule with no selection criteria serves as a default or catch-all.
For example, the following rules specification returns one of 3 values:

    PATH: /delete/ text: error
    PARAM:dog /fido|spot/ text: Hi {dog}
    text: OK


## After

<span style="color: orange">**TODO explain this option**</span>

Use the explicit text: to ensure a text rule with an after=XXms is interpreted as a rule
rather than as part of the currently being parsed text rule.
See test_rule_specific_after_only_no_selector.


## Delay

Wait for some number of milliseconds before responding to request.  For example:

    http://127.0.0.1:5000/?_echo_response=200 delay=5000ms ok, eventually


## Template Rules Spec

In addition to being used to select rules and define the response content, parameters
and JSON fields may be used to define the status code and the selection criteria.  The
following request, for example, may be used to simulate a 404 response:

    http://127.0.0.1:5000/code:404?_echo_response={code}

To exaggerate the point, the following requests all do the same thing:  when the
parameter named "color" has a value that includes the word "green", the response
content is "Go":

    http://127.0.0.1:5000/type:PARAM?_echo_response=200  {type}:color  /green/ Go
    http://127.0.0.1:5000/param:color?_echo_response=200 PARAM:{param} /green/ Go
    http://127.0.0.1:5000/hue:green?_echo_response=200   PARAM:color   /{hue}/ Go


## Pattern Matching Flags

Two flags are supported on the regular expressions:
- An i at the end of the pattern means case-insensitive
- An ! at the beginning of the pattern means to negate the polarity of the match

For example:

    PARAM:color  /GREEN/i   text:GrEeN, in any case
    PARAM:color  !/GREEN/   text:Not GREEN
    PARAM:color  !/GREEN/i  text:Not gReEn, in any case


## Multiple Locations

If a file is processed and no matches are made (and therefore, no
content to be returned), we continue looking for more rules
to apply.  For example:

    PARAM:fname  /bob/    file:nomatches.echo
    PARAM:lname  /smith/  file:stillnomatches.echo
                          text:no match

This works even if there are no selection criteria:

    file:nomatches.echo
    file:stillnomatches.echo
    text:no match

This works even for sequenced content.


## Attribute Scope

The status code, delay, and after can be defined specifically for a rule to
override the default or global value described above.  For example:

<span style="color: orange">**TODO example**</span>

The global values are parsed from the beginning of the line.  To avoid ambiguity
for the first rule, a separator line may be added after the global attribute
definitions.  For example:

<span style="color: orange">**TODO example**</span>


## Nested Templates

<span style="color: orange">**TODO improve this section**</span>

The contents of an .echo file may contain a single text template,
or it may contain a complete rules specification, the same format
as the \_echo_response parameter.

There is no limit to the number of file references that may be followed.
Each time a rule with .echo file content is selected, the contents of the
file are loaded, treated as a template and resolved, and then parsed as a
rules specification.  This continues until some unqualified text or
non-.echo file is defined for return, or, after all rules have been
excluded, an empty string.


## Nesting Semantics

<span style="color: orange">**TODO improve this section**</span>

There is a heirarchy of global and rule-specific, and nested files, so explain the nesting semantics: basically we override as we define more specifically on a rule, or in a file.  And a rule-specific setting for a file content and the same settings at the top of the file are two ways to do the same thing, the latter overriting the former if defined.


## Sequenced Responses

In addition to a single response content value, a list of values may be defined.
In this case, a single value is selected each time there is a match on the rule.
To select a value, we cycle through the list on successive matches.  For example:

    --[ 1 ]--
    return this on 1st call, 3rd call, etc
    --[ 2 ]--
    return this on 2nd call, 4th call, etc

The actual number used in the sequence header makes no difference:

    --[ 0 ]--
    odd calls
    --[ 0 ]--
    even calls

We can cycle through files like this:

    --[ 0 ]--
    file:events/seq1.echo
    --[ 0 ]--
    file:events/seq2.echo

We can also define multiple files and a default text value with the same semantics as described in #Multiple Locations.  For example:

    --[ 0 ]--
    file:magenta.echo
    file:triangle.echo
    --[ 0 ]--
    file:blue.echo
    text:not blue
    --[ 0 ]--
    file:tropical.echo
    not tropical

Finally, there is a compact variation on the syntax:

    --[ 0 ]-- file:events/seq1.echo
    --[ 0 ]-- file:events/seq2.echo

For the purpose of determining how many times a rule has been matched,
each rule is uniquely identified by a combination of
- the path, including named path parameters, but not the actual value
  (eg, "/sample/id" for "/sample/id:27"),
- the rule source, either the name of a file or '' for inline text content
- the selector type (ie, HEADER, PATH, PARAM, JSON, or BODY),
- the selector target (eg, 'color'), and
- the match pattern

Without this feature, the server is stateless.  With this feature in use,
the server becomes stateful.  See also _Reset_ under #Server Commands below.


## Response Headers

Headers can be included in the response definition.

<span style="color: orange">**TODO example**</span>

For sequenced respones, headers need to be repeated separately for each
block.

<span style="color: orange">**TODO example**</span>


## Formatting and Whitespace

Spaces and blank lines may be added before any rules, and before
the status code or delay spec preceding the rules or response
text (ie, the "global" status code or delay).

Spaces and blank lines may be added to the selection rules to make
them more readable. For example:

    http://127.0.0.1:5000/?_echo_response=200
        PATH:       /\b100\d{3}/   file:samples/get/100xxx.json

        PARAM:name         /bob/   file:samples/get/bob.json
        PARAM:name         /sue/   file:samples/get/sue.json

        JSON:pet.dog.name  /Fido/  file:samples/get/fido.json
        JSON:pet.pig.name  /Sue/   file:samples/get/piggie.json

                                   file:samples/get/response.json

Blank lines are ignored before and after rules with file content.
Spaces at the beginning of a line are ignored for rules with file content.


## Text Content Formatting

Like rules with file content, blank lines are ignored before rules with
text content, but blank lines are considered part of the text to be
returned and are not ignored.  A text rule ends

- at the end of the rules specification (ie, the last line)
- when another rule is defined (ie, a line beginning with a selector type, like PARAM:). For example:

      PARAM:color /green/ text:The color is green.
      PARAM:color /blue/  text:The color is blue.

- when a default rule is defined (ie, a line beginning with file: or text:, possibly with preceding spaces).  For example:

      PARAM:color /green/ text:The color is green.
      text: Unrecognized color.

In the example above, the "text:" label is required to indicate the
beginning of a new rule.  Contrast that with the following:

      PARAM:color /green/ file:/color.echo
      Unrecognized color.

In this case, the default content is preceded by a file rule, so the "text:"
label is not required.  The explicit "text:" may be added regardless and is
useful for indenting the content.  For example:

      PARAM:color /green/ text:The color is green.
      PARAM:color /blue/  text:The color is blue.
                          text:Unrecognized color.


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

    http://127.0.0.1:5000/?_echo_response=200
        %23 comment before rules
        PARAM:name  /bob/  file:samples/get/bob.json
        %23 another comment
        PARAM:name  /sue/  file:samples/get/sue.json


## Newline Markers

The HEADER, PATH, PARAM, JSON, and BODY selectors must begin on a new line.
For environments where it is hard to insert newlines into the \_echo_response
value, one of the following characters may be used instead: a vertical bar,
"@", or ">".  Each of the following lines, for example, are equivalent to the
rules specification in #Selection Rules above:

    | PATH: /delete/ text: error | PARAM:dog /fido|spot/ text: Hi {dog} | text: OK
    > PATH: /delete/ text: error > PARAM:dog /fido|spot/ text: Hi {dog} > text: OK

The newline markers may also be seen as a way to define multiple rules on a single line.
They may also be included to add visual appeal, if you're into that.  For example:

    200
    | PATH: /delete/ text: error
    | PARAM:dog /fido|spot/ text: Hi {dog}
    | text: OK


## Orthogonality

If the rules specification were fully orthogonal, we would be able to include selection criteria and
additional options on individual content element parts of a sequence rule.  For example:

    201 HEADER: X-num-elem=5
    PARAM:name /.../ 422 after=200ms
        HEADER: X-num-elem=0
        You have an error.
    PARAM:name /.../ 200
        Everything is ok.
    JSON:name.name /.../
        HEADER: X-num-elem=1
        The element was created.
    PATH: /.../
        --[ 1 ]--
        PARAM:name /.../ file:filename.echo
        PARAM:name /.../ file:filename.echo
        JSON:name.name /.../ content
        --[ 2 ]--
        200 text:content
        --[ 3 ]--
        500 delay=5000ms file:fatal.echo

We cannot do this, but we can achieve the same effect by placing each content element in a separate file.
For example, let's say we have a file named seq1.echo with the following content:

    PARAM:name /.../ file:filename.echo
    PARAM:name /.../ file:filename.echo
    JSON:name.name /.../ content

... a file named seq2.echo with the following content:

    200 text:content

...and a file named seq3.echo with the following content:

    500 delay=5000ms file:fatal.echo

Using these files, the final rule above becomes:

    PATH: /.../
        --[ 1 ]-- file:seq1.echo
        --[ 2 ]-- file:seq2.echo
        --[ 3 ]-- file:seq3.echo

...and all the selection criteria and additional options in the seq?.echo files are recognized.


## Server Commands

Reset the server.  This causes the cache to be cleared.  It is only
needed when using sequenced responses or the "after" attribute.

    http://127.0.0.1:5000/_echo_reset

List the rules.  For debugging only.

    http://127.0.0.1:5000/_echo_list_rules


## Limitations

- Inline \_echo_response content cannot contain '#' or '&'.  These characters must be encoded as %23 and %26 respectively.  (These characters are allowed in file content.)
- Response content cannot contain lines beginning with '#' or whitespace followed by '#'.  This is true of inline \_echo_response content as well as content stored in a file.
- The template system is based on str.format(**args), so there are limits on the use of '{' and '}' in the response content.
- Newlines not allowed in the middle of a selection rule line (see #TODO maybe below)
- Sequence markers have to begin on a new line


## TODO

- change file: to FILE: and text: to TEXT:
- version manage the rules specification format
- add support for an http location in addition to file and text
- add option to log, and return in a header, the rule that was matched, if any, and the sequence number
- add option to break out of text content, like @@@EndRule
- add error checking *everywhere* (including cirular file references), and add unit tests for each condition


## TODO maybe

- add more support for use as a library in addition to use as a service
- add option for a user id (eg: _echo_user=psamuels/healthalgo-tracking-api) to set up a shared echo server
- optimize by cacheing file contents as unresolved templates (and maybe the resolved instances too??)
- optimize by precompiling all the static regular expressions, like EchoServer.param_pat
- allow newlines anywhere in a rule (after selector type, selector target, pattern, status code, delay, or location)
- add rule selection capability based on a param or JSON field *not* supplied
- add support for logical combinations of selection criteria
  eg: OR PARAM:name /.../ AND PARAM:name /.../ JSON:name /.../
- add wildcard support for parameters and JSON fields (ie: "PARAM:\*" and "JSON:\*")
- check for security of allowing any expression in the content which will be evaluated via str.format()
- For more useful semantics of the sequenced content, perhaps the rule ID should be based on the path of nested file refs leading to the rule rather than just the name of the file containing the rule.  This would allow a file to be reused in multiple rules with the same selection criteria, but having been reached through a different path through the rules spec.  Not sure if this is preferred.



## Design Documentation: State Machine

***Some parts of this may have been anticipatory, pending completion of the
ambitious_attempt_to_improve_orthogonality branch.***


### Definitions
- Simple Rule: A rule with a single content value.
- Sequence Rule: A rule with multiple content sections (sequenced content).
- Content: The part of a rule that is echoed back to the client.
- Content Element: One of the content sections of a sequence rule.

### States
- INIT: Initial state, prior to any global options or rules.
- GLOBAL: We are parsing global options.
- RULE: We are parsing a simple rule, prior to parsing the content of the rule.
- CONTENT: We are parsing the content of a simple rule.
- SEQ: We are parsing a sequence rule, prior to parsing one of the content elements.
- SEQ_CONTENT: We are parsing one of the content elements of a sequence rule.

### Transitions

#### Options
On the following input...

- 999
- delay=99ms
- after=99ms
- HEADER: name=value$

...do this:

    if state is INIT or GLOBAL
        save option in global scope
        if state is INIT
            set state to GLOBAL
    elif state is RULE or SEQ
        save option in rule scope
    else (state is CONTENT or SEQ_CONTENT)
        input is read as part of content
    
#### Rule
On the following input...

- ^HEADER: name /.../
- ^PARAM: name /.../
- ^JSON: name /.../
- ^PATH: /.../
- ^BODY: /.../

...do this:

    if state is INIT or GLOBAL
        save selection criteria for the next rule
        set state to RULE
    else (state is RULE, CONTENT, SEQ, or SEQ_CONTENT)
        finish creating the current rule
        save selection criteria for the next rule
        set state to RULE

#### File Content
On the following input...

- file: filename$

...do this:

    if state is INIT or GLOBAL
        create a file rule based on the input
        set state to RULE
    elif state is RULE
        finish creating the current rule as a file rule
    elif state is CONTENT
        if match "file:" at beginning of line
            finish creating the current rule as a text rule
            create a file rule based on the input
            set state to RULE
        else
            add input to the content of the current text rule
    elif state is SEQ
        create a file rule based on the input and add it to the list for the current content element
    else (state is SEQ_CONTENT)
        finish creating the current rule as a text rule
        create a file rule based on the input and add it to the list for the current content element
        
#### Text Content
On the following input...

- text: content...
- content...

...do this:

    if state is INIT or GLOBAL
        start a text rule based on the input
        set state to RULE
    elif state is RULE
        make the current rule a text rule and add initial content
        set state to CONTENT
    elif state is CONTENT
        add to the content of the current text rule
    elif state is SEQ
        add input to the current content element
        set state to SEQ_CONTENT
    else (state is SEQ_CONTENT)
        add input to the current content element
        
#### End Element
On the following input...

--

...do this:

    if state is INIT or GLOBAL
        set state to RULE
    elif state is RULE or SEQ
        set state to CONTENT
    else (state is CONTENT or SEQ_CONTENT)
        input is read as part of content

#### Content Element
On the following input...

- --[ nn ]--

...do this:

    if state is INIT or GLOBAL
        start a sequence rule with an initial, empty content element
        set state to SEQ
    elif state is RULE
        make the current rule a sequence rule with an initial, empty content element
        set state to SEQ
    elif state is CONTENT
        if there is already some content in a text rule
            warn that it will be lost, or maybe prepend it to all content elements
        make the current rule a sequence rule with an initial, empty content element
        set state to SEQ
    else (state is SEQ or SEQ_CONTENT)
        finish the current content element
        add a new, empty content element to the current sequence rule
        
