# -*- coding: utf-8 -*-


class EdgeFilter:


    def __init__(self):

        self.ignore = {

            "print",
            "len",
            "str",
            "list",
            "dict",
            "set",
            "tuple",
            "decode",
            "encode",
            "isinstance"

        }



    def clean(
        self,
        graph
    ):


        edges = graph.get_edges()


        filtered = []


        for edge in edges:


            target = edge["target"]


            last = target.split(".")[-1]


            if last in self.ignore:

                continue



            filtered.append(
                edge
            )


        graph.edges = filtered


        return graph