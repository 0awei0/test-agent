import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def pytest_collection_modifyitems(items):
    for item in items:
        if "smoke" in item.nodeid:
            item.add_marker(pytest.mark.smoke)
        for marker in ["P0", "P1", "P2"]:
            if marker in item.nodeid:
                item.add_marker(getattr(pytest.mark, marker))


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".yaml" and file_path.name.startswith("test_"):
        return YamlFile.from_parent(parent, path=file_path)


class YamlFile(pytest.File):
    def collect(self):
        from core.yaml_parser import load_yaml
        from config.settings import settings

        data = load_yaml(str(self.fspath))
        suite_name = data.get("suite", "unknown")
        base_url = data.get("base_url", settings.BASE_URL)
        cases = data.get("cases", [])

        for i, case in enumerate(cases):
            yield YamlItem.from_parent(
                self,
                name=case.get("name", f"case_{i}"),
                calldata=case,
                suite_name=suite_name,
                base_url=base_url,
            )


class YamlItem(pytest.Item):
    def __init__(self, name, parent, calldata, suite_name, base_url):
        super().__init__(name, parent)
        self.calldata = calldata
        self.suite_name = suite_name
        self.base_url = base_url

    def runtest(self):
        from core.yaml_runner import run_yaml_test_case
        case = self.calldata
        case["base_url"] = self.base_url
        run_yaml_test_case(case)

    def repr_failure(self, excinfo):
        return f"[{self.suite_name}] {self.name} FAILED: {excinfo.value}"

    def reportinfo(self):
        return self.fspath, 0, f"[{self.suite_name}] {self.name}"
