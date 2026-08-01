# -*- coding: utf-8 -*-


class UnifiedCodeGraph:
    """A common graph representation for the project, symbol, and call graphs."""

    def __init__(self):
        self.nodes = {}
        self.edges = []

    @property
    def graph(self):
        """Compatibility view for utilities written against ``CodeGraph``."""
        return self.nodes

    def add_node(self, name, data=None):
        data = data or {}

        if name not in self.nodes:
            self.nodes[name] = {
                "id": name,
                "kind": "unknown",
                "file": None,
                "metadata": {},
                "edges": [],
            }

        node = self.nodes[name]
        kind = data.get("kind", data.get("type", "unknown"))

        if kind != "unknown" or node["kind"] == "unknown":
            node["kind"] = kind

        if data.get("file"):
            node["file"] = data["file"]

        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            node["metadata"].update(metadata)

        return node

    def add_edge(self, source, target, relation="references", confidence=0.5):
        self.add_node(source)
        self.add_node(target)

        edge = {
            "source": source,
            "target": target,
            "type": relation,
            "confidence": confidence,
        }

        if edge not in self.edges:
            self.edges.append(edge)

        node_edge = {
            "name": target,
            "relationship": relation,
        }

        if node_edge not in self.nodes[source]["edges"]:
            self.nodes[source]["edges"].append(node_edge)

        return edge

    def remove_node(self, name):
        self.nodes.pop(name, None)
        self.edges = [
            edge
            for edge in self.edges
            if edge["source"] != name and edge["target"] != name
        ]

        for node in self.nodes.values():
            node["edges"] = [
                edge for edge in node["edges"] if edge.get("name") != name
            ]

    def get_node(self, name):
        return self.nodes.get(name)

    def get_all(self):
        return self.nodes

    def get_edges(self):
        return self.edges

    def get_dependencies(self, name):
        return [edge for edge in self.edges if edge["source"] == name]

    def stats(self):
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
        }

    def merge(self, graph):
        """Merge one supported graph, or an iterable of supported graphs."""
        if isinstance(graph, (list, tuple, set)):
            for item in graph:
                self.merge(item)
            return self

        if hasattr(graph, "get_all"):
            nodes = graph.get_all()
        elif isinstance(graph, dict):
            nodes = graph
        else:
            raise TypeError("graph must provide get_all() or be a node dictionary")

        for name, data in nodes.items():
            self.add_node(name, data)

            for edge in data.get("edges", []):
                if isinstance(edge, dict):
                    target = edge.get("name")
                    relation = edge.get("relationship", "references")
                else:
                    target = edge
                    relation = "references"

                if target:
                    self.add_edge(name, target, relation)

        if hasattr(graph, "get_edges"):
            for edge in graph.get_edges():
                self.add_edge(
                    edge["source"],
                    edge["target"],
                    edge.get("type", "references"),
                    edge.get("confidence", 0.5),
                )

        return self

    def get_context(self, name=None):
        if name is None:
            return self.nodes

        return {
            "node": self.get_node(name),
            "dependencies": self.get_dependencies(name),
        }
