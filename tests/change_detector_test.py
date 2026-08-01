import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.index.change_detector import ChangeDetector


detector = ChangeDetector()


old = {
    "path": "test.py",
    "modified": 100
}


new = {
    "path": "test.py",
    "modified": 200
}


result = detector.is_changed(
    old,
    new
)


print(result)