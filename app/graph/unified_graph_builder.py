# -*- coding: utf-8 -*-

from app.graph.project_graph_builder import ProjectGraphBuilder
from app.graph.symbol_graph_builder import SymbolGraphBuilder
from app.graph.call_graph_builder import CallGraphBuilder

from app.graph.unified_graph import UnifiedCodeGraph

from app.graph.call_graph_cleaner import CallGraphCleaner



class UnifiedGraphBuilder:


    def __init__(self):

        self.project_builder = ProjectGraphBuilder()

        self.symbol_builder = SymbolGraphBuilder()

        self.call_builder = CallGraphBuilder()

        self.cleaner = CallGraphCleaner()



    def build(
        self,
        path
    ):


        unified = UnifiedCodeGraph()



        # ==========================
        # BUILD SOURCES
        # ==========================

        project_graph = self.project_builder.build(
            path
        )


        symbol_graph = self.symbol_builder.build(
            path
        )


        call_graph = self.call_builder.build(
            path
        )



        # ==========================
        # MERGE
        # ==========================

        unified.merge(
            project_graph
        )


        unified.merge(
            symbol_graph
        )


        unified.merge(
            call_graph
        )



        # ==========================
        # CLEAN
        # ==========================

        unified = self.cleaner.clean(
            unified
        )



        return unified
