# -*- coding: utf-8 -*-


class RelationshipAnalyzer:


    def __init__(self):

        self.results = []



    def analyze(
        self,
        relationships
    ):


        self.results = []


        for item in relationships:


            relation = item.get(
                "type"
            )


            target = item.get(
                "target"
            )


            new_relation = self.classify(
                relation,
                target
            )


            self.results.append(
                {
                    "source": item.get("source"),
                    "target": target,
                    "relationship": new_relation,
                    "original": relation,
                    "confidence": self.confidence(
                        new_relation
                    )
                }
            )


        return self.results



    def classify(
        self,
        relation,
        target
    ):


        if relation == "contains":

            return "contains"



        if relation == "inherits":

            return "inherits"



        if relation == "calls":

            if target.startswith(
                "self."
            ):

                return "uses_state"


            return "calls"



        if relation == "uses":

            return "depends_on"



        return "references"



    def confidence(
        self,
        relation
    ):


        scores = {

            "contains": 0.95,

            "inherits": 0.95,

            "depends_on": 0.9,

            "uses_state": 0.85,

            "calls": 0.8,

            "references": 0.5

        }


        return scores.get(
            relation,
            0.5
        )