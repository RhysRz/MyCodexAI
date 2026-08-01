from app.workspace.scanner import WorkspaceScanner
from app.index.symbol_index import SymbolIndexer
from app.graph.import_graph_builder import ImportGraphBuilder
from app.graph.code_graph import CodeGraph
from app.graph.symbol_resolver import SymbolResolver



class ProjectGraphBuilder:


    def __init__(self):

        self.scanner = WorkspaceScanner()

        self.symbol_indexer = SymbolIndexer()

        self.import_builder = ImportGraphBuilder()

        self.resolver = SymbolResolver()

        self.graph = CodeGraph()



    def build(
        self,
        root
    ):


        self.resolver = SymbolResolver()

        self.graph = CodeGraph()


        files = self.scanner.scan(
            root
        )


        all_symbols = {}



        #
        # Phase 1
        # Collect Symbols
        #

        for filepath in files:


            if not filepath.endswith(
                ".py"
            ):

                continue



            symbols = self.symbol_indexer.index_file(
                filepath
            )


            self.resolver.add_symbol(
                filepath,
                symbols
            )


            all_symbols[
                filepath
            ] = symbols




        #
        # Phase 2
        # Build Graph
        #

        for filepath, symbols in all_symbols.items():


            classes = []


            for symbol in symbols:


                if symbol["type"] == "class":


                    classes.append(
                        symbol["name"]
                    )


                    self.graph.add_node(
                        symbol["name"],
                        "class"
                    )



            imports = self.import_builder.extract_imports(
                filepath
            )


            dependencies = []


            for item in imports:


                name = item.split(
                    "."
                )[-1]


                dependencies.append(
                    self.resolver.resolve(
                        name
                    )
                )



            for cls in classes:


                for dep in dependencies:


                    self.graph.add_edge(
                        cls,
                        dep
                    )



        return self.graph
