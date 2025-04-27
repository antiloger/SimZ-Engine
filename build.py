import json
import simpy
from comp import Component, Generator, Resource
from sim_types import ComponentStore, GenTypeState
from graph import WorkflowGraph
from db import CsvLogger
from pathlib import Path
from typing import Dict, Type


class SimulationBuilder:
    compStore: ComponentStore
    genState: GenTypeState
    workflow: WorkflowGraph
    logger: CsvLogger
    env = simpy.Environment()

    def __init__(
        self,
        runName: str,
        ProjectPath: Path,
        runPath: Path,
        registered_components: Dict[str, Type[Component]],
        run_time: int | None = None,
    ):
        self.runName = runName
        self.filePath = ProjectPath
        self.runPath = runPath
        self.run_time = run_time
        self.compRegistry: Dict[str, Type[Component]] = registered_components
        self.load()

    def load_compStore(self):
        file_path = self.filePath / "dataState.json"
        raw = json.loads(file_path.read_text())
        self.compStore = ComponentStore.model_validate(raw)

    def load_genState(self):
        file_path = self.filePath / "genState.json"
        raw = json.loads(file_path.read_text())
        self.genState = GenTypeState.model_validate(raw)

    def load_workflow(self):
        file_path = self.filePath / "edge.json"
        raw = json.loads(file_path.read_text())
        if isinstance(raw, list) and all(isinstance(item, dict) for item in raw):
            self.workflow = WorkflowGraph(edges_data=raw)
        else:
            raise ValueError("Invalid JSON format: Expected a list of dictionaries")

    def create_logger(self):
        self.logger = CsvLogger(
            filename=str(self.runPath / f"{self.runName}.csv"),
            fieldnames=[
                "time",
                "component_id",
                "component_type",
                "action",
                "values",
                "PDV",
                "addition",
            ],
            buffer_size=1_048_576,
        )

    def load(self):
        self.load_compStore()
        self.load_genState()
        self.load_workflow()
        self.create_logger()

    def build(self):
        for name, comp in self.compStore.root.items():
            if comp.category not in self.compRegistry:
                raise ValueError(f"Component type '{comp.typeName}' not registered.")
            comp_class = self.compRegistry[comp.category]
            component = comp_class(
                env=self.env,
                name=name,
                compData=comp,
            )
            component.set_Gen_ref(self.genState)
            component.set_workflow(self.workflow)
            component.set_logger(self.logger)

    def pprint_compStore(self):
        for name, comp in self.compStore.root.items():
            print(f"Component Name: {name}")
            print(f"Component Data: {comp}")
            print("-" * 20)

    def get_compStore(self):
        return self.compStore

    def find_root_comps(self) -> list[Component]:
        root_comps = []
        roots = self.workflow.get_roots()
        for root in roots:
            comp = Component.comp_from_registery(root)
            if comp is None:
                raise ValueError(f"Component '{root}' not found in component store.")

            root_comps.append(comp)
        return root_comps

    def start(self):
        root_comps = self.find_root_comps()
        for comp in root_comps:
            if comp is None:
                raise ValueError("Component is None, cannot start simulation.")
            self.env.process(comp.run(input=None))

        self.env.run(until=self.run_time)


compReg = {
    "generator": Generator,
    "resource": Resource,
}


# run_name = "test_run"
# project_path = Path("path/to/project")
# run_path = Path("path/to/run")
# run_time = None
def run():
    builder = SimulationBuilder(
        runName="test_run",
        ProjectPath=Path("./projects/state"),
        runPath=Path("./projects/run"),
        registered_components=compReg,
    )

    builder.pprint_compStore()
    builder.build()
    print("Simulation build complete.")
    print(Component.registry)
