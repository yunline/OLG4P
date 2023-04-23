import ast
import random
from typing import Optional

random.seed(12345)


class ConvertError(Exception):
    pass


unique_id_set = {""}


def unique_id():
    uid = ""
    while uid in unique_id_set:
        uid = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for i in range(10))
    return uid


def ast_walk(node, excludes: Optional[list] = None):
    if excludes is None:
        excludes = []
    from collections import deque

    todo = deque([node])
    while todo:
        node = todo.popleft()
        if type(node) in excludes:
            continue
        todo.extend(ast.iter_child_nodes(node))
        yield node


def arg_remove_annotation(arg: ast.arguments) -> None:
    # Warning: In place operation
    if arg.vararg is not None:
        arg.vararg.annotation = None
    if arg.kwarg is not None:
        arg.kwarg.annotation = None
    for args in [arg.posonlyargs, arg.args, arg.kwonlyargs]:
        for _arg in args:
            _arg.annotation = None


def template_subscript_assign(target: ast.Subscript, value: ast.AST) -> ast.AST:
    _slice = target.slice
    if isinstance(target.slice, ast.Slice):
        _slice = ast.Call(
            func=ast.Name(
                id="slice",
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[],
        )
        for i in [
            target.slice.lower,
            target.slice.upper,
            target.slice.step,
        ]:
            if i is None:
                _slice.args.append(ast.Constant(value=None))
            else:
                _slice.args.append(i)

    out = ast.Call(
        func=ast.Attribute(
            value=target.value,
            attr="__setitem__",
            ctx=ast.Load(),
        ),
        args=[_slice, value],
        keywords=[],
    )
    return out


def template_attribute_assign(target: ast.Attribute, value: ast.AST) -> ast.AST:
    out = ast.Call(
        func=ast.Attribute(
            value=target.value,
            attr="__setattr__",
            ctx=ast.Load(),
        ),
        args=[ast.Constant(value=target.attr), value],
        keywords=[],
    )
    return out


def template_auto_assign(target: ast.AST, value: ast.AST) -> ast.AST:
    if isinstance(target, ast.Name):
        target.ctx = ast.Store()
        out = ast.NamedExpr(target=target, value=value)
    elif isinstance(target, ast.Subscript):
        out = template_subscript_assign(target, value)
    elif isinstance(target, ast.Attribute):
        out = template_attribute_assign(target, value)
    else:
        if hasattr(target, "lineno"):
            raise ConvertError(f"Unknown assign type at line {target.lineno}")
        raise ConvertError("Unknown assign type")

    return out


def template_while(payload: ast.AST, condition: ast.AST) -> ast.AST:
    takewhile_args = [
        ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="_")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=condition,
        ),
        ast.Call(
            func=ast.Attribute(
                value=ast.Name(
                    id="itertools",
                    ctx=ast.Load(),
                ),
                attr="count",
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[],
        ),
    ]
    out = ast.ListComp(
        elt=payload,
        generators=[
            ast.comprehension(
                target=ast.Name(
                    id="_",
                    ctx=ast.Store(),
                ),
                iter=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(
                            id="itertools",
                            ctx=ast.Load(),
                        ),
                        attr="takewhile",
                        ctx=ast.Load(),
                    ),
                    args=takewhile_args,
                    keywords=[],
                ),
                ifs=[],
                is_async=0,
            )
        ],
    )
    return out


class Converter:
    def __init__(self, isfunc: bool = False):
        self.isfunc = isfunc

        self.loop_control_stack = []
        self.names: set[str] = set()

        self.usesing_itertools = False
        self.filename = "<string>"

        if isfunc:
            _id = unique_id()
            self.not_return = ast.Name(id="__ol_not_return_" + _id)
            self.return_value = ast.Name(id="__ol_return_value_" + _id)
            self.have_return = False
            self.global_names: set[str] = set()

        self.node_handler_map = {
            ast.Expr: self.handle_expr,
            ast.For: self.handle_for,
            ast.If: self.handle_if,
            ast.Pass: self.handle_pass,
            ast.Assign: self.handle_assign,
            ast.AnnAssign: self.handle_ann_assign,
            ast.AugAssign: self.handle_aug_assign,
            ast.Import: self.handle_import,
            ast.While: self.handle_while,
            ast.FunctionDef: self.handle_def,
            ast.Continue: self.handle_continue,
            ast.Break: self.handle_break,
            ast.Return: self.handle_return,
            ast.Global: self.handle_global,
        }

    def set_filename(self, name: str):
        self.filename = name

    def update_names(self, nodes: list):
        for node in nodes:
            for _node in ast_walk(node, excludes=[ast.Lambda]):
                if isinstance(_node, ast.Name) and not _node.id.startswith("__ol_"):
                    self.names.add(_node.id)

    def handle_for(self, for_statement: ast.For) -> list:
        out = []

        _id = unique_id()
        not_break = ast.Name(id="__ol_not_brk_" + _id)
        not_continue = ast.Name(id="__ol_not_cont_" + _id)

        self.loop_control_stack.append(
            {
                "break_var": not_break,
                "continue_var": not_continue,
                "have_break": False,
                "have_continue": False,
            }
        )

        payload = self.convert(for_statement.body)
        _iter = for_statement.iter

        loop_control_info = self.loop_control_stack.pop()

        if loop_control_info["have_continue"]:
            reset_continue = ast.NamedExpr(
                target=not_continue, value=ast.Constant(value=True)
            )

            if isinstance(payload, ast.List):
                payload.elts.insert(0, reset_continue)
            else:
                payload = ast.List(elts=[reset_continue, payload])

        if loop_control_info["have_break"] or (self.isfunc and self.have_return):
            # 如果包含break/return
            self.usesing_itertools = True
            not_interrupt = ast.BoolOp(op=ast.And(), values=[])
            if loop_control_info["have_break"]:
                not_interrupt.values.append(not_break)
            if self.isfunc and self.have_return:
                not_interrupt.values.append(self.not_return)
            _iter = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(
                        id="itertools",
                        ctx=ast.Load(),
                    ),
                    attr="takewhile",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg="_")],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=not_interrupt,
                    ),
                    _iter,
                ],
                keywords=[],
            )

        if loop_control_info["have_break"]:  # 如果包含break, 初始化break变量
            out.append(ast.NamedExpr(target=not_break, value=ast.Constant(value=True)))

        for_body = ast.ListComp(
            elt=payload,
            generators=[
                ast.comprehension(
                    target=for_statement.target,
                    iter=_iter,
                    ifs=[],
                    is_async=False,
                )
            ],
        )
        out.append(for_body)

        if for_statement.orelse:  # 处理else
            if loop_control_info["have_break"]:
                orelse = self.convert(
                    [ast.If(test=not_break, body=for_statement.orelse, orelse=[])]
                )
            else:
                orelse = self.convert(for_statement.orelse)
            out.append(orelse)

        return out

    def handle_while(self, while_statement: ast.While) -> list:
        out = []
        self.usesing_itertools = True

        _id = unique_id()
        not_break = ast.Name(id="__ol_not_brk_" + _id)
        not_continue = ast.Name(id="__ol_not_cont_" + _id)

        self.loop_control_stack.append(
            {
                "break_var": not_break,
                "continue_var": not_continue,
                "have_break": False,
                "have_continue": False,
            }
        )

        condition = while_statement.test
        payload = self.convert(while_statement.body)

        loop_control_info = self.loop_control_stack.pop()

        if loop_control_info["have_continue"]:
            reset_continue = ast.NamedExpr(
                target=not_continue, value=ast.Constant(value=True)
            )

            if isinstance(payload, ast.List):
                payload.elts.insert(0, reset_continue)
            else:
                payload = ast.List(elts=[reset_continue, payload])

        if loop_control_info["have_break"]:
            condition = ast.BoolOp(op=ast.And(), values=[not_break, condition])

            out.append(ast.NamedExpr(target=not_break, value=ast.Constant(value=True)))

        if self.isfunc and self.have_return:  # 如果包含return
            condition = ast.BoolOp(op=ast.And(), values=[self.not_return, condition])

        out.append(template_while(payload, condition))

        if while_statement.orelse:  # 处理else
            if loop_control_info["have_break"]:
                orelse = self.convert(
                    [ast.If(test=not_break, body=while_statement.orelse, orelse=[])]
                )
            else:
                orelse = self.convert(while_statement.orelse)
            out.append(orelse)
        return out

    def handle_assign(self, assign: ast.Assign) -> list:
        out = []
        _target = assign.targets[0]

        if isinstance(_target, ast.Tuple):
            tmp_variable_name = "__ol_assign_tmp_" + unique_id()

            assign_to_tmp = ast.NamedExpr(
                target=ast.Name(id=tmp_variable_name, ctx=ast.Store()),
                value=assign.value,
            )
            out.append(assign_to_tmp)

            for ind, single_target in enumerate(_target.elts):
                value = ast.Subscript(
                    value=ast.Name(id=tmp_variable_name, ctx=ast.Load()),
                    slice=ast.Constant(value=ind),
                    ctx=ast.Load(),
                )
                single_assign = template_auto_assign(single_target, value)
                out.append(single_assign)

        else:
            out.append(template_auto_assign(_target, assign.value))
        return out

    def handle_aug_assign(self, assign: ast.AugAssign) -> list:
        _op_dict = {
            ast.Add: "__iadd__",
            ast.BitAnd: "__iand__",
            ast.FloorDiv: "__ifloordiv__",
            ast.LShift: "__ilshift__",
            ast.Mod: "__imod__",
            ast.Mult: "__imul__",
            ast.MatMult: "__imatmul__",
            ast.BitOr: "__ior__",
            ast.Pow: "__ipow__",
            ast.RShift: "__irshift__",
            ast.Sub: "__isub__",
            ast.Div: "__itruediv__",
            ast.BitXor: "__ixor__",
        }
        i_op_name = _op_dict[type(assign.op)]

        orelse_op = ast.BinOp(left=assign.target, op=assign.op, right=assign.value)
        orelse = template_auto_assign(assign.target, orelse_op)

        out = ast.Expr(
            value=ast.IfExp(
                test=ast.Call(
                    func=ast.Name(
                        id="hasattr",
                        ctx=ast.Load(),
                    ),
                    args=[assign.target, ast.Constant(value=i_op_name)],
                    keywords=[],
                ),
                body=ast.Call(
                    func=ast.Attribute(
                        value=assign.target,
                        attr=i_op_name,
                        ctx=ast.Load(),
                    ),
                    args=[assign.value],
                    keywords=[],
                ),
                orelse=orelse,
            )
        )
        return [out]

    def handle_ann_assign(self, assign: ast.AnnAssign) -> list:
        out = []
        if assign.value is not None:
            out.append(ast.NamedExpr(assign.target, assign.value))
        return out

    def handle_if(self, if_statement: ast.If) -> list:
        body = self.convert(if_statement.body)
        orelse = self.convert(if_statement.orelse)
        return [ast.IfExp(if_statement.test, body, orelse)]

    def handle_import(self, import_statement: ast.Import) -> list:
        # Example:
        # import pygame._sdl2.video as vvv
        #      ↓↓↓↓↓↓↓↓↓↓↓↓↓
        # (vvv := __import__('pygame._sdl2.video')._sdl2.video)

        for alias in import_statement.names:
            _import = ast.Call(
                func=ast.Name(id="__import__", ctx=ast.Load()),
                args=[ast.Constant(alias.name)],
                keywords=[],
            )

            module_path_list = alias.name.split(".")
            if alias.asname is None:
                _name = ast.Name(id=module_path_list[0], ctx=ast.Store())
            else:
                _name = ast.Name(id=alias.asname, ctx=ast.Store())
                if len(module_path_list) > 1:
                    _import = ast.Attribute(
                        value=_import,
                        attr=".".join(module_path_list[1:]),
                        ctx=ast.Store(),
                    )

            return [ast.NamedExpr(target=_name, value=_import)]

    def handle_def(self, def_statement: ast.FunctionDef) -> list:
        arg_remove_annotation(def_statement.args)

        converter = Converter(isfunc=True)
        converter.set_filename(self.filename)
        function_body = ast.Lambda(
            args=def_statement.args,
            body=converter.convert(def_statement.body, top_level=True),
        )
        if converter.usesing_itertools:
            self.usesing_itertools = True
        for dec in def_statement.decorator_list[::-1]:  # handle decorators
            function_body = ast.Call(
                func=dec,
                args=[function_body],
                keywords=[],
            )
        return [
            ast.NamedExpr(
                target=ast.Name(
                    id=def_statement.name,
                    ctx=ast.Store(),
                ),
                value=function_body,
            )
        ]

    def handle_break(self, break_statement: ast.Break) -> list:
        self.loop_control_stack[-1]["have_break"] = True  # have break
        self.loop_control_stack[-1]["have_continue"] = True  # break includes continue

        return [
            ast.NamedExpr(
                target=self.loop_control_stack[-1]["continue_var"],
                value=ast.Constant(value=False),
            ),
            ast.NamedExpr(
                target=self.loop_control_stack[-1]["break_var"],
                value=ast.Constant(value=False),
            ),
        ]

    def handle_continue(self, continue_statement: ast.Continue) -> list:
        self.loop_control_stack[-1]["have_continue"] = True  # have continue

        return [
            ast.NamedExpr(
                target=self.loop_control_stack[-1]["continue_var"],
                value=ast.Constant(value=False),
            )
        ]

    def handle_return(self, return_statement: ast.Return) -> list:
        self.have_return = True
        return_value = return_statement.value
        if return_value is None:
            return_value = ast.Constant(value=None)
        return [
            ast.NamedExpr(target=self.not_return, value=ast.Constant(value=False)),
            ast.NamedExpr(target=self.return_value, value=return_value),
        ]

    def handle_pass(self, pass_statement: ast.Pass) -> list:
        return []

    def handle_expr(self, expr: ast.Expr) -> list:
        return [expr]

    def handle_global(self, global_statement: ast.Global) -> list:
        if not self.isfunc:
            return []
        for name in global_statement.names:
            if name in self.names:
                raise SyntaxError(
                    f"Invalid Syntax.\n"
                    f'File "{self.filename}", line {global_statement.lineno}\n'
                    f"    Name '{name}' is used prior to global declaration."
                )
            self.global_names.add(name)
        return []

    def convert(self, nodes: list[ast.AST], top_level: bool = False) -> ast.AST:
        out = []

        for node_index, node in enumerate(nodes):
            if type(node) not in self.node_handler_map:
                raise ConvertError(
                    f"Convert failed.\n"
                    f'File "{self.filename}", line {node.lineno}\n'
                    f'    Statement "{type(node).__name__}" is not convertable.'
                )

            # Handle AST node
            converted_list = self.node_handler_map[type(node)](node)
            self.update_names(converted_list)
            out.extend(converted_list)

            if type(node) in [ast.Continue, ast.Break, ast.Return]:
                break

            if nodes[node_index + 1 :] and type(node) in [ast.For, ast.While, ast.If]:
                # 如果在分支之后还有语句
                # 且在分支中有continue/break/return
                # 则判断是否中断，再执行

                interrupt_list = []

                if (
                    isinstance(node, ast.If)
                    and len(self.loop_control_stack)
                    and self.loop_control_stack[-1]["have_continue"]
                ):
                    interrupt_list.append(self.loop_control_stack[-1]["continue_var"])

                if self.isfunc and self.have_return:
                    interrupt_list.append(self.not_return)

                if interrupt_list:
                    if len(interrupt_list) == 1:
                        interrupt_check = interrupt_list[0]
                    else:
                        interrupt_check = ast.BoolOp(
                            op=ast.And(),
                            values=interrupt_list,
                        )

                    check_interrupt_expr = ast.IfExp(
                        test=interrupt_check,
                        body=self.convert(nodes[node_index + 1 :]),
                        orelse=ast.Constant(value=None),
                    )
                    out.append(check_interrupt_expr)
                    break

        if top_level:
            if self.isfunc:
                if self.have_return:
                    _not_return_assign = ast.NamedExpr(
                        target=self.not_return,
                        value=ast.Constant(value=True),
                    )
                    _return_value_assign = ast.NamedExpr(
                        target=self.return_value,
                        value=ast.Constant(value=None),
                    )
                    out.insert(0, _not_return_assign)
                    out.insert(0, _return_value_assign)

                    out.append(self.return_value)
                else:
                    out.append(ast.Constant(value=None))

                out = [
                    ast.Subscript(
                        value=ast.List(elts=out),
                        slice=ast.Constant(value=-1),
                    )
                ]

            elif self.usesing_itertools:
                itertools_import = ast.NamedExpr(
                    target=ast.Name(id="itertools", ctx=ast.Store()),
                    value=ast.Call(
                        func=ast.Name(id="__import__", ctx=ast.Load()),
                        args=[ast.Constant(value="itertools")],
                        keywords=[],
                    ),
                )
                out.insert(0, itertools_import)

        # Optimize output
        if len(out) == 0:
            out_node = ast.Constant(value=None)
        elif len(out) == 1:
            out_node = out[0]
        else:
            out_node = ast.List(elts=out)

        return out_node


def convert_code_string(code: str, filename: Optional[str] = None) -> str:
    c = Converter()
    if filename is not None:
        c.set_filename(os.path.abspath(filename))
    return ast.unparse(
        c.convert(ast.parse(code).body, top_level=True),
    ).replace("\n", "")


__all__ = ["ConvertError", "Converter", "convert_code_string"]

if __name__ == "__main__":
    import sys
    import os

    output_file_name = ""
    help_text = """Usage: oneliner.py [input file] [param [param option]] ...
Options:
    -h               -> get help info.
    -o [output path] -> set output script path
"""

    argv = sys.argv[1:]

    def parse_param(param: str, has_option: bool = True):
        if param not in argv:
            return (False, "")
        index = argv.index(param)
        if not has_option:
            argv.pop(index)
            return (True, "")
        if index < len(argv) - 1:
            option = argv[index + 1]
            argv.pop(index)
            argv.pop(index)
            return (True, option)
        return (False, "")

    has_param, data = parse_param("-h", has_option=False)
    if has_param:
        print(help_text)
        sys.exit(0)

    has_param, data = parse_param("-o")
    if has_param:
        output_file_name = data

    if len(argv) == 0:
        print("Error: No input file.")
        print(help_text)
        sys.exit(1)

    if not os.path.isfile(argv[0]):
        print("Error: Invalid input script path %s." % argv[0])
        sys.exit(1)
    input_file_name = argv[0]

    with open(input_file_name, "r", encoding="utf8") as input_file:
        script = input_file.read()

    result = convert_code_string(script, filename=input_file_name)

    if output_file_name:
        with open(output_file_name, "w", encoding="utf8") as output_file:
            print(result, file=output_file)
    else:
        print(result)
    print("Script generated successfully.")
