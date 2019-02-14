from seneca.constants.whitelists import ALLOWED_AST_TYPES, ALLOWED_IMPORT_PATHS, SENECA_LIBRARY_PATH
import ast

class Plugins:

    @staticmethod
    def fixed_precision(code_str):
        return '''
from seneca.libs.decimal import make_decimal
''' + code_str

    @staticmethod
    def resource_limits(code_str):
        return '''
from seneca.libs.resources import set_resources
set_resources()
''' + code_str

    @staticmethod
    def stamps(code_str, stamps_supplied):
        return '''
from seneca.contracts.currency import submit_stamps
submit_stamps({})
'''.format(stamps_supplied) + code_str

    @staticmethod
    def import_module(code_str, module, func):
        return code_str + '''
__result__ = {func}()
'''.format(func=func)


class ReadOnlyException(Exception):
    pass


class CompilationException(Exception):
    pass


class Assert:

    @staticmethod
    def ast_types(t):
        if type(t) not in ALLOWED_AST_TYPES:
            CompilationException('Illegal AST type: {}'.format(t))

    @staticmethod
    def not_system_variable(v):
        if v.startswith('__') and v.endswith('__'):
            raise CompilationException('Access denied for system variable: {}'.format(v))

    @staticmethod
    def valid_import_path(import_path, module_name=None, contract_name=None):
        if module_name == '*':
            raise ImportError('Not allowed to import *')
        elif module_name:
            import_path = '.'.join([import_path, module_name])
        if import_path == 'seneca.engine.interpret.executor.Executor' and contract_name in ('smart_contract', ):
            return True
        if import_path.startswith(SENECA_LIBRARY_PATH):
            return True
        for path in ALLOWED_IMPORT_PATHS:
            if import_path.startswith(path):
                if len(import_path.split('.')) - len(path.split('.')) == 2:
                    return True
                else:
                    raise ImportError(
                        'Instead of importing the entire "{}" module, you must import each functions directly.'.format(
                            import_path))
        raise ImportError('Cannot find module "{}" in allowed protected_imports'.format(import_path))

    @staticmethod
    def is_protected(target, scope):
        if isinstance(target, ast.Subscript):
            return
        if target.id in scope['protected'] or target.id in [k.rsplit('.', 1)[-1] for k in scope['imports'].keys()]:
            raise ReadOnlyException('Cannot assign value to "{}" as it is a read-only variable'.format(target.id))

    @staticmethod
    def no_nested_imports(node):
        for item in node.body:
            if type(item) in [ast.ImportFrom, ast.Import]:
                raise CompilationException('Not allowed to import inside a function definition')