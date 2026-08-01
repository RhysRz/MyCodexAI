class SmartCleaner:


    IGNORE = {

        "os",
        "sys",
        "ast",
        "json",
        "typing",
        "time",
        "pathlib",
        "dataclasses",

        "open",
        "print",
        "str",
        "len",
        "any",
        "isinstance",
        "Path"

    }



    def clean(self, graph):


        remove = []



        for node, data in graph.graph.items():


            #
            # remove python builtin
            #

            if node in self.IGNORE:

                remove.append(node)

                continue



            #
            # remove lowercase modules
            #

            if (
                data["type"] == "module"
                and node.islower()
            ):

                remove.append(node)



        for node in remove:

            graph.remove_node(node)



        return graph