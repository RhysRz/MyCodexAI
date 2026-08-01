# -*- coding: utf-8 -*-


class CodeGraph:


    def __init__(self):

        self.graph = {}



    def add_node(
        self,
        name,
        node_type="unknown"
    ):

        if name not in self.graph:

            self.graph[name] = {

                "type": node_type,

                "edges": []

            }



    def add_edge(
        self,
        source,
        target,
        relationship=None,
        target_type=None
    ):


        self.add_node(
            source
        )


        if target_type:

            self.add_node(
                target,
                target_type
            )

        else:

            self.add_node(
                target
            )



        edge = target


        if relationship:

            edge = {

                "name": target,

                "relationship": relationship

            }



        if edge not in self.graph[source]["edges"]:

            self.graph[source]["edges"].append(
                edge
            )



    def remove_node(
        self,
        name
    ):


        if name in self.graph:

            del self.graph[name]



        for node in self.graph.values():

            node["edges"] = [

                e

                for e in node["edges"]

                if not (

                    e == name

                    or

                    (
                        isinstance(e, dict)
                        and
                        e.get("name") == name
                    )

                )

            ]



    def get_node(
        self,
        name
    ):

        return self.graph.get(
            name
        )



    def get_dependencies(
        self,
        name
    ):


        if name not in self.graph:

            return []



        result = []



        for edge in self.graph[name]["edges"]:


            if isinstance(
                edge,
                dict
            ):

                result.append(
                    edge["name"]
                )

            else:

                result.append(
                    edge
                )



        return result



    def get_all(
        self
    ):

        return self.graph



    def get_edges(
        self
    ):


        result = []



        for source, data in self.graph.items():


            for edge in data.get(
                "edges",
                []
            ):



                if isinstance(
                    edge,
                    dict
                ):


                    result.append(

                        {

                            "source": source,

                            "target": edge.get(
                                "name"
                            ),

                            "type": edge.get(
                                "relationship",
                                "references"
                            ),

                            "confidence": 0.5

                        }

                    )


                else:


                    result.append(

                        {

                            "source": source,

                            "target": edge,

                            "type": "references",

                            "confidence": 0.5

                        }

                    )



        return result



    def clean_external(
        self
    ):


        remove = []



        for node in self.graph:


            if (

                node.startswith("_")

                or

                node in [

                    "typing",

                    "os",

                    "ast",

                    "json"

                ]

            ):

                remove.append(
                    node
                )



        for node in remove:

            self.remove_node(
                node
            )