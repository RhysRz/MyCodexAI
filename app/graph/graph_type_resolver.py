class GraphTypeResolver:


    def resolve(
        self,
        graph
    ):


        if hasattr(
            graph,
            "get_all"
        ):

            nodes = graph.get_all()

        else:

            nodes = graph.graph


        for node, data in nodes.items():


            kind = data.get(
                "kind",
                data.get(
                    "type",
                    "unknown"
                )
            )


            if kind != "unknown":

                continue



            #
            # Class
            #

            if (
                node[0].isupper()
                and "." not in node
            ):

                kind = "class"



            #
            # Call
            #

            elif "." in node:

                kind = "call"



            #
            # Method
            #

            elif node in {

                "chat",
                "build",
                "execute",
                "handle",
                "plan",
                "search",
                "read",
                "write"

            }:

                kind = "method"



            else:

                kind = "unknown"


            if "kind" in data:

                data["kind"] = kind

            else:

                data["type"] = kind



        return graph
