# -*- coding: utf-8 -*-


class EdgeNormalizer:


    priority = {

        "inherits": 5,

        "uses": 5,

        "calls": 4,

        "contains": 3,

        "references": 1

    }



    ignore = {

        "print",
        "decode",
        "encode",
        "get",
        "append",
        "extend",
        "isinstance",
        "open",
        "str",
        "list",
        "dict"

    }



    def normalize(
        self,
        graph
    ):


        merged = {}



        for edge in graph.get_edges():


            source = edge.get(
                "source"
            )


            target = self.normalize_target(
                edge.get(
                    "target"
                )
            )



            if not source or not target:

                continue



            if self.should_ignore(
                target
            ):

                continue



            parent = self.get_parent(
                target
            )



            # ป้องกัน self dependency

            if source == parent:

                continue



            key = (

                source,

                parent

            )



            new_edge = {

                "source": source,

                "target": parent,

                "type": edge.get(
                    "type",
                    "references"
                ),

                "confidence": edge.get(
                    "confidence",
                    0.5
                )

            }



            if key not in merged:


                merged[key] = new_edge



            else:


                old_edge = merged[key]



                if self.priority.get(
                    new_edge["type"],
                    0
                ) > self.priority.get(
                    old_edge["type"],
                    0
                ):


                    merged[key] = new_edge



                elif self.priority.get(
                    new_edge["type"],
                    0
                ) == self.priority.get(
                    old_edge["type"],
                    0
                ):


                    # ถ้า relation เท่ากัน
                    # เลือก confidence สูงกว่า

                    if new_edge["confidence"] > old_edge["confidence"]:

                        merged[key] = new_edge




        graph.edges = list(
            merged.values()
        )


        return graph





    def normalize_target(
        self,
        target
    ):


        if not target:

            return None



        # self.xxx.method

        if target.startswith(
            "self."
        ):


            parts = target.split(".")



            if len(parts) > 1:

                return parts[1]



        return target





    def get_parent(
        self,
        target
    ):


        if "." in target:


            return target.split(
                "."
            )[0]



        return target





    def should_ignore(
        self,
        target
    ):


        last = target.split(
            "."
        )[-1]


        return last in self.ignore