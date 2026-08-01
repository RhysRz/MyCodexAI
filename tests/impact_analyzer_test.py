import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)



from app.graph.unified_graph_builder import UnifiedGraphBuilder
from app.graph.impact_analyzer import ImpactAnalyzer



print(
    "========== IMPACT ANALYSIS =========="
)



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)



analyzer = ImpactAnalyzer(
    graph
)



result = analyzer.find_impact(
    "SessionMemory"
)



for item in result:

    print(item)