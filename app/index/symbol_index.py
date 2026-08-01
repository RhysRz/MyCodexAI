import ast
import os



class SymbolIndexer:


    def index_file(
        self,
        filepath
    ):


        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            source = f.read()



        tree = ast.parse(
            source
        )


        symbols = []


        module = os.path.basename(
            filepath
        ).replace(
            ".py",
            ""
        )



        for node in tree.body:

            self._extract_symbols(
                node,
                symbols,
                module=module
            )


        return symbols



    def _extract_symbols(
        self,
        node,
        symbols,
        parent=None,
        module=None
    ):



        if isinstance(
            node,
            ast.ClassDef
        ):


            class_symbol = {

                "type": "class",

                "name": node.name,

                "module": module,

                "line_start": node.lineno,

                "line_end": node.end_lineno,

                "methods": []

            }



            symbols.append(
                class_symbol
            )



            for child in node.body:


                self._extract_symbols(
                    child,
                    symbols,
                    parent=node.name,
                    module=module
                )


                if isinstance(
                    child,
                    ast.FunctionDef
                ):

                    class_symbol["methods"].append(
                        child.name
                    )




        elif isinstance(
            node,
            ast.FunctionDef
        ):


            symbols.append({

                "type":
                    "method"
                    if parent
                    else "function",


                "name":
                    node.name,


                "module":
                    module,


                "parent":
                    parent,


                "line_start":
                    node.lineno,


                "line_end":
                    node.end_lineno,


                "args":
                    [
                        arg.arg
                        for arg in node.args.args
                    ]

            })