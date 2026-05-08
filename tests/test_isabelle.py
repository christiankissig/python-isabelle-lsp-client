from isabelle_lsp_client.isabelle import (
    command_finishes_subgoal,
    get_command_from_sledgehammer,
    is_isabelle_ready,
    is_sledgehammer_done,
    is_sledgehammer_noproof,
)


class TestIsIsabelleReady:
    def test_returns_true_for_welcome_message(self):
        assert is_isabelle_ready("Welcome to Isabelle/HOL (Isabelle2024)")

    def test_returns_true_for_various_versions(self):
        assert is_isabelle_ready("Welcome to Isabelle/Pure")

    def test_returns_false_for_unrelated_string(self):
        assert not is_isabelle_ready("Starting server...")

    def test_returns_false_for_empty_string(self):
        assert not is_isabelle_ready("")


class TestIsSledgehammer:
    def test_is_sledgehammer_done_true(self):
        assert is_sledgehammer_done("Some output\nDone")

    def test_is_sledgehammer_done_false(self):
        assert not is_sledgehammer_done("Sledgehammering...")

    def test_is_sledgehammer_noproof_true(self):
        assert is_sledgehammer_noproof("No proof found after 30s")

    def test_is_sledgehammer_noproof_false(self):
        assert not is_sledgehammer_noproof("Try this: simp (0.1 ms)")


class TestGetCommandFromSledgehammer:
    def test_extracts_command_from_well_formed_response(self):
        content = r"Try this: by simp (0.5 ms)"
        assert get_command_from_sledgehammer(content) == "by simp"

    def test_extracts_command_with_milliseconds(self):
        content = r"Try this: apply (auto simp: foo) (12.3 ms)"
        assert get_command_from_sledgehammer(content) == "apply (auto simp: foo)"

    def test_returns_none_when_no_match(self):
        assert get_command_from_sledgehammer("No proof found") is None

    def test_returns_none_for_empty_string(self):
        assert get_command_from_sledgehammer("") is None


class TestCommandFinishesSubgoal:
    def test_by_finishes(self):
        assert command_finishes_subgoal("by simp")

    def test_done_finishes(self):
        assert command_finishes_subgoal("done")

    def test_qed_finishes(self):
        assert command_finishes_subgoal("qed")

    def test_apply_does_not_finish(self):
        assert not command_finishes_subgoal("apply simp")

    def test_empty_does_not_finish(self):
        assert not command_finishes_subgoal("")
