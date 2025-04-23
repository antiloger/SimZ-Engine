from typing import Any, Dict, Generator, List, Optional
import simpy
from db import CsvLogger
from sim_types import CompDataI, GenContainer
from abc import ABC, abstractmethod


class Component(ABC):
    actionSet: List[str]
    run_call_count: int = 0

    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        logger: CsvLogger,
        compData: CompDataI,
        next_conn: List[str],
    ):
        self.env = env
        self.name = name
        self.log = logger
        self.component_data = compData
        self.next_components = next_conn

    @abstractmethod
    def next_wrapper(self):
        pass

    @abstractmethod
    def defult_output(self):
        pass

    def _next(self):
        pass

    @abstractmethod
    def run(self, input: GenContainer) -> Generator:
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
        values: Dict,
        PDV: GenContainer,
        more: Optional[Dict[str, Any]] = None,
    ):
        self.log.log_event(
            {
                "time": self.env.now,
                "component_id": self.component_data.id,
                "component_type": self.component_data.typeName,
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


class Resource(Component):
    input_count = 0

    def __init__(
        self,
        env: simpy.Environment,
        logger: CsvLogger,
        compData: CompDataI,
        next_conn: List[str],
    ):
        super().__init__(
            env=env,
            name="Resource",
            logger=logger,
            compData=compData,
            next_conn=next_conn,
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

    def next_wrapper(self):
        # before calling next() method, user can decide which compoent to call
        pass

    def defult_output(self):
        pass

    def run(self, input: GenContainer) -> Generator:
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
            # run the custom code or function
            # self.run_custom_code(code, self)

        self._next()
