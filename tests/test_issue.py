import importlib.metadata as m

import pytest

from generate_ledger import __version__

project_name = "legleux-generate_ledger"


@pytest.fixture()
def resource():
    print("setup")
    yield "resource"
    print("teardown")


class TestIssue:
    def test_that_depends_on_resource(self, resource):
        print(f"testing {resource}")
        assert isinstance(__version__, str)

    def test_version(self):
        v = m.version(project_name)
        assert isinstance(v, str)
        assert v.count(".") >= 1
