from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel


# Placeholder for TimeStepGenConfig (import this or define it as needed)
class TimeStepGenConfig(BaseModel):
    # Define your specific fields here
    pass


# A DynArray is defined recursively in TS.
# Here, we treat it as a List of generic JSON types.
DynArray = List[Any]


# -----------------------------
# InputFieldFormat and dependencies
# -----------------------------
class FieldType(str, Enum):
    number = "number"
    text = "text"
    select = "select"
    checkbox = "checkbox"
    multiselect = "multiselect"


class InputFieldFormat(BaseModel):
    inputName: str
    fieldType: FieldType
    # defaultValue can be a number, string, boolean, list (of strings or numbers), or None
    defaultValue: Union[int, str, bool, List[str], List[int], None]
    validation: str  # a regex pattern or similar
    display: bool
    description: Optional[str] = None
    required: bool
    options: Optional[Union[List[str], List[int]]] = None


# -----------------------------
# OutputDataFormats
# -----------------------------
class OutputType(str, Enum):
    chart_pie = "Chart-Pie"
    table = "Table"
    card = "Card"


class OutputDataFormats(BaseModel):
    typeOut: OutputType


# -----------------------------
# ConfigGenerator and DataGenerator
# -----------------------------
class ConfigGenerator(BaseModel):
    genFn: str
    config: TimeStepGenConfig


class DataGenerator(BaseModel):
    config: ConfigGenerator
    types: Optional[List[str]]  # represents TS: string[] | null


# -----------------------------
# CompRegDataI
# -----------------------------
class CompCategory(str, Enum):
    generator = "generator"
    model = "model"
    distributer = "distributer"


class CompRegDataI(BaseModel):
    typeName: str
    description: Optional[str] = None
    color: Optional[str] = None
    category: CompCategory
    InputForm: List[InputFieldFormat]
    OutputData: List[OutputDataFormats]
    isGenerator: Optional[bool] = None


# Example for a registry store:
# Mapping: { category: { compType: CompRegDataI } }
CompRegStore = Dict[str, Dict[str, CompRegDataI]]


# -----------------------------
# ConnectorData
# -----------------------------
class FlowType(str, Enum):
    in_flow = "in"
    out_flow = "out"
    inout = "inout"


class ConnectorData(BaseModel):
    id: str
    name: str
    flow: FlowType  # use FlowType if your valid flows are "in", "out", "inout"
    type: List[str]
    validation: str


# -----------------------------
# RunnerFn
# -----------------------------
class RunnerFnType(str, Enum):
    ML = "ML"
    PreFunc = "PreFunc"
    DynCode = "DynCode"
    SubProcess = "SubProcess"


class RunnerFn(BaseModel):
    type: RunnerFnType
    name: str
    args: DynArray


# -----------------------------
# CompDataI
# -----------------------------
class CompDataI(BaseModel):
    typeName: str
    compName: str
    id: Optional[str] = None
    category: str  # if there is a limited set of categories, you could use an Enum here as well
    color: Optional[str] = None
    notification: Optional[List[str]] = None
    # inputData: values can be number, string, bool, list of strings/numbers, or None
    inputData: Dict[str, Union[int, str, bool, List[str], List[int], None]]
    # customInput maps keys to InputFieldFormat instances
    customInput: Dict[str, InputFieldFormat]
    connectors: List[ConnectorData]
    Runners: List[RunnerFn]
    GenData: Optional[DataGenerator] = None

    def get_input_data(
        self, key: str
    ) -> Optional[Union[int, str, bool, List[str], List[int], None]]:
        """
        Get input data by key.
        """
        return self.inputData.get(key)


# -----------------------------
# GenAttributes
# -----------------------------
class GenAttributes(BaseModel):
    type: str
    value: Union[str, int, float, bool, dict, None]


# -----------------------------
# GenTypes
# -----------------------------
class GenTypes(BaseModel):
    typeName: str
    genComponentId: str
    attributes: Dict[str, GenAttributes]

    # in attr type can be str, int, float, bool, dict. then value need to be same type
    def type_check(self, attr_name: str) -> bool:
        """
        Check if the attribute type matches the expected type.
        """
        attr = self.get_attribute(attr_name)
        if attr:
            if attr.value == "str":
                return isinstance(attr.value, str)
            elif attr.value == "int":
                return isinstance(attr.value, int)
            elif attr.value == "float":
                return isinstance(attr.value, float)
            elif attr.value == "bool":
                return isinstance(attr.value, bool)
            elif attr.value == "dict":
                return isinstance(attr.value, dict)
            else:
                return False
        return False

    def _type_check_helper(
        self, attr_type: str, attr_value: Union[str, int, float, bool, dict]
    ) -> bool:
        if attr_type == "str":
            return isinstance(attr_value, str)
        elif attr_type == "int":
            return isinstance(attr_value, int)
        elif attr_type == "float":
            return isinstance(attr_value, float)
        elif attr_type == "bool":
            return isinstance(attr_value, bool)
        elif attr_type == "dict":
            return isinstance(attr_value, dict)
        else:
            return False

    def get_attribute(self, attr_name: str) -> Optional[GenAttributes]:
        """
        Get the attribute by name.
        """
        return self.attributes.get(attr_name)

    def get_value(self, attr_name: str) -> Optional[Union[str, int, float, bool, dict]]:
        """
        Get the value of the attribute by name.
        """
        attr = self.get_attribute(attr_name)
        if attr:
            return attr.value
        return None

    def update_value(
        self, attr_name: str, new_value: Union[str, int, float, bool, dict]
    ) -> None:
        """
        Update the value of the attribute by name.
        """
        if attr_name in self.attributes:
            self.attributes[attr_name].value = new_value
        else:
            raise KeyError(f"Attribute '{attr_name}' not found in GenTypes.")

    def delete_attribute(self, attr_name: str) -> None:
        """
        Delete the attribute by name.
        """
        if attr_name in self.attributes:
            del self.attributes[attr_name]
        else:
            raise KeyError(f"Attribute '{attr_name}' not found in GenTypes.")

    def create_attribute(
        self,
        attr_name: str,
        attr_type: str,
        attr_value: Union[str, int, float, bool, dict],
    ) -> None:
        """
        Create a new attribute.
        """
        if attr_name not in self.attributes:
            if not self._type_check_helper(attr_type, attr_value):
                raise ValueError(
                    f"Type mismatch: expected {attr_type}, got {type(attr_value).__name__}"
                )
            self.attributes[attr_name] = GenAttributes(type=attr_type, value=attr_value)
        else:
            raise KeyError(f"Attribute '{attr_name}' already exists in GenTypes.")

    def get_genCompId(self) -> str:
        """
        Get the genComponentId.
        """
        return self.genComponentId

    def get_typeName(self) -> str:
        """
        Get the typeName.
        """
        return self.typeName


# -----------------------------
# GenContainer
# -----------------------------
class GenContainer(BaseModel):
    containerId: int
    Data: Dict[str, GenTypes]

    def insert(self, genType: GenTypes) -> None:
        """
        Insert a new GenTypes instance.
        """
        if genType.typeName in self.Data:
            raise KeyError(f"GenType '{genType.typeName}' already exists.")
        self.Data[genType.typeName] = genType

    def get(self, type_name: str) -> Optional[GenTypes]:
        """
        Get a GenTypes instance by typeName.
        """
        return self.Data.get(type_name)

    def insert_data(self, data: Dict[str, GenTypes]) -> None:
        """
        Insert multiple GenTypes instances.
        """
        for key, value in data.items():
            if key in self.Data:
                raise KeyError(f"GenType '{key}' already exists.")
            self.Data[key] = value


# -----------------------------
# GenTypeState
# -----------------------------
class GenTypeState(BaseModel):
    __root__: Dict[str, GenTypes]

    def insert(self, genType: GenTypes) -> None:
        """
        Insert a new GenTypes instance.
        """
        if genType.typeName in self.__root__:
            raise KeyError(f"GenType '{genType.typeName}' already exists.")
        self.__root__[genType.typeName] = genType

    def delete(self, type_name: str) -> None:
        """
        Delete a GenTypes instance by typeName.
        """
        if type_name in self.__root__:
            del self.__root__[type_name]
        else:
            raise KeyError(f"GenType '{type_name}' not found.")

    def update_value(self, type_name: str, attr_name: str, new_value: Any) -> None:
        """
        Update the value of a specific attribute in a GenTypes instance.
        """
        if type_name in self.__root__:
            gen_type = self.__root__[type_name]
            gen_type.update_value(attr_name, new_value)
        else:
            raise KeyError(f"GenType '{type_name}' not found.")

    def genType_checker(self, type_name: str, type: GenTypes) -> bool:
        """
        Check if the typeName and genComponentId match.
        """
        if type_name in self.__root__:
            existing_gen_type = self.__root__[type_name]
            return (
                existing_gen_type.typeName == type.typeName
                and existing_gen_type.genComponentId == type.genComponentId
            )
        return False
