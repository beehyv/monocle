import os
from datetime import datetime
import pytest
from .fluent_api import TraceAssertion

@pytest.fixture(scope="session", autouse=True)
def run_once_at_start_of_session():
    """
    This fixture runs once at the start of the pytest session.
    Place any setup code here that should execute only once before any tests run.
    """
    # Set LOCAL_RUN_ID only if not already set (to preserve it across session)
    if "LOCAL_RUN_ID" not in os.environ:
        os.environ["LOCAL_RUN_ID"] = datetime.now().isoformat()
    yield

@pytest.fixture()
def monocle_trace_asserter(request:pytest.FixtureRequest):
    """
    Provides a fresh TraceAssertion instance for each test.
    
    This fixture automatically handles cleanup and ensures test isolation.
    Each test gets its own clean asserter with cleared memory and empty spans.
    
    Example:
        def test_my_agent(monocle_trace_asserter):
            monocle_trace_asserter.run_agent(my_agent, "google_adk", "my_task")
            
            # Make assertions
            monocle_trace_asserter.called_tool("my_tool") \\
                .has_input("expected input") \\
                .contains_output("expected output")
    """
    traceAssertion = TraceAssertion.get_trace_asserter()
    token = traceAssertion.validator.pre_test_run_setup(request.node.name)
    exception_message = None
    try:
        result = yield traceAssertion
    except Exception as e:
        # Capture the actual exception message when test fails
        exception_message = str(e)
        raise
    finally:
        is_test_failed = _is_test_failed(request)
        if is_test_failed:
            # Priority: 1) Captured exception 2) pytest report exception 3) trace assertions
            if exception_message:
                assertion_messages = exception_message
            elif hasattr(request.node, 'rep_call') and hasattr(request.node.rep_call, 'longrepr'):
                # Try to get the actual exception from pytest's representation
                longrepr = request.node.rep_call.longrepr
                
                # If longrepr has reprcrash, use it (it has the exception message)
                if hasattr(longrepr, 'reprcrash') and longrepr.reprcrash:
                    assertion_messages = longrepr.reprcrash.message
                # If longrepr has reprtraceback with an exception entry, use that
                elif hasattr(longrepr, 'reprtraceback'):
                    # Get the exception info from the traceback
                    longrepr_str = str(longrepr)
                    # The exception message is usually after the last "E   " line
                    lines = longrepr_str.split('\n')
                    exc_lines = [line[4:] for line in lines if line.startswith('E   ')]
                    if exc_lines:
                        assertion_messages = ' '.join(exc_lines)
                    else:
                        # Fallback: look for ValueError, TypeError, etc.
                        for line in reversed(lines):
                            if 'Error:' in line or 'Exception:' in line:
                                assertion_messages = line.strip()
                                break
                        else:
                            assertion_messages = str(longrepr)
                else:
                    assertion_messages = str(longrepr)
            else:
                assertion_messages = traceAssertion.get_assertion_messages()
        else:
            assertion_messages = None
        traceAssertion.validator.post_test_cleanup(token, request.node.name, is_test_failed,
                                    assertion_messages)
        
        # Cleanup trace asserter (triggers eval cleanup including trace deletion)
        traceAssertion.cleanup()

@pytest.fixture()
def monocle_test_case(request:pytest.FixtureRequest):
    """
    Fixture for parametrized monocle test cases with automatic setup/teardown.

    Use with indirect parametrize to automatically handle monocle test lifecycle:
    - Converts dict test cases to TestCase objects
    - Sets up monocle test context (scopes, mock tools)
    - Yields the TestCase for the test to use
    - Validates spans after the test completes
    - Cleans up and exports results

    Example:
        agent_test_cases = [
            {"test_input": ["prompt"], "test_output": "expected", "comparer": "similarity"},
        ]

        @pytest.mark.parametrize("monocle_test_case", agent_test_cases, indirect=True)
        async def test_my_agent(monocle_test_case):
            await MonocleValidator().test_agent_async(agent, "google_adk", monocle_test_case)
    """
    from .validator import MonocleValidator
    from .schema import TestCase

    test_case_data = request.param
    validator = MonocleValidator()
    if isinstance(test_case_data, dict):
        test_case = TestCase.model_validate(test_case_data)
    else:
        test_case = test_case_data

    token = validator.pre_test_run_setup(request.node.name, test_case.mock_tools)
    validation_failed = False
    validation_error_message = None
    try:
        yield test_case
    except Exception as e:
        validation_failed = True
        validation_error_message = str(e)
        raise
    finally:
        try:
            validator.validate(test_case)
        except AssertionError as e:
            if not validation_failed:
                validation_failed = True
                validation_error_message = str(e)
                raise
        finally:
            is_test_failed = validation_failed or _is_test_failed(request)
            validator.post_test_cleanup(token, request.node.name, is_test_failed,
                                        validation_error_message)

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test reports and modify based on trace assertions."""
    outcome = yield
    rep = outcome.get_result()
    
    # Store report
    setattr(item, f"rep_{rep.when}", rep)
    
    # After test call phase, check trace assertions
    if rep.when == "call" and rep.outcome == "passed":
        traceAssertion:TraceAssertion = TraceAssertion()
        if traceAssertion.has_assertions():
            rep.outcome = "failed"

            rep.longrepr = traceAssertion.get_assertion_messages()


def _is_test_failed(request:pytest.FixtureRequest) -> bool:
    """Check if the test has failed based on the pytest request object."""
    return request.node.rep_call.passed == False if hasattr(request.node, "rep_call") else False