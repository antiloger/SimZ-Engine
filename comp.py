from typing import Any, Dict, Optional, List, Generator as TypingGen
import simpy
from codeExec import CodeExec
from db import CsvLogger
from graph import WorkflowGraph
from kvstorage import KVStorage
from sim_types import CompDataI, GenContainer, GenTypeState, GenTypes, GeneratorList
from abc import ABC, abstractmethod
import weakref


class Component(ABC):
    # Define as class variables to be shared across all instances
    genState: GenTypeState
    workflow: WorkflowGraph
    logger: CsvLogger  # Using WeakValueDictionary to avoid memory leaks - when a component is deleted,
    # its entry in the registry will be automatically removed
    registry: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    # Flag to track if class-level resources have been initialized
    _initialized = False

    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        compData: CompDataI,
    ):
        # Check if class resources are initialized
        if not Component._initialized:
            print("WARNING: Component class resources are not initialized yet!")

        self.env = env
        self.name = name

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
        self.run_call_count = 0
        self.input_count = 0
        self.actionSet = []
        self.executor = CodeExec(code=compData.Runners)
        # Register this component instance in the class registry
        self._register()

    def _register(self):
        """Register this component in the class registry."""
        Component.registry[self.compId] = self
        print(
            f"Registered component {self.compId} of type {self.__class__.__name__} in registry"
        )

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
        Component.genState = gen_ref  # Ensure base class has it too
        Component._initialized = True
        print(f"Set GenState reference for {cls.__name__}")

    @classmethod
    def set_workflow(cls, workflow: WorkflowGraph):
        cls.workflow = workflow
        Component.workflow = workflow  # Ensure base class has it too
        Component._initialized = True
        print(f"Set workflow reference for {cls.__name__}")

    @classmethod
    def set_logger(cls, logger: CsvLogger):
        cls.logger = logger
        Component.logger = logger  # Ensure base class has it too
        Component._initialized = True
        print(f"Set logger reference for {cls.__name__}")

    @abstractmethod
    def next_wrapper(self):
        pass

    @classmethod
    def comp_from_registery(cls, compId: str) -> Optional["Component"]:
        """Retrieve a component by its ID from the registry."""
        comp = cls.registry.get(compId)
        if comp is None:
            print(
                f"Component with ID {compId} not found in registry. Registry has {len(cls.registry)} components."
            )
            print(f"Available components: {list(cls.registry.keys())}")
        return comp

    @classmethod
    def get_registry_size(cls) -> int:
        """Return the number of components in the registry."""
        return len(cls.registry)

    @classmethod
    def get_registry_keys(cls) -> List[str]:
        """Return a list of all component IDs in the registry."""
        return list(cls.registry.keys())

    @classmethod
    def check_registry(cls):
        """Check and print registry information for debugging."""
        print(f"Registry contains {len(cls.registry)} components.")
        print(f"Registry keys: {list(cls.registry.keys())}")
        print(
            f"Registry values types: {[type(v).__name__ for v in cls.registry.values()]}"
        )

    def targetHandlerFind(self, output: GenContainer) -> Optional[str]:
        types_gen = output.get_name_in_Data()
        if len(types_gen) == 1:
            return f"{types_gen[0]}-out"
        return None

    def getGenType(self, name: str) -> Optional[Dict[str, GenTypes]]:
        gen_data = self.genState.get_by_name(name)
        if gen_data is None:
            print(f"GenType {name} not found in GenState.")
            return None
        return gen_data

    def create_default_containter(self, genTypeName) -> GenContainer:
        gen_data = self.genState.get_by_name(genTypeName)
        if gen_data is None:
            print(f"GenType {genTypeName} not found in GenState.")
            raise ValueError("GenType not found in GenState.")

        return GenContainer(
            Data=gen_data,
            targetComp=None,
            targetHandler=None,
        )

    def _next(self, output: Optional[GenContainer] = None):
        if output is None:
            print("Output is None, cannot proceed.")
            return
        if output.targetComp is None:
            output.targetComp = self.compId

        if output.targetHandler is None:
            str_hand = self.targetHandlerFind(output)
            if str_hand is None:
                return
            output.targetHandler = str_hand

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

        # Check registry explicitly before proceeding
        print(
            f"Looking for component {output_list[0]} in registry with {self.get_registry_size()} components"
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

    def input_processing(self, input: GenContainer):
        t, d = input.split_at_last_dash()
        if t is None or d is None:
            raise ValueError("Invalid input format. Expected 'type-data'.")

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
        genlist = (
            []
            if compData.GenData is None or compData.GenData.types is None
            else compData.GenData.types
        )
        self.GenList = self.initGenType(genlist)

        self.generated_count = 0
        default_actions = ["GENERATE"]
        self.set_actionSet(default_actions)
        row_gencount = compData.get_input_data("gen_count")
        if isinstance(row_gencount, int):
            self.gen_count = row_gencount
        else:
            self.gen_count = None
        print(f"Generator {self.compId} initialized with gen_count: {self.gen_count}")

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

    def initGenType(self, data: List[str]) -> List[GeneratorList]:
        genTypes = []
        for i in data:
            t = GeneratorList(id=i, count=0)
            genTypes.append(t)
        return genTypes

    def inc_Gen_Count(self):
        self.generated_count += 1

    def test_func(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        genTypes = {}
        for value in self.GenList:
            genData = self.genState.get(value.id)
            genTypes[value.id] = genData

        container = GenContainer(
            Data=genTypes,
            targetComp=None,
            targetHandler=None,
        )
        yield self.env.timeout(1)
        return container

    def run(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        # infinite or bounded loop
        loop = self.gen_count if self.gen_count is not None else None
        while loop is None or loop > 0:
            self.inc_run_call_count()
            self.input_count = getattr(self, "input_count", 0) + 1

            # get a new GenContainer from the user's logic
            output: GenContainer = yield from self.test_func(input=None)

            self.log_event(
                action="GENERATE",
                values={
                    "input_count": self.input_count,
                    "run_count": self.run_call_count,
                },
                PDV=output,
            )
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
        capacity = compData.get_input_data("capacity")

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
        return input

    def run(self, input: Optional[GenContainer]) -> TypingGen[Any, Any, Any]:
        """
        this the method called when simulation need to run a process. previous component will send the input to this component.
        that way inside this fn will decide what are the thing should be done and need to be returned.
        inside this fn, user can call the custom code and pass the self to it.
        """
        self.inc_run_call_count()
        self.input_count = getattr(self, "input_count", 0) + 1

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
        if output is not None and output.targetHandler is not None:
            b, _ = output.targetHandler.rsplit("-", 1)
            output.targetHandler = b + "-out"
        self._next(output=output)
