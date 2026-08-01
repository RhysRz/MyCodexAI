import ast
import os


from app.graph.code_graph import CodeGraph



class ImportGraphBuilder:


    def __init__(self):

        self.graph = CodeGraph()



    def extract_imports(
        self,
        filepath
    ):

        imports = []


        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            source = f.read()



        tree = ast.parse(
            source
        )


        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.Import
            ):

                for name in node.names:

                    imports.append(
                        name.name
                    )


            elif isinstance(
                node,
                ast.ImportFrom
            ):

                if node.module:

                    imports.append(
                        node.module
                    )


        return imports



    def build_file_graph(
        self,
        filepath
    ):


        filename = os.path.basename(
            filepath
        )


        source_name = filename.replace(
            ".py",
            ""
        )


        imports = self.extract_imports(
            filepath
        )


        for item in imports:

            target = item.split(
                "."
            )[-1]


            self.graph.add_edge(
                source_name,
                target
            )


        return self.graph