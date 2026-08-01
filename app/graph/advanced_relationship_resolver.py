class SymbolRelationshipResolver:

    def __init__(self, graph=None):
        self.graph = graph
        self.relationships = []


    def build(self):

        if not self.graph:
            return []

        self.relationships = []

        nodes = self.graph.get_all()


        for source, data in nodes.items():

            edges = data.get("edges", [])


            for target in edges:

                relation = self._detect_relation(
                    source,
                    target,
                    data
                )

                self.relationships.append(
                    {
                        "source": source,
                        "target": target,
                        "type": relation,
                        "confidence": 0.8
                    }
                )


        return self.relationships



    def resolve(self):

        return self.build()



    def get_all(self):

        return self.relationships



    def _detect_relation(
        self,
        source,
        target,
        data
    ):

        source_type = data.get(
            "type",
            ""
        )


        if source_type == "class":

            if target.startswith("_"):
                return "contains"


            if target[0:1].isupper():
                return "uses"


            return "calls"


        return "references"