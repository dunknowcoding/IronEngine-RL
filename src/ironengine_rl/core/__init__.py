__all__ = [
    "HeuristicAgent",
    "InferenceEngine",
    "KnowledgeRepository",
    "RuntimeOrchestrator",
    "SafetyController",
    "TaskMetricsAccumulator",
]


def __getattr__(name: str):
    if name == "HeuristicAgent":
        from .agent import HeuristicAgent

        return HeuristicAgent
    if name == "InferenceEngine":
        from .inference_engine import InferenceEngine

        return InferenceEngine
    if name == "KnowledgeRepository":
        from .knowledge_repository import KnowledgeRepository

        return KnowledgeRepository
    if name == "RuntimeOrchestrator":
        from .runtime import RuntimeOrchestrator

        return RuntimeOrchestrator
    if name == "SafetyController":
        from .safety import SafetyController

        return SafetyController
    if name == "TaskMetricsAccumulator":
        from .task_metrics import TaskMetricsAccumulator

        return TaskMetricsAccumulator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
