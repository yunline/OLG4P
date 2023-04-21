import ast
import random

random.seed(12345)

usesing_itertools = False
filename = "<string>"


class ConvertError(Exception):
    pass


unique_id_set = {""}


def unique_id():
    uid = ""
    while uid in unique_id_set:
        uid = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for i in range(10))
    return uid


class Converter:
    def __init__(self, isfunc=False):
        self.isfunc = isfunc
        self.loop_control_stack = []
        # [[break_obj, continue_obj, have_break, have_continue], ...]
        if isfunc:
            _id = unique_id()
            self.not_return = ast.Name(id="__ol_not_return_" + _id)
            self.return_value = ast.Name(id="__ol_return_value_" + _id)
            self.have_return = False

    @staticmethod
    def template_subscript_assign(target: ast.Subscript, value) -> ast.AST:
        _slice = target.slice
        if isinstance(target.slice, ast.Slice):
            _slice = ast.Call(func=ast.Name(id="slice"), args=[], keywords=[])
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
            func=ast.Attribute(value=target.value, attr="__setitem__"),
            args=[_slice, value],
            keywords=[],
        )
        return out

    @staticmethod
    def template_attribute_assign(target: ast.Attribute, value) -> ast.AST:
        out = ast.Call(
            func=ast.Attribute(value=target.value, attr="__setattr__"),
            args=[ast.Constant(value=target.attr), value],
            keywords=[],
        )
        return out

    def template_auto_assign(self, target, value) -> ast.AST:
        if isinstance(target, ast.Name):
            out = ast.NamedExpr(target=target, value=value)
        elif isinstance(target, ast.Subscript):
            out = self.template_subscript_assign(target, value)
        elif isinstance(target, ast.Attribute):
            out = self.template_attribute_assign(target, value)
        else:
            raise ConvertError("Unknown assign type")

        return out

    @staticmethod
    def template_while(payload, condition) -> ast.AST:
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
                func=ast.Attribute(value=ast.Name(id="itertools"), attr="count"),
                args=[],
                keywords=[],
            ),
        ]
        out = ast.ListComp(
            elt=payload,
            generators=[
                ast.comprehension(
                    target=ast.Name(id="_"),
                    iter=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="itertools"), attr="takewhile"
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

    @staticmethod
    def arg_remove_annotation(arg: ast.arguments) -> None:
        # Warning: In place operation
        if arg.vararg is not None:
            arg.vararg.annotation = None
        if arg.kwarg is not None:
            arg.kwarg.annotation = None
        for args in [arg.posonlyargs, arg.args, arg.kwonlyargs]:
            for _arg in args:
                _arg.annotation = None

    def handle_for(self, for_statement: ast.For) -> list:
        out = []
        global usesing_itertools

        _id = unique_id()
        not_break = ast.Name(id="__ol_not_brk_" + _id)
        not_continue = ast.Name(id="__ol_not_cont_" + _id)
        # 中断指示器入栈
        self.loop_control_stack.append([not_break, not_continue, False, False])

        payload = self.convert(for_statement.body)
        _iter = for_statement.iter

        indicator = self.loop_control_stack.pop()  # 弹出中断指示器

        if indicator[3]:  # 如果包含continue/break
            reset_continue = ast.NamedExpr(
                target=not_continue, value=ast.Constant(value=True)
            )

            if isinstance(payload, ast.List):
                payload.elts.insert(0, reset_continue)
            else:
                payload = ast.List(elts=[reset_continue, payload])

        if indicator[2] or (self.isfunc and self.have_return):
            # 如果包含break/return
            usesing_itertools = True
            not_interrupt = ast.BoolOp(op=ast.And(), values=[])
            if indicator[2]:
                not_interrupt.values.append(not_break)
            if self.isfunc and self.have_return:
                not_interrupt.values.append(self.not_return)
            _iter = ast.Call(
                func=ast.Attribute(value=ast.Name(id="itertools"), attr="takewhile"),
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

        if indicator[2]:  # 如果包含break, 初始化break变量
            out.append(ast.NamedExpr(target=not_break, value=ast.Constant(value=True)))

        for_body = ast.ListComp(
            elt=payload,
            generators=[
                ast.comprehension(
                    target=for_statement.target, iter=_iter, ifs=[], is_async=False
                )
            ],
        )
        out.append(for_body)

        if for_statement.orelse:
            if indicator[2]:  # if have break
                orelse = self.convert(
                    [ast.If(test=not_break, body=for_statement.orelse, orelse=[])]
                )
            else:
                orelse = self.convert(for_statement.orelse)
            out.append(orelse)

        return out

    def handle_while(self, while_statement: ast.While) -> list:
        out = []
        global usesing_itertools
        usesing_itertools = True

        _id = unique_id()
        not_break = ast.Name(id="__ol_not_brk_" + _id)
        not_continue = ast.Name(id="__ol_not_cont_" + _id)
        # 中断指示器入栈
        self.loop_control_stack.append([not_break, not_continue, False, False])

        condition = while_statement.test
        payload = self.convert(while_statement.body)

        indicator = self.loop_control_stack.pop()  # 弹出中断指示器

        if indicator[3]:  # 如果包含continue/break
            reset_continue = ast.NamedExpr(
                target=not_continue, value=ast.Constant(value=True)
            )

            if isinstance(payload, ast.List):
                payload.elts.insert(0, reset_continue)
            else:
                payload = ast.List(elts=[reset_continue, payload])

        if indicator[2]:  # 如果包含break
            condition = ast.BoolOp(op=ast.And(), values=[not_break, condition])

            out.append(ast.NamedExpr(target=not_break, value=ast.Constant(value=True)))

        if self.isfunc and self.have_return:  # 如果包含return
            condition = ast.BoolOp(op=ast.And(), values=[self.not_return, condition])

        out.append(self.template_while(payload, condition))

        if while_statement.orelse:
            if indicator[2]:  # if have break
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

            out.append(
                ast.NamedExpr(target=ast.Name(id=tmp_variable_name), value=assign.value)
            )

            for n, single_target in enumerate(_target.elts):
                value = ast.Subscript(
                    value=ast.Name(id=tmp_variable_name),
                    slice=ast.Constant(value=n),
                )
                single_assign = self.template_auto_assign(single_target, value)
                out.append(single_assign)

        else:
            try:
                out.append(self.template_auto_assign(_target, assign.value))
            except ConvertError:
                raise ConvertError("Unknown assign type at line %d" % assign.lineno)
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
        orelse = self.template_auto_assign(assign.target, orelse_op)

        out = ast.Expr(
            value=ast.IfExp(
                test=ast.Call(
                    func=ast.Name(id="hasattr"),
                    args=[assign.target, ast.Constant(value=i_op_name)],
                    keywords=[],
                ),
                body=ast.Call(
                    func=ast.Attribute(value=assign.target, attr=i_op_name),
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
                func=ast.Name("__import__"),
                args=[ast.Constant(alias.name)],
                keywords=[],
            )

            module_path_list = alias.name.split(".")
            if alias.asname is None:
                _name = ast.Name(module_path_list[0])
            else:
                _name = ast.Name(alias.asname)
                if len(module_path_list) > 1:
                    _import = ast.Attribute(
                        value=_import, attr=".".join(module_path_list[1:])
                    )

            return [ast.NamedExpr(target=_name, value=_import)]

    def handle_def(self, def_statement: ast.FunctionDef) -> list:
        self.arg_remove_annotation(def_statement.args)

        converter = Converter(isfunc=True)
        function_body = ast.Lambda(
            args=def_statement.args,
            body=converter.convert(def_statement.body, top_level=True),
        )
        for dec in def_statement.decorator_list[::-1]:  # handle decorators
            function_body = ast.Call(
                func=dec,
                args=[function_body],
                keywords=[],
            )
        return [
            ast.NamedExpr(
                target=ast.Name(id=def_statement.name),
                value=function_body,
            )
        ]

    def handle_break(self, break_statement: ast.Break) -> list:
        self.loop_control_stack[-1][2] = True  # have break
        self.loop_control_stack[-1][3] = True  # break includes continue

        return [
            ast.NamedExpr(
                target=self.loop_control_stack[-1][1],
                value=ast.Constant(value=False),
            ),
            ast.NamedExpr(
                target=self.loop_control_stack[-1][0],
                value=ast.Constant(value=False),
            ),
        ]

    def handle_continue(self, continue_statement: ast.Continue) -> list:
        self.loop_control_stack[-1][3] = True  # have continue

        return [
            ast.NamedExpr(
                target=self.loop_control_stack[-1][1],
                value=ast.Constant(value=False),
            )
        ]

    def handle_return(self, return_statement: ast.Return) -> list:
        self.have_return = True
        return [
            ast.NamedExpr(target=self.not_return, value=ast.Constant(value=False)),
            ast.NamedExpr(target=self.return_value, value=return_statement.value),
        ]

    def handle_pass(self, pass_statement: ast.Pass) -> list:
        return []

    def handle_expr(self, expr: ast.Expr) -> list:
        return [expr]

    def convert(self, body: list, top_level=False):
        out_node = ast.List([])

        def inject_itertools():
            out_node.elts.insert(
                0,
                ast.NamedExpr(
                    target=ast.Name(id="itertools"),
                    value=ast.Call(
                        func=ast.Name(id="__import__"),
                        args=[ast.Constant(value="itertools")],
                        keywords=[],
                    ),
                ),
            )

        def post_process(out_node):  # Output optimization
            if len(out_node.elts) == 0:
                out_node = ast.Expr(value=ast.Constant(value=None))
            elif len(out_node.elts) == 1:
                out_node = out_node.elts[0]
            return out_node

        for n_body, node in enumerate(body):
            if isinstance(node, ast.Expr):
                out_node.elts.extend(self.handle_expr(node))
            elif isinstance(node, ast.For):
                out_node.elts.extend(self.handle_for(node))
            elif isinstance(node, ast.If):
                out_node.elts.extend(self.handle_if(node))
            elif isinstance(node, ast.Pass):
                out_node.elts.extend(self.handle_pass(node))
            elif isinstance(node, ast.Assign):
                out_node.elts.extend(self.handle_assign(node))
            elif isinstance(node, ast.AnnAssign):
                out_node.elts.extend(self.handle_ann_assign(node))
            elif isinstance(node, ast.AugAssign):
                out_node.elts.extend(self.handle_aug_assign(node))
            elif isinstance(node, ast.Import):
                out_node.elts.extend(self.handle_import(node))
            elif isinstance(node, ast.While):
                out_node.elts.extend(self.handle_while(node))
            elif isinstance(node, ast.FunctionDef):
                out_node.elts.extend(self.handle_def(node))
            elif isinstance(node, ast.Continue):
                out_node.elts.extend(self.handle_continue(node))
            elif isinstance(node, ast.Break):
                out_node.elts.extend(self.handle_break(node))
            elif isinstance(node, ast.Return):
                out_node.elts.extend(self.handle_return(node))
            else:
                raise ConvertError(
                    'Convert failed.\nError: "%s", '
                    'line %d, Statement "%s" is not convertable.'
                    % (filename, node.lineno, type(node).__name__)
                )

            if type(node) in [ast.Continue, ast.Break, ast.Return]:
                break

            if body[n_body + 1 :]:
                # 如果在分支中有continue/break/return且之后还有语句
                # 则判断是否中断，再执行
                if (
                    isinstance(node, ast.If)
                    and self.loop_control_stack
                    and self.loop_control_stack[-1][3]
                ):
                    out_node.elts.append(
                        ast.IfExp(
                            test=self.loop_control_stack[-1][1],
                            body=self.convert(body[n_body + 1 :]),
                            orelse=ast.Constant(value=None),
                        )
                    )
                    if not self.isfunc:
                        break
                if self.isfunc and type(node) in [ast.For, ast.While, ast.If]:
                    if self.have_return:
                        out_node.elts.append(
                            ast.IfExp(
                                test=self.not_return,
                                body=self.convert(body[n_body + 1 :]),
                                orelse=ast.Constant(value=None),
                            )
                        )
                    break

        if top_level:
            if self.isfunc:
                if self.have_return:
                    # inject not_return and return_value
                    _not_return_assign = ast.NamedExpr(
                        target=self.not_return, value=ast.Constant(value=True)
                    )
                    _return_value_assign = ast.NamedExpr(
                        target=self.return_value, value=ast.Constant(value=None)
                    )
                    out_node.elts.insert(0, _not_return_assign)
                    out_node.elts.insert(0, _return_value_assign)

                    # set the return value to return_value
                    out_node.elts.append(self.return_value)
                else:
                    # set the return value to None
                    out_node.elts.append(ast.Constant(value=None))

                out_node = ast.List(
                    elts=[
                        ast.Subscript(
                            value=out_node,
                            slice=ast.Constant(value=-1),
                        )
                    ]
                )

            elif usesing_itertools:
                inject_itertools()

        out_node = post_process(out_node)

        return out_node


def convert_code_string(code: str):
    c = Converter()
    return ast.unparse(c.convert(ast.parse(code).body, top_level=True)).replace(
        "\n", ""
    )


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

    def parse_param(param, has_option=True):
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
    filename = input_file_name

    with open(input_file_name, "r", encoding="utf8") as input_file:
        script = input_file.read()

    result = convert_code_string(script)

    if output_file_name:
        with open(output_file_name, "w", encoding="utf8") as output_file:
            print(result, file=output_file)
    else:
        print(result)
    print("Script generated successfully.")
