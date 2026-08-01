class SymbolRelationshipResolver:


    def __init__(self):

        self.relationships = {}



    def build(
        self,
        symbol_graph,
        call_graph
    ):


        symbols = symbol_graph.get_all()

        calls = call_graph.get_all()



        for name, data in symbols.items():

            if data.get("type") != "class":

                continue


            self.relationships[name] = {

                "type": "class",

                "methods": []

            }



        for name, data in symbols.items():

            if data.get("type") != "method":

                continue


            parent = data.get(
                "parent"
            )


            if parent not in self.relationships:

                continue



            method = {

                "name": name,

                "type": "method",

                "calls": []

            }


            full_name = f"{parent}.{name}"



            if full_name in calls:

                method["calls"] = calls[full_name].get(
                    "edges",
                    []
                )



            self.relationships[parent]["methods"].append(
                method
            )



        return self.relationships



    def get_all(self):

        return self.relationships