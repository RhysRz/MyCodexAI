# -*- coding: utf-8 -*-


class CallGraphCleaner:


    def __init__(self):

        self.ignore = {
            "print",
            "open",
            "str",
            "list",
            "dict",
            "any",
            "len",
            "isinstance"
        }



    def clean(
        self,
        graph
    ):


        if not hasattr(
            graph,
            "get_all"
        ):

            return graph



        data = graph.get_all()



        remove = []



        for node, value in list(data.items()):


            if node in self.ignore:

                remove.append(
                    node
                )

                continue



            # ลบเฉพาะ node เปล่า
            # ห้ามลบ class / method relationships

            if (
                value.get("type") == "call"
                and
                not value.get("edges")
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

            elif node in data:

                del data[node]



        return graph
