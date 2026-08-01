import json
import os


class IndexStore:

    def __init__(self, path="app/index/code_index.json"):
        self.path = path


    def save(self, data):

        folder = os.path.dirname(self.path)

        if not os.path.exists(folder):
            os.makedirs(folder)

        with open(
            self.path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )


    def load(self):

        if not os.path.exists(self.path):
            return None


        with open(
            self.path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)