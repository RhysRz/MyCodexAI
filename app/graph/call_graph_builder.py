# -*- coding: utf-8 -*-

import ast
import os

from app.graph.core_graph import CoreGraph



class CallGraphBuilder(ast.NodeVisitor):


    def __init__(self):

        self.graph = CoreGraph()

        self.current_symbol = None

        self.current_file = None



    # ==========================
    # BUILD
    # ==========================

    def build(
        self,
        path
    ):


        self.graph = CoreGraph()


        for root, _, files in os.walk(path):


            for filename in files:


                if filename.endswith(".py"):


                    filepath = os.path.join(
                        root,
                        filename
                    )


                    self.build_file(
                        filepath
                    )



        return self.graph


    def build_file_graph(
        self,
        filepath
    ):


        self.graph = CoreGraph()

        self.build_file(
            filepath
        )

        return self.graph





    # ==========================
    # FILE
    # ==========================

    def build_file(
        self,
        filepath
    ):


        self.current_file = filepath

        self.current_symbol = None



        try:

            with open(
                filepath,
                "r",
                encoding="utf-8"
            ) as f:

                source = f.read()



            tree = ast.parse(
                source
            )


            self.visit(
                tree
            )



        except Exception as e:


            print(
                "Call parse error:",
                filepath,
                e
            )





    # ==========================
    # CLASS
    # ==========================

    def visit_ClassDef(
        self,
        node
    ):


        old = self.current_symbol

        self.current_symbol = node.name


        self.graph.add_node(

            node.name,

            kind="class",

            file=self.current_file

        )



        self.generic_visit(
            node
        )


        self.current_symbol = old





    # ==========================
    # FUNCTION
    # ==========================

    def visit_FunctionDef(
        self,
        node
    ):


        if self.current_symbol:


            symbol = (

                self.current_symbol

                + "."

                + node.name

            )


        else:


            symbol = node.name



        self.graph.add_node(

            symbol,

            kind="function",

            file=self.current_file

        )



        old = self.current_symbol


        self.current_symbol = symbol



        self.generic_visit(
            node
        )


        self.current_symbol = old





    # ==========================
    # CALL
    # ==========================

    def visit_Call(
        self,
        node
    ):


        target = self.get_call_name(
            node
        )


        if target and self.current_symbol:


            self.graph.add_edge(

                self.current_symbol,

                target,

                "calls",

                0.7

            )



        self.generic_visit(
            node
        )





    # ==========================
    # NAME RESOLVER
    # ==========================

    def get_call_name(
        self,
        node
    ):


        if isinstance(
            node.func,
            ast.Name
        ):

            return node.func.id



        if isinstance(
            node.func,
            ast.Attribute
        ):


            parts = []

            current = node.func



            while isinstance(
                current,
                ast.Attribute
            ):


                parts.append(
                    current.attr
                )


                current = current.value



            if isinstance(
                current,
                ast.Name
            ):


                parts.append(
                    current.id
                )



            return ".".join(
                reversed(parts)
            )



        return None
