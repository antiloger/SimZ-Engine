from comp import Component
from sim_types import GenContainer, RunnerFile
from typing import Any, Dict
import ast
import inspect
import os


class CodeExec:
    def __init__(self, code: RunnerFile):
        self.run = ""
        self.model = ""
        self.generator = ""
        self.event = ""
        self._run_namespace = {}
        self._generator_namespace = {}
        self._model_namespace = {}
        self._event_namespace = {}
        # Import dependencies once
        self._default_imports = {
            "Component": Component,
            "GenContainer": GenContainer,
            "os": os,
            # Add any other required imports here
        }
        self.load(code)

    def load(self, code: RunnerFile):
        """Load and execute the code components into namespaces"""
        self.run = code.run
        self.model = code.model
        self.generator = code.generator
        self.event = code.event

        # Process each component
        if self.run:
            self._run_namespace = self._prepare_code(self.run)

        # if self.generator:
        #     self._generator_namespace = self._prepare_code(self.generator)
        #
        # if self.model:
        #     self._model_namespace = self._prepare_code(self.model)
        #
        # if self.event:
        #     self._event_namespace = self._prepare_code(self.event)

    def _prepare_code(self, code_str: str):
        """Validate syntax and execute code in a new namespace"""
        try:
            # First validate syntax
            ast.parse(code_str)

            # Create namespace with common imports
            namespace = self._default_imports.copy()

            # Execute code directly in the namespace
            exec(code_str, namespace)
            return namespace
        except SyntaxError as e:
            print(f"Syntax error in code: {e}")
            return {}
        except Exception as e:
            print(f"Error executing code: {e}")
            return {}

    def execute_run(self, component: Component, input_data: GenContainer):
        """Execute the run function with the specified signature"""
        return self._execute_simulation_function(
            "run", self._run_namespace, component, input_data
        )

    def execute_generator(self, component: Component, input_data: GenContainer):
        """Execute the generator function with the specified signature"""
        return self._execute_simulation_function(
            "generate_data", self._generator_namespace, component, input_data
        )

    def execute_model(self, component: Component, input_data: GenContainer):
        """Execute the model function with the specified signature"""
        return self._execute_simulation_function(
            "process_model", self._model_namespace, component, input_data
        )

    def execute_event(self, component: Component, input_data: GenContainer):
        """Execute the event function with the specified signature"""
        return self._execute_simulation_function(
            "handle_event", self._event_namespace, component, input_data
        )

    def execute_test(self, data):
        try:
            # First validate syntax
            ast.parse(self.run)

            # Create namespace with common imports
            namespace = {
                "os": os,
            }

            # Execute code directly in the namespace
            exec(self.run, namespace)

            func = namespace.get("run")
            if not callable(func):
                print("Error:  is not callable")
                return None
            func(data)

        except SyntaxError as e:
            print(f"Syntax error in code: {e}")
            return {}
        except Exception as e:
            print(f"Error executing code: {e}")
            return {}

    def _execute_simulation_function(
        self,
        func_name: str,
        namespace: Dict[str, Any],
        component: Component,
        input_data: GenContainer,
    ):
        """Execute a simulation function with the standard signature"""
        if func_name not in namespace:
            print(f"Error: '{func_name}' function not found in the code")
            return None

        func = namespace[func_name]

        if not callable(func):
            print(f"Error: '{func_name}' is not callable")
            return None

        try:
            result = func(component, input_data)

            # Handle generator functions (those that use 'yield')
            if inspect.isgeneratorfunction(func):
                return result  # Return the generator object for the caller to iterate
            else:
                return result  # Return the normal function result
        except Exception as e:
            print(f"Error calling {func_name} function: {e}")
            return None
