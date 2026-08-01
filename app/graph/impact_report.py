# -*- coding: utf-8 -*-


class ImpactReport:


    def __init__(
        self,
        graph
    ):

        self.graph = graph



    def generate(
        self,
        target,
        impacts
    ):


        report = {

            "target": target,

            "impact": [],

            "risk": self.calculate_risk(
                impacts
            )

        }



        for item in impacts:


            source = item.get(
                "source"
            )


            node = self.graph.get_all().get(
                source,
                {}
            )


            report["impact"].append(
                {

                    "symbol": source,

                    "file": node.get(
                        "file",
                        "unknown"
                    ),

                    "reason": self.detect_reason(
                        source,
                        target
                    ),

                    "depth": item.get(
                        "depth",
                        0
                    )

                }
            )



        return report



    def detect_reason(
        self,
        source,
        target
    ):


        node = self.graph.get_all().get(
            source,
            {}
        )


        for edge in node.get(
            "edges",
            []
        ):


            if isinstance(
                edge,
                dict
            ):

                name = edge.get(
                    "name"
                )

                relation = edge.get(
                    "relationship",
                    "references"
                )


                if name == target:

                    return relation



        return "references"



    def calculate_risk(
        self,
        impacts
    ):


        count = len(
            impacts
        )


        if count >= 10:

            return "high"


        if count >= 3:

            return "medium"


        return "low"