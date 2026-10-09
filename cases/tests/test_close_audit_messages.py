"""Audit formatting/configuration tests; no database is needed."""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from cases.services.case_close import (
    CLOSE_AUDIT_MESSAGES_KEY,
    DEFAULT_CLOSE_AUDIT_MESSAGES,
    build_close_audit_body,
    close_case,
    complete_system_closed_case,
    update_finished_case_close_data,
)

DEFINITION = {
    "version": 1,
    "sections": [{"questions": [
        {"label": "ຜົນການວິໄຈ", "fields": [{"name": "lab_custom", "type": "text"}]},
        {"label": "question fallback", "fields": [
            {"name": "count_custom", "label": "ຈຳນວນ", "type": "integer", "min": 0}
        ]},
    ]}],
}
PAYLOAD = {"lab_custom": " LAB-001: ທົດສອບ <&> ", "count_custom": 0}


class CloseAuditMessagesTests(SimpleTestCase):
    def setUp(self):
        self.config = patch("accounts.models.Configuration.get", return_value=None).start()
        self.addCleanup(patch.stopall)

    def test_missing_configuration_preserves_english(self):
        body = build_close_audit_body(source="officer", payload={"stamp_out": 0})
        self.assertEqual(body, "[Case close] Close case\nstamp out: 0")
        self.config.assert_called_once_with(CLOSE_AUDIT_MESSAGES_KEY)

    def test_each_action_uses_bundle(self):
        messages = {key: "ລາວ " + key for key in DEFAULT_CLOSE_AUDIT_MESSAGES}
        self.config.return_value = json.dumps(messages)
        for kwargs, key in [
            ({"source": "officer"}, "close_case"),
            ({"source": "officer", "outcome": "false_positive"}, "false_positive"),
            ({"source": "system"}, "automatic_close"),
            ({"source": "system", "action": "complete_after_auto_close"}, "complete_after_auto_close"),
            ({"source": "officer", "action": "superuser_edit"}, "superuser_edit"),
        ]:
            with self.subTest(key=key):
                body = build_close_audit_body(**kwargs)
                expected = messages[key]
                if key == "automatic_close":
                    expected += "\n" + messages["no_close_data"]
                self.assertEqual(body, expected)
        self.assertEqual(self.config.call_count, 5)

    def test_partial_invalid_entries_and_unknown_keys(self):
        self.config.return_value = json.dumps({"close_case": "ປິດເຄສ", "reason": [], "no_close_data": " ", "unknown": "x"})
        self.assertEqual(build_close_audit_body(source="officer"), "ປິດເຄສ")
        body = build_close_audit_body(source="officer", outcome="false_positive", payload={"reason": "user"})
        self.assertEqual(body, "[Case close] False positive\nreason: user")
        self.assertTrue(build_close_audit_body(source="system").endswith("No close data recorded."))

    def test_malformed_json_and_non_object_fall_back_and_log(self):
        for raw in ("{broken", "[]", "null", "42"):
            with self.subTest(raw=raw):
                self.config.return_value = raw
                with self.assertLogs("cases.services.case_close", level="WARNING") as logs:
                    self.assertEqual(build_close_audit_body(source="officer"), "[Case close] Close case")
                self.assertIn(CLOSE_AUDIT_MESSAGES_KEY, logs.output[0])
                self.assertNotIn(raw, logs.output[0])

    def test_definition_labels_values_zero_and_unknown_field(self):
        payload = dict(PAYLOAD, another_field="unchanged", close_outcome="close_case", empty="", missing=None)
        original = dict(payload)
        body = build_close_audit_body(source="officer", definition=DEFINITION, payload=payload)
        self.assertEqual(body, "[Case close] Close case\nຜົນການວິໄຈ:  LAB-001: ທົດສອບ <&> \nຈຳນວນ: 0\nanother field: unchanged")
        self.assertEqual(payload, original)

    def test_thin_definition_and_first_duplicate_label(self):
        definition = {"fields": [{"id": "x", "label": "First"}, {"id": "x", "label": "Second"}, {"id": "blank_label", "label": " "}]}
        body = build_close_audit_body(source="officer", definition=definition, payload={"x": 0, "blank_label": 2})
        self.assertEqual(body, "[Case close] Close case\nFirst: 0\nblank label: 2")

    def test_false_positive_reason_uses_config_not_close_form(self):
        self.config.return_value = json.dumps({"reason": "ເຫດຜົນ"})
        definition = {"fields": [{"id": "reason", "label": "unrelated close field"}]}
        for action in ("close", "superuser_edit"):
            body = build_close_audit_body(source="officer", outcome="false_positive", action=action,
                                         definition=definition, payload={"reason": "unchanged"})
            self.assertTrue(body.endswith("ເຫດຜົນ: unchanged"))

    def test_configuration_is_read_again_without_cross_tenant_cache(self):
        self.config.side_effect = [json.dumps({"close_case": "Tenant A"}), None]
        self.assertEqual(build_close_audit_body(source="officer"), "Tenant A")
        self.assertEqual(build_close_audit_body(source="officer"), "[Case close] Close case")

    def test_all_service_calls_supply_definition_to_new_audit(self):
        # Transaction wrapper alone is bypassed here. Local DB acceptance covers persistence.
        for action in ("close", "complete", "edit"):
            with self.subTest(action=action):
                case = SimpleNamespace(stopped_at=None if action == "close" else timezone.now(),
                                       is_finished=action != "close", close_source="system", close_outcome="",
                                       close_payload={}, status_label="Open", save=Mock())
                actor = SimpleNamespace(is_superuser=True)
                with patch("cases.services.case_close.get_close_definition_for_case", return_value=DEFINITION), patch(
                    "cases.services.case_close.post_case_audit_comment"
                ) as post:
                    if action == "close":
                        close_case.__wrapped__(case, source="officer", actor=actor, payload=PAYLOAD)
                    elif action == "complete":
                        complete_system_closed_case.__wrapped__(case, actor=actor, payload=PAYLOAD)
                    else:
                        update_finished_case_close_data.__wrapped__(case, actor=actor, payload=PAYLOAD)
                post.assert_called_once()
                self.assertIn("ຜົນການວິໄຈ: LAB-001: ທົດສອບ <&>", post.call_args.kwargs["body"])
                self.assertIn("ຈຳນວນ: 0", post.call_args.kwargs["body"])
                self.assertIs(post.call_args.kwargs["actor"], actor)
