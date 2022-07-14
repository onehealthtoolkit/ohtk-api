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

    assignment_functions = {"set_data": set_data}
    s.functions = {**functions, **assignment_functions}
    return s
