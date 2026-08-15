import pytest

from src.agent.tools import calculator, document_search


def test_calculator():
    assert calculator("(17.5 * 8) + 2")["result"] == 142.0

def test_calculator_rejects_code():
    with pytest.raises(ValueError):
        calculator("__import__('os').system('echo nope')")

def test_document_search():
    result = document_search("observability metrics ml systems")
    assert result["results"]
    assert result["results"][0]["document"] == "ml_systems.txt"
