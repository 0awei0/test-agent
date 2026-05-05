import re
import yaml
from loguru import logger


def load_yaml(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def replace_variables(data, variables: dict):
    if isinstance(data, str):
        pattern = r"\{\{(\w+)\}\}"
        matches = re.findall(pattern, data)
        for match in matches:
            if match in variables:
                data = data.replace(f"{{{{{match}}}}}", str(variables[match]))
        return data
    elif isinstance(data, dict):
        return {k: replace_variables(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_variables(item, variables) for item in data]
    return data


def parse_yaml_with_variables(file_path: str, variables: dict = None) -> dict:
    data = load_yaml(file_path)
    if variables:
        data = replace_variables(data, variables)
    return data
