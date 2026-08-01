class CallGraphFilter:


    IGNORE_NAMES = {

        "print",
        "open",
        "len",
        "str",
        "int",
        "float",
        "list",
        "dict",
        "set",
        "isinstance",

        "append",
        "extend",
        "get",
        "items",
        "keys",
        "values",

        "lower",
        "split",
        "strip",
        "encode",
        "decode",

        "walk",
        "parse",
        "loads",
        "dump",
        "load"

    }



    def clean(
        self,
        graph
    ):


        remove = []


        if hasattr(
            graph,
            "get_all"
        ):

            nodes = graph.get_all()

        else:

            nodes = graph.graph


        for node in nodes:


            last = node.split(".")[-1]


            if last in self.IGNORE_NAMES:

                remove.append(
                    node
                )


            elif node.startswith(
                "self."
            ):

                remove.append(
                    node
                )



        for node in remove:

            if hasattr(
                graph,
                "remove_node"
            ):

                graph.remove_node(
                    node
                )

            else:

                del nodes[node]



        return graph
