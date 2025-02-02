import os
from collections import defaultdict
import pandas as pd
from ccf.easy_yaml import EasyYaml


def aslist(item):
    if not item:
        return []
    elif type(item) is list:
        return item
    else:
        return [item]


def xyz(body, n=1):
    args = ', '.join(list('xXyYzZ')[:n * 2])
    code = 'def func(%s):\n    ' % args
    code += body.replace('\n', '\n    ')
    new_local = {}
    exec(code, None, new_local)
    return new_local['func']


def passthrough(x, X, y=None, Y=None, z=None, Z=None):
    return x, y, z


class Transformer:
    def __init__(self, map_dir='./map/', funcs={}):
        self.Y = EasyYaml()
        self.funcs = funcs
        self.map_dir = map_dir
        self.elements = []
        self.mappings = {}
        self.load_maps()

    def load_map(self, struct):
        filepath = os.path.join(self.map_dir, struct + '.yaml')
        contents = self.Y(filepath)
        element_list = contents['elements']
        print("Loading  ",filepath)
        elements = []
        for item in element_list:
            item['struct'] = struct
            sources_list = aslist(item.pop('source'))
            for source in sources_list:
                new_element = item.copy()
                elements.append(new_element)

                if type(source) is str:
                    new_element['source'] = source
                else:
                    new_element['source'], additional_detail = source.popitem()
                    new_element.update(additional_detail)
        self.elements.extend(elements)
        return elements

    def load_maps(self, path=None):
        path = path if path else self.map_dir
        for filename in os.listdir(path):
            if filename.endswith('.yaml'):
                self.load_map(filename[:-5])

    def get_unique_variables(self):
        unique = set()
        for e in self.elements:
            names = e.get('name')
            source = e.get('source')
            struct = e.get('struct')

            if type(names) is str:
                unique.add((source, names))
            elif type(names) is list:
                unique.update([(source, name) for name in names])
        return unique

    def get_executable(self, element, nargs):
        code, func = element.get('code'), element.get('func')
        if func:
            if func in self.funcs:
                executable = self.funcs[func]
            else:
                print('There is no function of that name so just passing through.', func)
                executable = passthrough
        elif code:
            executable = xyz(code, nargs)
        else:
            executable = passthrough
        return executable

    def transform(self, datacache, filter_fn=None):
        db = defaultdict(lambda: defaultdict(dict))
        for e in filter(filter_fn, self.elements):
            struct, source, = e['struct'], e['source']
            column = db[struct][source]
            renames = aslist(e.get('rename'))
            names = aslist(e.get('name'))
            data = datacache.get_fields(source, names)
            func = self.get_executable(e, len(names))
            try:
                result = func(*data)
            except Exception as err:
                print("Error on the following item:")
                print("Names:",names)
                print("Renames:",renames)
                print("Exec:", func.__code__)
                raise err

            if type(result) is not tuple:
                result = (result,)

            for i in range(min(len(result), len(renames))):
                if 'recode' in e:
                    column[renames[i]] = result[i].replace(e['recode'])
                else:
                    column[renames[i]] = result[i]

        result = {}
        for struct, v1 in db.items():
            result[struct] = pd.concat(list(map(pd.DataFrame, v1.values())))

        return result
