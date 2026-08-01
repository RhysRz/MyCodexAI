# -*- coding: utf-8 -*-


from collections import deque



class ImpactAnalyzer:


    def __init__(
        self,
        graph
    ):

        self.graph = graph



    def find_impact(
        self,
        target,
        depth=3
    ):


        results = []

        visited = set()


        queue = deque()


        queue.append(
            (
                target,
                0
            )
        )


        visited.add(
            target
        )



        while queue:


            current, level = queue.popleft()



            if level >= depth:

                continue



            for source, data in self.graph.get_all().items():


                edges = data.get(
                    "edges",
                    []
                )


                for edge in edges:


                    if isinstance(
                        edge,
                        dict
                    ):

                        name = edge.get(
                            "name"
                        )

                    else:

                        name = edge



                    if name == current:


                        item = {
                            "source": source,
                            "target": current,
                            "depth": level + 1
                        }


                        results.append(
                            item
                        )



                        if source not in visited:


                            visited.add(
                                source
                            )


                            queue.append(
                                (
                                    source,
                                    level + 1
                                )
                            )



        return results