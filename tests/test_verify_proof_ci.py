"""HEAD policy regressions; cryptographic verification is deliberately mocked."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class TestStrictHead(unittest.TestCase):
    COMMIT = "abcdef0123456789abcdef0123456789abcdef0123"
    OTHER_COMMIT = "123456789abcdef0123456789abcdef0123456789a"

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.proof = Path(directory.name) / "proof.json"
        self.data = {"commit": self.COMMIT}
        self.proof.write_text(json.dumps(self.data), encoding="utf-8")

        # Load a fresh verifier with a local stub, preventing its import-time
        # upstream download and avoiding any real cryptographic dependency.
        self.agent = types.ModuleType("technocore_agent")
        self.agent.verify_contribution_proof = Mock(return_value=None)
        source = Path(__file__).resolve().parents[1] / "scripts" / "verify_proof_ci.py"
        spec = importlib.util.spec_from_file_location("verifier_under_test", source)
        self.verifier = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"technocore_agent": self.agent}):
            with patch.object(sys, "path", sys.path.copy()):
                spec.loader.exec_module(self.verifier)

        self.output = io.StringIO()
        self.enter_output = contextlib.redirect_stdout(self.output)
        self.enter_output.__enter__()
        self.addCleanup(self.enter_output.__exit__, None, None, None)

    def test_strict_head_accepts_matching_commit(self):
        for head in (self.COMMIT, self.COMMIT.upper()):
            with self.subTest(head=head):
                with patch.object(self.verifier, "get_git_head_commit", return_value=head):
                    self.assertTrue(self.verifier.verify_proof_file(self.proof, strict_head=True))

    def test_strict_head_rejects_mismatch(self):
        with patch.object(self.verifier, "get_git_head_commit", return_value=self.OTHER_COMMIT):
            self.assertFalse(self.verifier.verify_proof_file(self.proof, strict_head=True))
        self.agent.verify_contribution_proof.assert_called_once_with(self.data)
        self.assertNotIn("checks PASSED", self.output.getvalue())

    def test_strict_head_rejects_unavailable_head(self):
        for head in (None, ""):
            with self.subTest(head=head):
                with patch.object(self.verifier, "get_git_head_commit", return_value=head):
                    self.assertFalse(self.verifier.verify_proof_file(self.proof, strict_head=True))
        self.assertNotIn("checks PASSED", self.output.getvalue())

    def test_default_mode_does_not_require_head_alignment(self):
        for head in (self.OTHER_COMMIT, None, ""):
            with self.subTest(head=head):
                with patch.object(self.verifier, "get_git_head_commit", return_value=head) as get_head:
                    self.assertTrue(self.verifier.verify_proof_file(self.proof))
                    get_head.assert_not_called()

    def test_signature_failure_still_fails_in_both_modes(self):
        self.agent.verify_contribution_proof.side_effect = ValueError("invalid proof")
        for strict in (False, True):
            with self.subTest(strict=strict):
                with patch.object(self.verifier, "get_git_head_commit") as get_head:
                    self.assertFalse(self.verifier.verify_proof_file(self.proof, strict_head=strict))
                    get_head.assert_not_called()

    def test_cli_exit_status(self):
        for strict, head, expected in (
            (True, self.COMMIT, 0),
            (True, self.OTHER_COMMIT, 1),
            (True, None, 1),
            (False, None, 0),
        ):
            with self.subTest(strict=strict, head=head):
                argv = ["verify_proof_ci.py", str(self.proof)]
                if strict:
                    argv.append("--strict-head")
                with patch.object(sys, "argv", argv):
                    with patch.object(self.verifier, "get_git_head_commit", return_value=head):
                        with self.assertRaises(SystemExit) as raised:
                            self.verifier.main()
                self.assertEqual(raised.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
