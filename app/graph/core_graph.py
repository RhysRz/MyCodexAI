# -*- coding: utf-8 -*-


class CoreGraph:


    def __init__(self):

        self.nodes = {}

        self.edges = []



    def add_node(
        self,
        name,
        kind="unknown",
        file=None,
        metadata=None
    ):


        if name not in self.nodes:


            self.nodes[name] = {

                "id": name,

                "kind": kind,

                "file": file,

                "metadata": metadata or {}

            }


        else:


            if kind != "unknown":

                self.nodes[name]["kind"] = kind



            if file:

                self.nodes[name]["file"] = file





    def add_edge(
        self,
        source,
        target,
        relation,
        confidence=0.5
    ):


        self.add_node(source)

        self.add_node(target)



        edge = {

            "source": source,

            "target": target,

            "type": relation,

            "confidence": confidence

        }


        if edge not in self.edges:

            self.edges.append(edge)




    def get_node(
        self,
        name
    ):

        return self.nodes.get(name)




    def get_all(
        self
    ):

        return self.nodes




    def get_edges(
        self
    ):

        return self.edges


    def remove_node(
        self,
        name
    ):


        self.nodes.pop(
            name,
            None
        )


        self.edges = [

            edge

            for edge in self.edges

            if edge["source"] != name
            and edge["target"] != name

        ]




    def get_dependencies(
        self,
        name
    ):


        result = []


        for edge in self.edges:


            if edge["source"] == name:

                result.append(edge)



        return result




    def stats(
        self
    ):


        return {

            "nodes": len(self.nodes),

            "edges": len(self.edges)

        }
