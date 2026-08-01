import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from app.graph.unified_graph_builder import UnifiedGraphBuilder
from app.graph.impact_analyzer import ImpactAnalyzer
from app.graph.impact_report import ImpactReport



print(
    "========== IMPACT REPORT =========="
)



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)

print("========== DEBUG CHAT SERVICE ==========")
print(graph.get_node("ChatService"))
print("========================================")


analyzer = ImpactAnalyzer(
    graph
)


impacts = analyzer.find_impact(
    "SessionMemory"
)



reporter = ImpactReport(
    graph
)



report = reporter.generate(
    "SessionMemory",
    impacts
)



print(report)