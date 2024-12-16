
import inspect
import logging

from opentelemetry.sdk.trace import Span

from monocle_apptrace.utils import get_workflow_name

logger = logging.getLogger(__name__)
WORKFLOW_TYPE_KEY = "workflow_type"
DATA_INPUT_KEY = "data.input"
DATA_OUTPUT_KEY = "data.output"
PROMPT_INPUT_KEY = "data.input"
PROMPT_OUTPUT_KEY = "data.output"
QUERY = "input"
RESPONSE = "response"

INFRA_SERVICE_KEY = "infra_service_name"

TYPE = "type"
PROVIDER = "provider_name"
EMBEDDING_MODEL = "embedding_model"
VECTOR_STORE = 'vector_store'
META_DATA = 'metadata'

WORKFLOW_TYPE_MAP = {
    "llama_index": "workflow.llamaindex",
    "langchain": "workflow.langchain",
    "haystack": "workflow.haystack"
}

class SpanHandler:

    def validate(self, to_wrap, wrapped, instance, args, kwargs):
        pass

    def pre_task_processing(self, to_wrap, wrapped, instance, args, span):
        pass

    def post_task_processing(self, to_wrap, wrapped, instance, args, kwargs):
        pass

    def set_context_properties(self, to_wrap, wrapped, instance, args, kwargs):
        pass


    def hydrate_span(self, to_wrap, wrapped, instance, args, kwargs, result, span):
        self.hydrate_attributes(to_wrap, wrapped, instance, args, kwargs, result, span)
        self.hydrate_events(to_wrap, wrapped, instance, args, kwargs, result, span)


    def hydrate_attributes(self, to_wrap, wrapped, instance, args, kwargs, result, span):
        span_index = 0
        if self.__is_root_span(span):
            span_index += self.set_workflow_attributes(to_wrap, span, span_index+1)
            #span_index += self.set_app_hosting_identifier_attribute(span, span_index+1)

        if 'output_processor' in to_wrap:    
            output_processor=to_wrap['output_processor']
            if 'type' in output_processor:
                        span.set_attribute("span.type", output_processor['type'])
            else:
                logger.warning("type of span not found or incorrect written in entity json")
            if 'attributes' in output_processor:
                for processors in output_processor["attributes"]:
                    for processor in processors:
                        attribute = processor.get('attribute')
                        accessor = processor.get('accessor')

                        if attribute and accessor:
                            attribute_name = f"entity.{span_index+1}.{attribute}"
                            try:
                                arguments = {"instance":instance, "args":args, "kwargs":kwargs, "result":result}
                                result = accessor(arguments)
                                if result and isinstance(result, str):
                                    span.set_attribute(attribute_name, result)
                            except Exception as e:
                                logger.error(f"Error processing accessor: {e}")
                        else:
                            logger.warning(f"{' and '.join([key for key in ['attribute', 'accessor'] if not processor.get(key)])} not found or incorrect in entity JSON")
                    span_index += 1
            else:
                logger.warning("attributes not found or incorrect written in entity json")

        if span_index > 0:
            span.set_attribute("entity.count", span_index)


    def hydrate_events(self, to_wrap, wrapped, instance, args, kwargs, result, span):
        if 'output_processor' in to_wrap:    
            output_processor=to_wrap['output_processor']

            if 'events' in output_processor:
                events = output_processor['events']
                arguments = {"instance":instance, "arguments":args, "kwargs":kwargs, "result":result}
                for event in events:
                    event_name = event.get("name")
                    event_attributes = {}
                    attributes = event.get("attributes", [])
                    for attribute in attributes:
                        attribute_key = attribute.get("attribute")
                        accessor = attribute.get("accessor")
                        if accessor:
                            try:
                                signature = inspect.signature(accessor)
                                for keyword, value in arguments.items():
                                    if  keyword in signature.parameters:
                                        event_attributes[attribute_key] = accessor(value)
                            except Exception as e:
                                logger.error(f"Error evaluating accessor for attribute '{attribute_key}': {e}")
                    span.add_event(name=event_name, attributes=event_attributes)


    def set_workflow_attributes(self, to_wrap, span: Span, span_index):
        return_value = 1
        workflow_name = get_workflow_name(span=span)
        if workflow_name:
            span.set_attribute("span.type", "workflow")
            span.set_attribute(f"entity.{span_index}.name", workflow_name)
            # workflow type
        package_name = to_wrap.get('package')
        workflow_type_set = False
        for (package, workflow_type) in WORKFLOW_TYPE_MAP.items():
            if (package_name is not None and package in package_name):
                span.set_attribute(f"entity.{span_index}.type", workflow_type)
                workflow_type_set = True
        if not workflow_type_set:
            span.set_attribute(f"entity.{span_index}.type", "workflow.generic")
        return return_value


    def __is_root_span(self, curr_span: Span) -> bool:
        return curr_span.parent is None
