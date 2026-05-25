"""Tests for workflow duplicate parameter validation."""
import pytest
from src.orchestrator.workflow import Workflow, WorkflowStep, WorkflowValidationError


class TestWorkflowValidation:
    def test_valid_workflow(self):
        wf = Workflow("test", [
            WorkflowStep(name="step1", agent="agent_a", input={"query": "hello"}),
            WorkflowStep(name="step2", agent="agent_b", input={"result": "world"}),
        ])
        assert wf.name == "test"
        assert len(wf.steps) == 2

    def test_duplicate_step_names_raises(self):
        with pytest.raises(WorkflowValidationError, match="Duplicate step name"):
            Workflow("bad", [
                WorkflowStep(name="same", agent="a"),
                WorkflowStep(name="same", agent="b"),
            ])

    def test_duplicate_param_alias_raises(self):
        with pytest.raises(WorkflowValidationError, match="Duplicate parameter alias"):
            Workflow("test", [
                WorkflowStep(name="s1", agent="a", input={"user_name": "alice"}),
                WorkflowStep(name="s2", agent="b", input={"username": "bob"}),
            ])

    def test_different_params_accepted(self):
        wf = Workflow("test", [
            WorkflowStep(name="s1", agent="a", input={"user_id": "1"}),
            WorkflowStep(name="s2", agent="b", input={"report_id": "2"}),
        ])
        assert len(wf.steps) == 2

    def test_add_step_valid(self):
        wf = Workflow("test", [WorkflowStep(name="s1", agent="a")])
        wf.add_step(WorkflowStep(name="s2", agent="b"))
        assert len(wf.steps) == 2

    def test_add_duplicate_step_raises(self):
        wf = Workflow("test", [WorkflowStep(name="s1", agent="a")])
        with pytest.raises(WorkflowValidationError):
            wf.add_step(WorkflowStep(name="s1", agent="b"))
        # Step should not be added
        assert len(wf.steps) == 1
