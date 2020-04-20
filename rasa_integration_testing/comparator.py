from string import Template
from typing import Any, Dict, List

from .common import lazy_property
from .configuration import configure
from .identifier import Identifier

IGNORED_KEYS_SEPARATOR = ","
INDEX_KEY_PREFIX = "_"


class JsonPath(Identifier):
    @lazy_property
    def join_without_index_elements(self) -> str:
        return self.ELEMENT_SEPARATOR.join(
            element
            for element in self.elements
            if not element.startswith(INDEX_KEY_PREFIX)
        )

    def __repr__(self) -> str:
        return self.join_elements


class JsonDiff:
    def __init__(
        self, missing_entries: Dict[JsonPath, Any], extra_entries: Dict[JsonPath, Any]
    ):
        self.missing_entries = missing_entries
        self.extra_entries = extra_entries

    @property
    def identical(self) -> bool:
        return len(self.missing_entries) == 0 and len(self.extra_entries) == 0

    def __repr__(self) -> str:
        return (
            f"<JsonDiff, Missing Entries: {self.missing_entries}, "
            f"'Extra Entries: {self.extra_entries}'>"
        )


@configure("runner.ignored_result_keys")
class JsonDataComparator:
    def __init__(self, ignored_result_keys: str):
        self._ignored_result_keys: List[str] = ignored_result_keys.split(
            IGNORED_KEYS_SEPARATOR
        ) if ignored_result_keys else []

    def flatten_json(
        self, nodes: dict, json_path: JsonPath = JsonPath(), variables={}
    ) -> Dict[JsonPath, Any]:
        resolved_json_data: Dict[JsonPath, Any] = {}

        for key, value in nodes.items():
            node_id = JsonPath(*json_path, key)
            if self._check_if_ignored(node_id):
                continue

            if isinstance(value, dict):
                resolved_json_data.update(self.flatten_json(value, node_id, variables))
            elif isinstance(value, list):
                for index, entry in enumerate(value, 1):
                    entry_id = JsonPath(*node_id, f"{INDEX_KEY_PREFIX}{index}")
                    resolved_json_data.update(
                        self.flatten_json(entry, entry_id, variables)
                    )
            elif isinstance(value, str):
                resolved_json_data[node_id] = Template(value).safe_substitute(variables)
            else:
                resolved_json_data[node_id] = value

        return resolved_json_data

    def compare(
        self, expected_json_data: dict, actual_json_data: dict, variables: dict = {}
    ) -> JsonDiff:
        expected: Dict[JsonPath, Any] = self.flatten_json(
            expected_json_data, variables=variables
        )
        actual: Dict[JsonPath, Any] = self.flatten_json(
            actual_json_data, variables=variables
        )

        missing_entries: Dict[JsonPath, Any] = _get_diff(expected, actual)
        extra_entries: Dict[JsonPath, Any] = _get_diff(actual, expected)
        return JsonDiff(missing_entries, extra_entries)

    def _check_if_ignored(self, json_path: JsonPath) -> bool:
        for ignored_key in self._ignored_result_keys:
            if json_path.join_without_index_elements.endswith(ignored_key):
                return True

        return False


def _get_diff(expected_dict: dict, actual_dict: dict) -> dict:
    diff: Dict[JsonPath, Any] = {}

    for key, value in expected_dict.items():
        if key not in actual_dict:
            diff[key] = value
        elif expected_dict[key] != actual_dict[key]:
            diff[key] = value

    return diff
