# -*- coding: utf-8 -*-


class RelationshipCleaner:


    def __init__(self):

        self.seen = set()



    def clean(self, relationships):

        cleaned = []

        self.seen.clear()



        for item in relationships:


            source = item.get(
                "source"
            )

            target = item.get(
                "target"
            )

            relation = item.get(
                "type",
                "references"
            )


            if not source or not target:

                continue



            key = (
                source,
                target,
                relation
            )


            if key in self.seen:

                continue



            self.seen.add(
                key
            )



            cleaned.append(
                {
                    "source": source,
                    "target": target,
                    "type": relation,
                    "confidence": self.get_confidence(
                        relation
                    )
                }
            )



        return cleaned




    def get_confidence(
        self,
        relation
    ):


        if relation == "contains":

            return 0.9



        if relation == "uses":

            return 0.9



        if relation == "inherits":

            return 0.9



        if relation == "calls":

            return 0.7



        return 0.5