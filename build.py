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
        self.components = {}  # Store component instances by their IDs
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

        # Set class-level references for all component types immediately after loading
        # This ensures the class variables are set before any instances are created
        for comp_class in self.compRegistry.values():
            comp_class.set_Gen_ref(self.genState)
            comp_class.set_workflow(self.workflow)
            comp_class.set_logger(self.logger)

    def build(self):
        # First, ensure the Component class has the necessary references
        # This is critical to ensure that all components created will have access to these
        Component.set_Gen_ref(self.genState)
        Component.set_workflow(self.workflow)
        Component.set_logger(self.logger)

        # Now build all components
        for comp_id, comp_data in self.compStore.root.items():
            if comp_data.category not in self.compRegistry:
                raise ValueError(
                    f"Component type '{comp_data.typeName}' not registered."
                )

            comp_class = self.compRegistry[comp_data.category]

            # Create the component instance
            component = comp_class.create(
                env=self.env,
                compData=comp_data,
            )

            # Store the component in our local dictionary for easier access
            self.components[comp_id] = component

            # Debug output to confirm creation
            print(f"Created component {comp_id} of type {comp_data.category}")

        # Verify that components are properly registered
        print(f"Registry size after build: {Component.get_registry_size()}")
        print(f"Registry keys: {Component.get_registry_keys()}")

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
        print(f"Found root components: {roots}")

        for root in roots:
            comp = Component.comp_from_registery(root)
            if comp is None:
                # Try to find it in our local components dictionary as a fallback
                comp = self.components.get(root)
                if comp is None:
                    raise ValueError(
                        f"Component '{root}' not found in component registry or local components."
                    )
                # Re-register it just to be safe
                Component.registry[root] = comp
                print(f"Re-registered component {root} in registry")

            root_comps.append(comp)
        return root_comps

    def start(self):
        # Before starting, verify registry state
        print(f"Registry before start: {list(Component.registry.keys())}")

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


def run():
    builder = SimulationBuilder(
        runName="test_run",
        ProjectPath=Path("./projects/state"),
        runPath=Path("./projects/run"),
        registered_components=compReg,
    )

    builder.pprint_compStore()
    builder.build()

    # Check registry after build
    print("Simulation build complete.")
    print(f"Registry contains {Component.get_registry_size()} components")
    print(f"Registry keys: {Component.get_registry_keys()}")

    # Print the actual registry dictionary to see what's in it
    registry_dict = {k: v.__class__.__name__ for k, v in Component.registry.items()}
    print(builder.genState)

    # Optional - start the simulation
    # builder.start()
