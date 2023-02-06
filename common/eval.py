from typing import Dict

from simpleeval import SimpleEval


def build_eval_obj(context: dict, functions: dict = {}):
    s = SimpleEval()
    s.names = context

    def set_data(name, value):
        keys = name.split(".")
        target = context
        last_key = keys[-1]
        for k in keys[:-1]:  # when assigning drill down to *second* last key
            target = target[k]
        target[last_key] = value

    default_functions = {"set_data": set_data, "any": any}
    s.functions = {**functions, **default_functions}
    return s


class FormData:
    def __init__(self, data: Dict):
        self.data = {
            k: FormData(v) if isinstance(v, dict) else v for k, v in data.items()
        }

    def __getattr__(self, item):
        return self.data.get(item, None)

    def __getitem__(self, item):
        return self.data.get(item, None)

    def fields_end_with(self, postfix: str):
        return FormData({k: v for k, v in self.data.items() if k.endswith(postfix)})

    def items(self):
        return self.data.items()

    def exclude_value(self, *args):
        return FormData({k: v for k, v in self.data.items() if v not in args})

    def values(self):
        return self.data.values()

    def exists(self):
        return any(self.data.values())

    def contains_value(self, *args):
        return self.count_contains_value(*args) == len(args)

    def count_contains_value(self, *args):
        values = self.data.values()
        cnt = 0
        for arg in args:
            for value in values:
                if arg in value:
                    cnt += 1
                    break
        return cnt
