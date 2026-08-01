import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)



from app.graph.unified_graph_builder import UnifiedGraphBuilder
from app.graph.symbol_relationship_resolver import SymbolRelationshipResolver
from app.graph.relationship_analyzer import RelationshipAnalyzer



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)



resolver = SymbolRelationshipResolver(
    graph
)


relationships = resolver.build()



analyzer = RelationshipAnalyzer()


result = analyzer.analyze(
    relationships
)



print(
    "========== INTELLIGENT RELATIONSHIPS =========="
)



for item in result[:30]:

    print(item)