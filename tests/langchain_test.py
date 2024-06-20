

import json
import logging
import os
import time
import unittest
from unittest.mock import ANY, MagicMock, patch

import requests
from dummy_class import DummyClass
from embeddings_wrapper import HuggingFaceEmbeddings
from langchain.llms.fake import FakeListLLM
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain_community.vectorstores import faiss
from langchain_core.messages.ai import AIMessage
from langchain_core.runnables import RunnablePassthrough
from monocle_apptrace.instrumentor import (
    MonocleInstrumentor,
    set_context_properties,
    setup_monocle_telemetry,
)
from monocle_apptrace.wrap_common import (
    CONTEXT_PROPERTIES_KEY,
    PROMPT_INPUT_KEY,
    PROMPT_OUTPUT_KEY,
    update_span_from_llm_response,
)
from monocle_apptrace.wrapper import WrapperMethod
from opentelemetry import trace
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanProcessor, ConsoleSpanExporter

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
fileHandler = logging.FileHandler('traces.txt','w')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)


class TestHandler(unittest.TestCase):

    prompt = PromptTemplate.from_template(
            """
            <s> [INST] You are an assistant for question-answering tasks. Use the following pieces of retrieved context
            to answer the question. If you don't know the answer, just say that you don't know. Use three sentences
                maximum and keep the answer concise. [/INST] </s>
            [INST] Question: {question}
            Context: {context}
            Answer: [/INST]
            """
        )
    ragText = """A latte is a coffee drink that consists of espresso, milk, and foam.\
        It is served in a large cup or tall glass and has more milk compared to other espresso-based drinks.\
            Latte art can be created on the surface of the drink using the milk."""

    def __format_docs(self, docs):
            return "\n\n ".join(doc.page_content for doc in docs)

    def __createChain(self):

        resource = Resource(attributes={
            SERVICE_NAME: "coffee_rag_fake"
        })
        traceProvider = TracerProvider(resource=resource)
        exporter = ConsoleSpanExporter()
        monocleProcessor = BatchSpanProcessor(exporter)

        traceProvider.add_span_processor(monocleProcessor)
        trace.set_tracer_provider(traceProvider)
        instrumentor = MonocleInstrumentor()
        instrumentor.instrument()
        self.instrumentor = instrumentor
        self.processor = monocleProcessor
        responses=[self.ragText]
        llm = FakeListLLM(responses=responses)

        embeddings = HuggingFaceEmbeddings(model_id = "multi-qa-mpnet-base-dot-v1")
        my_path = os.path.abspath(os.path.dirname(__file__))
        model_path = os.path.join(my_path, "../data/coffee_embeddings")
        vectorstore = faiss.FAISS.load_local(model_path, embeddings, allow_dangerous_deserialization = True)

        retriever = vectorstore.as_retriever()

        rag_chain = (
            {"context": retriever| self.__format_docs, "question": RunnablePassthrough()}
            | self.prompt
            | llm
            | StrOutputParser()
        )
        return rag_chain

    def setUp(self):
        print("setUp")

    def tearDown(self) -> None:
        print("cleaning up with teardown")
        try:
            self.instrumentor.uninstrument()
        except:
            print("teardown errors")

        return super().tearDown()

    def to_json(self,obj):
        return json.dumps(obj, indent=4, default=lambda obj: obj.__dict__)

    @patch.object(requests.Session, 'post')
    def test_llm_chain(self, mock_post):
        context_key = "context_key_1"
        context_value = "context_value_1"
        set_context_properties({context_key: context_value})

        self.chain = self.__createChain()

        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = 'mock response'

        query = "what is latte"
        response = self.chain.invoke(query, config={})
        assert response == self.ragText
        time.sleep(5)
        mock_post.assert_called_with(
            url = 'https://localhost:3000/api/v1/traces',
            data=ANY,
            timeout=ANY
        )

        '''mock_post.call_args gives the parameters used to make post call.
           This can be used to do more asserts'''
        dataBodyStr = mock_post.call_args.kwargs['data']
        dataJson =  json.loads(dataBodyStr) # more asserts can be added on individual fields
        assert len(dataJson['batch']) == 7


        root_attributes = [x for x in  dataJson["batch"] if x["parent_id"] == "None"][0]["attributes"]
        assert root_attributes[PROMPT_INPUT_KEY] == query
        assert root_attributes[PROMPT_OUTPUT_KEY] == TestHandler.ragText
        assert root_attributes[f"{CONTEXT_PROPERTIES_KEY}.{context_key}"] == context_value

        for spanObject in dataJson['batch']:
            assert spanObject["context"]["span_id"].startswith("0x") == False
            assert spanObject["context"]["trace_id"].startswith("0x") == False
    def test_custom_methods(self):
        app_name = "test"
        wrap_method = MagicMock(return_value=3)
        setup_monocle_telemetry(
            workflow_name=app_name,
            span_processors=[],
            wrapper_methods=[
                WrapperMethod(
                    package="dummy_class",
                    object="DummyClass",
                    method="invoke",
                    span_name="langchain.workflow",
                    wrapper=wrap_method),

            ])
        dummy_class_1 = DummyClass()

        dummy_class_1.dummy_method()
        wrap_method.assert_called_once()

    def test_llm_response(self):
        trace.set_tracer_provider(TracerProvider())

        tracer = trace.get_tracer(__name__)

        span = tracer.start_span("foo", start_time=0)

        message = AIMessage(
            content = "",
            response_metadata = {
                'token_usage': {'completion_tokens': 58, 'prompt_tokens': 584, 'total_tokens': 642}
            }
        )
        update_span_from_llm_response(span=span,response=message)
        assert span.attributes.get("completion_tokens") == 58
        assert span.attributes.get("prompt_tokens") == 584
        assert span.attributes.get("total_tokens") == 642







if __name__ == '__main__':
    unittest.main()


