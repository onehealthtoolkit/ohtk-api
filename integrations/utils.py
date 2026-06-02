import hashlib
import json

from integrations.constants import is_secret_key_name


def payload_hash(payload):
    if isinstance(payload, bytes):
        serialized = payload
    elif isinstance(payload, str):
        serialized = payload.encode("utf-8")
    else:
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


def secret_safe_summary(value, max_string_length=200, max_list_length=20):
    if isinstance(value, dict):
        if _is_secret_header_mapping(value):
            summary = {}
            for key, child in value.items():
                if str(key).lower() == "value":
                    summary[key] = "[REDACTED]"
                else:
                    summary[key] = secret_safe_summary(
                        child, max_string_length, max_list_length
                    )
            return summary

        summary = {}
        for key, child in value.items():
            key_text = str(key)
            if is_secret_key_name(key_text):
                summary[key_text] = "[REDACTED]"
            else:
                summary[key_text] = secret_safe_summary(
                    child, max_string_length, max_list_length
                )
        return summary

    if isinstance(value, list):
        children = value if max_list_length is None else value[:max_list_length]
        return [
            secret_safe_summary(child, max_string_length, max_list_length)
            for child in children
        ]

    if isinstance(value, str):
        if max_string_length is not None and len(value) > max_string_length:
            return value[:max_string_length] + "..."
        return value

    return value


def _is_secret_header_mapping(value):
    if not isinstance(value, dict):
        return False

    keys = {str(key).lower() for key in value.keys()}
    if "name" not in keys or "value" not in keys:
        return False

    for key, child in value.items():
        if str(key).lower() == "name":
            return is_secret_key_name(child)

    return False
