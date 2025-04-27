from typing import Any, Dict, Optional, List, Generator as TypingGen
import simpy
from db import CsvLogger
from graph import WorkflowGraph
from kvstorage import KVStorage
from sim_types import CompDataI, GenContainer, GenTypeState
from abc import ABC, abstractmethod
import weakref


class Component(ABC):
    genState: GenTypeState
    workflow: WorkflowGraph
    logger: CsvLogger
    registry: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        compData: CompDataI,
    ):
        self.env = env
        self.name = name
        # self.component_data = compData
        if compData.id is None:
            raise ValueError(
                "Component 'Resource' requires 'component_data' to be defined."
            )
        self.compId = compData.id
        self.comp_name = compData.compName
        self.type = compData.typeName
        self.category = compData.category
        self.genList = [] if compData.GenData is None else compData.GenData.types
        kv_data = compData.get_custom_input()
        self.var = KVStorage(storage=kv_data)
        self.Yieldable = False if compData.Yieldable is None else compData.Yieldable

        Component.registry[self.compId] = self

    @classmethod
    @abstractmethod
    def create(
        cls,
        env: simpy.Environment,
        compData: CompDataI,
    ) -> "Component":
        """Return a new instance of this component."""
        pass

    @classmethod
    def set_Gen_ref(cls, gen_ref: GenTypeState):
        cls.genState = gen_ref

    @classmethod
    def set_workflow(cls, workflow: WorkflowGraph):
        cls.workflow = workflow

    @classmethod
    def set_logger(cls, logger: CsvLogger):
        cls.logger = logger

    @abstractmethod
    def next_wrapper(self):
        pass

    @classmethod
    def comp_from_registery(cls, compId: str) -> Optional["Component"]:
        return Component.registry.get(compId)

    def _next(self, output: Optional[GenContainer] = None):
        if output is None:
            print("Output is None, cannot proceed.")
            return
        if output.targetComp is None:
            return
        if output.targetHandler is None:
            return

        output_list = self.workflow.find_connection_target(
            source_component_id=output.targetComp,
            source_handle_id=output.targetHandler,
        )

        if output_list is None:
            print(
                f"Connection not found for source component {output.targetComp} and handler {output.targetHandler}."
            )
            return

        output.set_next_target(
            comp=output_list[0],
            handler=output_list[1],
        )

        next_comp_ref = self.comp_from_registery(output_list[0])
        if next_comp_ref is None:
            print(f"Component with ID {output_list[0]} not found in registry.")
            return
        self.env.process(next_comp_ref.run(output))

    @abstractmethod
    def run(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        pass

    def set_actionSet(self, actionSet: List[str]):
        self.actionSet = actionSet

    def get_actionSet(self) -> List[str]:
        return self.actionSet

    def insert_action(self, action: str):
        self.actionSet.append(action)

    def inc_run_call_count(self):
        self.run_call_count += 1

    def get_run_call_count(self) -> int:
        return self.run_call_count

    def log_event(
        self,
        action: str,
        values: Dict[str, Any],
        PDV: Optional[GenContainer] = None,
        more: Optional[Dict[str, Any]] = None,
    ):
        self.logger.log_event(
            {
                "time": self.env.now,
                "component_id": self.compId,
                "component_type": self.category,
                "action": action,
                "values": values,
                "PDV": PDV,
                "addition": more,
            }
        )

    def set_componentData(self, data: CompDataI):
        self.component_data = data

    def set_next_components(self, next_components: List[str]):
        self.next_components = next_components

    def run_custom_code(self, code: str, context):
        try:
            code_obj = compile(code, "<string>", "exec")
            namespace = {}
            exec(code_obj, namespace)
            run_func = namespace["run"]
            result = run_func(context)
            return result
        except Exception as e:
            print(f"Error compiling code: {e}")
            return None

    def timeout(self, duration: int):
        yield self.env.timeout(duration)


class Generator(Component):
    def __init__(
        self,
        env: simpy.Environment,
        compData: CompDataI,
    ):
        super().__init__(
            env=env,
            name="Generator",
            compData=compData,
        )
        self.generated_count = 0
        default_actions = ["GENERATE"]
        self.set_actionSet(default_actions)
        row_gencount = compData.get_input_data("gen_count")
        if isinstance(row_gencount, int):
            self.gen_count = row_gencount
        else:
            self.gen_count = None

    @classmethod
    def create(cls, env: simpy.Environment, compData: CompDataI) -> "Generator":
        return Generator(env=env, compData=compData)

    def next_wrapper(self):
        # before calling next() method, user can decide which compoent to call
        pass

    def defult_output(self):
        pass

    def GenContainerBuild(self, input: GenContainer):
        pass

    def inc_Gen_Count(self):
        self.generated_count += 1

    def test_func(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        yield self.env.timeout(1)

    def run(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        # infinite or bounded loop
        loop = self.gen_count if self.gen_count is not None else None
        while loop is None or loop > 0:
            self.inc_run_call_count()
            self.input_count = getattr(self, "input_count", 0) + 1
            # always yield so this stays a generator
            yield self.env.timeout(1)

            self.log_event(
                action="GENERATE",
                values={
                    "input_count": self.input_count,
                    "run_count": self.run_call_count,
                },
                PDV=None,
            )

            # get a new GenContainer from the user’s logic
            output: GenContainer = yield from self.test_func(input=None)

            # hand it off
            self._next(output)

            self.inc_Gen_Count()
            if loop is not None:
                loop -= 1


class Resource(Component):
    def __init__(
        self,
        env: simpy.Environment,
        compData: CompDataI,
    ):
        super().__init__(
            env=env,
            name="Resource",
            compData=compData,
        )
        default_actions = ["ENTER", "EXIT", "PROCESSING"]
        self.set_actionSet(default_actions)

        # Retrieve and validate the capacity value from component data
        capacity = self.component_data.get_input_data("capacity")

        if capacity is None:
            raise ValueError("Component 'Resource' requires 'capacity' to be defined.")

        if not isinstance(capacity, int):
            raise TypeError(
                f"Capacity must be an integer, got {type(capacity).__name__} instead."
            )

        self.capacity: int = capacity
        self.resource = simpy.Resource(env, capacity=self.capacity)

    @classmethod
    def create(cls, env: simpy.Environment, compData: CompDataI) -> "Resource":
        return Resource(env=env, compData=compData)

    def next_wrapper(self):
        # before calling next() method, user can decide which compoent to call
        pass

    def defult_output(self):
        pass

    def test_func(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        yield self.env.timeout(1)

    def run(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        """
        this the method called when simulation need to run a process. previous component will send the input to this component.
        that way inside this fn will decide what are the thing should be done and need to be returned.
        inside this fn, user can call the custom code and pass the self to it.
        """
        self.inc_run_call_count()
        self.input_count += 1

        # run method for resource
        with self.resource.request() as req:
            yield req
            # Log the event of resource allocation
            self.log_event(
                action="ENTER",
                values={
                    "input_count": self.input_count,
                    "run_count": self.run_call_count,
                },
                PDV=input,
            )
            output: GenContainer = yield from self.test_func(input)

        # Log the event of resource allocation
        self.log_event(
            action="Exit",
            values={
                "input_count": self.input_count,
                "run_count": self.run_call_count,
            },
            PDV=input,
        )
        self._next(output=output)
