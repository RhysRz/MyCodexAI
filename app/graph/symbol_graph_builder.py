# -*- coding: utf-8 -*-

import ast
import os

from app.graph.core_graph import CoreGraph



class SymbolGraphBuilder(ast.NodeVisitor):


    def __init__(self):

        self.graph = CoreGraph()

        self.current_class = None

        self.current_file = None



    # ==========================
    # BUILD PROJECT
    # ==========================

    def build(
        self,
        path
    ):


        for root, _, files in os.walk(path):

            for filename in files:


                if filename.endswith(".py"):


                    filepath = os.path.join(
                        root,
                        filename
                    )


                    self.build_file_graph(
                        filepath
                    )



        return self.graph





    # ==========================
    # BUILD FILE
    # ==========================

    def build_file_graph(
        self,
        filepath
    ):


        self.current_file = filepath

        self.current_class = None



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
                "Symbol parse error:",
                filepath,
                e
            )


        return self.graph





    # ==========================
    # CLASS
    # ==========================

    def visit_ClassDef(
        self,
        node
    ):


        self.graph.add_node(

            node.name,

            kind="class",

            file=self.current_file

        )



        old = self.current_class


        self.current_class = node.name



        # inheritance

        for base in node.bases:


            if isinstance(
                base,
                ast.Name
            ):


                self.graph.add_edge(

                    node.name,

                    base.id,

                    "inherits",

                    0.9

                )



        self.generic_visit(
            node
        )



        self.current_class = old





    # ==========================
    # FUNCTION / METHOD
    # ==========================

    def visit_FunctionDef(
        self,
        node
    ):


        if self.current_class:


            symbol = (

                self.current_class

                + "."

                + node.name

            )


            self.graph.add_node(

                symbol,

                kind="method",

                file=self.current_file

            )



            self.graph.add_edge(

                self.current_class,

                symbol,

                "contains",

                0.95

            )


        else:


            self.graph.add_node(

                node.name,

                kind="function",

                file=self.current_file

            )



        self.generic_visit(
            node
        )





    # ==========================
    # OBJECT CREATION
    # ==========================

    def visit_Assign(
        self,
        node
    ):


        if isinstance(
            node.value,
            ast.Call
        ):


            target = self.get_call_name(
                node.value
            )


            if target and self.current_class:


                self.graph.add_edge(

                    self.current_class,

                    target,

                    "uses",

                    0.8

                )



        self.generic_visit(
            node
        )





    # ==========================
    # METHOD CALL
    # ==========================

    def visit_Call(
        self,
        node
    ):


        target = self.get_call_name(
            node
        )


        if target and self.current_class:


            self.graph.add_edge(

                self.current_class,

                target,

                "calls",

                0.8

            )



        self.generic_visit(
            node
        )





    # ==========================
    # EXTRACT CALL NAME
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
