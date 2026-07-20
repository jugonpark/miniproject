import pytest
from pydantic import ValidationError

from moodwave_mcp.models import MusicRequest


def test_music_request_accepts_free_text_without_conditions():
    request = MusicRequest(conditions=[], free_text="late-night coding")

    assert request.conditions == []
    assert request.free_text == "late-night coding"


@pytest.mark.parametrize("free_text", [None, "", "   "])
def test_music_request_rejects_when_conditions_and_free_text_are_empty(free_text):
    with pytest.raises(ValidationError):
        MusicRequest(conditions=[], free_text=free_text)
