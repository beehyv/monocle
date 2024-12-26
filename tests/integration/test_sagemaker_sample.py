import json
import os
import time
from typing import Dict, List

import boto3
from common.custom_exporter import CustomConsoleSpanExporter
import pytest
from langchain_community.embeddings import SagemakerEndpointEmbeddings
from langchain_community.embeddings.sagemaker_endpoint import EmbeddingsContentHandler
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import RequestsHttpConnection
from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from requests_aws4auth import AWS4Auth

from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry


custom_exporter = CustomConsoleSpanExporter()
@pytest.fixture(scope="module")
def setup():
    setup_monocle_telemetry(
        workflow_name="sagemaker_workflow_1",
        span_processors=[BatchSpanProcessor(custom_exporter)],
        wrapper_methods=[]
    )


@pytest.mark.integration()
def test_sagemaker_sample(setup):
    query = "how"
    #similar_documents = search_similar_documents_opensearch(query)
    produce_llm_response(query)
    time.sleep(30)
    spans = custom_exporter.get_captured_spans()

    for span in spans:
        span_attributes = span.attributes
        if "span.type" in span_attributes and span_attributes["span.type"] == "inference":
            # Assertions for all inference attributes
            assert span_attributes["entity.1.name"] == "sagemaker_workflow_1"
            assert span_attributes["entity.1.type"] == "workflow.generic"
            assert span_attributes["entity.2.type"] == "inference.aws_sagemaker"
            assert "entity.2.inference_endpoint" in span_attributes
            assert span_attributes["entity.3.name"] == "okahu-sagemaker-rag-qa-ep"
            assert span_attributes["entity.3.type"] == "model.llm.okahu-sagemaker-rag-qa-ep"



def produce_llm_response(query):
    client = boto3.client('sagemaker-runtime', region_name='us-east-1')

    endpoint_name = "okahu-sagemaker-rag-qa-ep"  # Your endpoint name.
    content_type = "application/json"  # The MIME type of the input data in the request body.
    accept = "application/json"  # The desired MIME type of the inference in the response.

    data = {
        "context": """You are an assistant for question-answering tasks. \
Use the following pieces of retrieved context to answer the question. \
If you don't know the answer, just say that you don't know. \
Use three sentences maximum and keep the answer concise.\
""" ,
        "question": query
    }

    response = client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType=content_type,
        Accept=accept,
        Body=json.dumps(data)
    )

    content = response['Body'].read()

    # Print the content
    response_str = content.decode('utf-8')
    print(f"The response provided by the endpoint: {response_str}")

    answer = json.loads(response_str)["answer"]
    return answer


def build_context(similar_documents):
    if len(similar_documents) > 0:
        documents_concatenated = "-------------END OF DOCUMENT-------------".join(similar_documents)
        return f"""Based on embedding lookup, we've found these documents to be the most relevant from the knowledge 
        base: {documents_concatenated}"""
    else:
        return "We couldn't locate any documents that would be relevant for this question. Please apologize politely " \
               "and say that you don't know the answer if this is not something you can answer on your own."


def search_similar_documents_opensearch(query):
    opensearch_url = os.environ['OPENSEARCH_ENDPOINT_URL_BOTO']
    index_name = "embeddings"  # Your index name
    content_handler = ContentHandler()
    sagemaker_endpoint_embeddings = SagemakerEndpointEmbeddings(endpoint_name="okahu-sagemaker-rag-embedding-ep",
                                                                region_name="us-east-1",
                                                                content_handler=content_handler)
    region = 'us-east-1'
    service = 'aoss'
    credentials = boto3.Session().get_credentials()
    aws_auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service,
                        session_token=credentials.token)
    doc_search = OpenSearchVectorSearch(
        opensearch_url=opensearch_url,
        index_name=index_name,
        embedding_function=sagemaker_endpoint_embeddings,
        http_auth=aws_auth,
        use_ssl=True,
        verify_certs=True,
        ssl_assert_hostname=True,
        ssl_show_warn=True,
        connection_class=RequestsHttpConnection
    )
    docs = doc_search.similarity_search(query)
    print(f"Retrieved docs: {docs}")
    return [doc.page_content for doc in docs]


class ContentHandler(EmbeddingsContentHandler):
    content_type = "application/json"
    accepts = "application/json"

    def transform_input(self, inputs: List[str], model_kwargs: Dict) -> bytes:
        input_str = json.dumps({"text_inputs": inputs, **model_kwargs})
        return input_str.encode("utf-8")

    def transform_output(self, output: bytes) -> List[List[float]]:
        response_json = json.loads(output.read().decode("utf-8"))
        return response_json["embedding"]

#
# {
#     "name": "botocore-sagemaker-runtime-invoke-endpoint",
#     "context": {
#         "trace_id": "0xd3c554d5335e94524366adb9574cd532",
#         "span_id": "0xe8076532c5d9eda2",
#         "trace_state": "[]"
#     },
#     "kind": "SpanKind.INTERNAL",
#     "parent_id": null,
#     "start_time": "2024-12-26T10:30:21.283691Z",
#     "end_time": "2024-12-26T10:30:22.466974Z",
#     "status": {
#         "status_code": "UNSET"
#     },
#     "attributes": {
#         "entity.1.name": "sagemaker_workflow_1",
#         "entity.1.type": "workflow.generic",
#         "span.type": "inference",
#         "entity.2.type": "inference.aws_sagemaker",
#         "entity.2.inference_endpoint": "https://runtime.sagemaker.us-east-1.amazonaws.com",
#         "entity.3.name": "okahu-sagemaker-rag-qa-ep",
#         "entity.3.type": "model.llm.okahu-sagemaker-rag-qa-ep",
#         "entity.count": 3
#     },
#     "events": [
#         {
#             "name": "data.input",
#             "timestamp": "2024-12-26T10:30:22.466974Z",
#             "attributes": {
#                 "input": [
#                     "how"
#                 ]
#             }
#         },
#         {
#             "name": "data.output",
#             "timestamp": "2024-12-26T10:30:22.466974Z",
#             "attributes": {
#                 "response": [
#                     "Use the following pieces of retrieved context"
#                 ]
#             }
#         },
#         {
#             "name": "metadata",
#             "timestamp": "2024-12-26T10:30:22.466974Z",
#             "attributes": {}
#         }
#     ],
#     "links": [],
#     "resource": {
#         "attributes": {
#             "service.name": "sagemaker_workflow_1"
#         },
#         "schema_url": ""
#     }
# }
