import json


class JsonParser:


    @staticmethod
    def parse(text):

        try:

            data = json.loads(
                text
            )


            if "tool" not in data:

                data["tool"] = None


            if "arguments" not in data:

                data["arguments"] = {}


            if isinstance(
                data["arguments"],
                str
            ):

                data["arguments"] = {}


            return data



        except Exception:


            return {
                "tool": None,
                "arguments": {}
            }