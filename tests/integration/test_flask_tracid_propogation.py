import pytest
import os, time
import requests, uuid
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from common.custom_exporter import CustomConsoleSpanExporter
from tests.common import flask_helper
from common.custom_exporter import CustomConsoleSpanExporter
from common.chain_exec import TestScopes, setup_chain
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry, start_scope, stop_scope
from monocle_apptrace.instrumentation.common.constants import SCOPE_METHOD_FILE, SCOPE_CONFIG_PATH, TRACE_PROPOGATION_URLS

CHAT_SCOPE_NAME = "chat"
CONVERSATION_SCOPE_NAME = "discussion"
CONVERSATION_SCOPE_VALUE = "conv1234"
custom_exporter = CustomConsoleSpanExporter()

@pytest.fixture(scope="module")
def setup():
    print ("Setting up Flask")
    os.environ[TRACE_PROPOGATION_URLS] = "http://127.0.0.1"
    os.environ[SCOPE_CONFIG_PATH] = os.path.join(os.path.dirname(os.path.abspath(__file__)), SCOPE_METHOD_FILE)
    flask_helper.start_flask()
    setup_monocle_telemetry(workflow_name = "flask_test", span_processors=[SimpleSpanProcessor(custom_exporter)])

@pytest.fixture(autouse=True)
def pre_test():
    # clear old spans
   custom_exporter.reset()

@pytest.mark.integration()
def test_http_flask_scope(setup):
    custom_exporter.reset()
    client_session_id = f"{uuid.uuid4().hex}"
    prompt = "What is Task Decomposition?"
    headers = {"client-id": client_session_id}
    url = flask_helper.get_url()
    token = start_scope(CONVERSATION_SCOPE_NAME, CONVERSATION_SCOPE_VALUE)
    response = requests.get(f"{url}/chat?question={prompt}", headers=headers, data={"test": "123"})
    stop_scope(token)
    verify_scopes()

def verify_scopes():
    scope_name = "conversation"
    spans = custom_exporter.get_captured_spans()
    message_scope_id = None
    trace_id = None
    for span in spans:
        span_attributes = span.attributes
        if span_attributes.get("span.type", "") in ["inference", "retrieval"]:
            if message_scope_id is None:
                message_scope_id = span_attributes.get("scope."+scope_name)
                assert message_scope_id is not None
            else:
                assert message_scope_id == span_attributes.get("scope."+scope_name)
            assert span_attributes.get("scope."+CONVERSATION_SCOPE_NAME) == CONVERSATION_SCOPE_VALUE
        if span_attributes.get("span.type", "") == "http.send":
            span_input, span_output = span.events
            assert span_attributes.get("entity.1.method").lower() == "get"
            assert span_attributes.get("entity.1.URL") is not None
            assert span_output.attributes['status'] == "200"
        if span_attributes.get("span.type", "") == "http.process":
            span_input, span_output = span.events
            assert span_attributes.get("entity.1.method").lower() == "get"
            assert span_attributes.get("entity.1.route") is not None
            assert span_output.attributes['status'] == "200"
        if trace_id is None:
            trace_id = span.context.trace_id
        else:
            assert trace_id == span.context.trace_id
