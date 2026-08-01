# -*- coding: utf-8 -*-


class SymbolRelationshipResolver:


    def __init__(
        self,
        graph=None
    ):

        self.graph = graph



    def build(
        self
    ):

        relationships = []

        seen = set()


        edges = self.collect_edges()



        for edge in edges:


            source = edge["source"]

            target = edge["target"]

            relation = edge["type"]



            resolved = self.resolve_type(
                relation
            )



            key = (
                source,
                target,
                resolved
            )


            if key in seen:

                continue


            seen.add(
                key
            )


            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": resolved,
                    "type": resolved,
                    "original": relation,
                    "confidence": self.confidence(
                        resolved
                    )
                }
            )



        return relationships


    def resolve(
        self
    ):


        return self.build()





    def collect_edges(
        self
    ):


        result = []



        if self.graph is None:

            return result



        # UnifiedCodeGraph

        if hasattr(
            self.graph,
            "get_all"
        ):


            nodes = self.graph.get_all()



        # CodeGraph

        elif hasattr(
            self.graph,
            "graph"
        ):


            nodes = self.graph.graph



        # dict

        elif isinstance(
            self.graph,
            dict
        ):


            nodes = self.graph



        else:

            nodes = {}



        for source, data in nodes.items():


            edges = data.get(
                "edges",
                []
            )



            for edge in edges:


                if isinstance(
                    edge,
                    dict
                ):


                    target = edge.get(
                        "name"
                    )

                    relation = edge.get(
                        "relationship",
                        "references"
                    )


                else:


                    target = edge

                    relation = "references"



                if target:


                    result.append(

                        {

                            "source": source,

                            "target": target,

                            "type": relation

                        }

                    )



        return result





    def resolve_type(
        self,
        relation
    ):


        return {

            "uses": "depends_on",

            "calls": "invokes",

            "inherits": "extends",

            "contains": "contains",

            "references": "references"

        }.get(
            relation,
            "references"
        )





    def confidence(
        self,
        relation
    ):


        return {

            "depends_on": 0.9,

            "invokes": 0.85,

            "extends": 0.95,

            "contains": 0.95,

            "references": 0.5

        }.get(
            relation,
            0.5
        )
