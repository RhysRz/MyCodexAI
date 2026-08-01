from pathlib import Path


def test_image_runtime_dependencies_include_pillow_for_hugging_face_results():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").casefold()
    assert "huggingface_hub" in requirements
    assert "pillow" in requirements
