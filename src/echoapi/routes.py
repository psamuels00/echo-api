from .rules import (
    reset as rules_reset,
    rule_match_count,
)
from .echo_server import EchoServer

from flask import Flask

import time


app = Flask(__name__)


@app.route("/<path:text>", methods=["GET", "POST", "PUT", "DELETE", "HEAD"])
def all_routes(text):
    server = EchoServer(text)
    delay, resp = server.response()
    if delay:
        time.sleep(delay / 1000)
    return resp


@app.route("/", methods=["GET", "POST", "PUT", "DELETE", "HEAD"])
def root_path():
    return all_routes("/")


@app.route("/_echo_reset", methods=["GET"])
def reset():
    rules_reset()
    return "ok"


@app.route("/_echo_list_rules", methods=["GET"])
def list_rules():  # for debugging
    keys = rule_match_count.keys()
    for k in sorted(keys):
        v = rule_match_count[k]
        print(f"RULE: {v:5} {k}")
    return "ok"
