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

    def convert(self, body: list, recursion: int = 0):
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

        def handle_while(while_statement: ast.While):
            global usesing_itertools
            usesing_itertools = True

            _id = unique_id()
            not_break = ast.Name(id="__ol_not_brk_" + _id)
            not_continue = ast.Name(id="__ol_not_cont_" + _id)
            # 中断指示器入栈
            self.loop_control_stack.append([not_break, not_continue, False, False])

            condition = while_statement.test
            payload = self.convert(while_statement.body, recursion + 1)

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

                out_node.elts.append(
                    ast.NamedExpr(target=not_break, value=ast.Constant(value=True))
                )

            if self.isfunc and self.have_return:  # 如果包含return
                condition = ast.BoolOp(
                    op=ast.And(), values=[self.not_return, condition]
                )

            out = ast.ListComp(
                elt=payload,
                generators=[
                    ast.comprehension(
                        target=ast.Name(id="_"),
                        iter=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="itertools"), attr="takewhile"
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
                                    body=condition,
                                ),
                                ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id="itertools"), attr="count"
                                    ),
                                    args=[],
                                    keywords=[],
                                ),
                            ],
                            keywords=[],
                        ),
                        ifs=[],
                        is_async=0,
                    )
                ],
            )
            out_node.elts.append(out)

            if while_statement.orelse:
                if indicator[2]:  # if have break
                    orelse = self.convert(
                        [
                            ast.If(
                                test=not_break, body=while_statement.orelse, orelse=[]
                            )
                        ],
                        recursion + 1,
                    )
                else:
                    orelse = self.convert(while_statement.orelse, recursion + 1)
                out_node.elts.append(orelse)

        def handle_assign(assign: ast.Assign):
            _target = assign.targets[0]

            if isinstance(_target, ast.Name):
                out_node.elts.append(ast.NamedExpr(_target, assign.value))
            elif isinstance(_target, ast.Tuple):
                tmp_variable_name = "__ol_assign_tmp_" + unique_id()
                out = ast.List(
                    elts=[
                        ast.NamedExpr(
                            target=ast.Name(id=tmp_variable_name), value=assign.value
                        )
                    ],
                )
                for n, target in enumerate(_target.elts):
                    single_assign = ast.NamedExpr(
                        target=target,
                        value=ast.Subscript(
                            value=ast.Name(id=tmp_variable_name),
                            slice=ast.Constant(value=n),
                        ),
                    )
                    out.elts.append(single_assign)
                out_node.elts.append(out)
            else:
                raise ConvertError("Unknown assign type at line %d" % assign.lineno)

        def handle_aug_assign(assign: ast.AugAssign):
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
                    orelse=ast.NamedExpr(
                        target=assign.target,
                        value=ast.BinOp(
                            left=assign.target, op=assign.op, right=assign.value
                        ),
                    ),
                )
            )
            out_node.elts.append(out)

        def handle_for(for_statement: ast.For):
            global usesing_itertools
            _id = unique_id()
            not_break = ast.Name(id="__ol_not_brk_" + _id)
            not_continue = ast.Name(id="__ol_not_cont_" + _id)
            # 中断指示器入栈
            self.loop_control_stack.append([not_break, not_continue, False, False])

            payload = self.convert(for_statement.body, recursion + 1)
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

            if indicator[2] or (self.isfunc and self.have_return):  # 如果包含break/return
                usesing_itertools = True
                not_interrupt = ast.BoolOp(op=ast.And(), values=[])
                if indicator[2]:
                    not_interrupt.values.append(not_break)
                if self.isfunc and self.have_return:
                    not_interrupt.values.append(self.not_return)
                _iter = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="itertools"), attr="takewhile"
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

            if indicator[2]:  # 如果包含break, 初始化break变量
                out_node.elts.append(
                    ast.NamedExpr(target=not_break, value=ast.Constant(value=True))
                )

            out = ast.ListComp(
                elt=payload,
                generators=[
                    ast.comprehension(
                        target=for_statement.target, iter=_iter, ifs=[], is_async=False
                    )
                ],
            )
            out_node.elts.append(out)

            if for_statement.orelse:
                if indicator[2]:  # if have break
                    orelse = self.convert(
                        [ast.If(test=not_break, body=for_statement.orelse, orelse=[])],
                        recursion + 1,
                    )
                else:
                    orelse = self.convert(for_statement.orelse, recursion + 1)
                out_node.elts.append(orelse)

        def handle_import(import_statement: ast.Import):
            name_list = [alias.name for alias in import_statement.names]
            asname_list = [
                alias.asname if not alias.asname is None else alias.name
                for alias in import_statement.names
            ]

            for n, asname in enumerate(asname_list):
                out = ast.NamedExpr(
                    target=ast.Name(asname),
                    value=ast.Call(
                        func=ast.Name("__import__"),
                        args=[ast.Constant(name_list[n])],
                        keywords=[],
                    ),
                )
                out_node.elts.append(out)

        def handle_if(if_statement: ast.If):
            body = self.convert(if_statement.body, recursion + 1)
            orelse = self.convert(if_statement.orelse, recursion + 1)
            out = ast.IfExp(if_statement.test, body, orelse)
            out_node.elts.append(out)

        def handle_continue():
            self.loop_control_stack[-1][3] = True  # have continue
            out_node.elts.append(
                ast.NamedExpr(
                    target=self.loop_control_stack[-1][1],
                    value=ast.Constant(value=False),
                )
            )

        def handle_break():
            self.loop_control_stack[-1][2] = True  # have break
            self.loop_control_stack[-1][3] = True  # break includes continue
            out_node.elts.append(
                ast.NamedExpr(
                    target=self.loop_control_stack[-1][1],
                    value=ast.Constant(value=False),
                )
            )
            out_node.elts.append(
                ast.NamedExpr(
                    target=self.loop_control_stack[-1][0],
                    value=ast.Constant(value=False),
                )
            )

        def handle_def(def_statement: ast.FunctionDef):
            converter = Converter(isfunc=True)
            out = ast.NamedExpr(
                target=ast.Name(id=def_statement.name),
                value=ast.Lambda(
                    args=def_statement.args,
                    body=converter.convert(def_statement.body, 0),
                ),
            )
            out_node.elts.append(out)

        def handle_return(return_statement: ast.Return):
            self.have_return = True
            out_node.elts.append(
                ast.NamedExpr(target=self.not_return, value=ast.Constant(value=False))
            )

            out_node.elts.append(
                ast.NamedExpr(target=self.return_value, value=return_statement.value)
            )

        def post_process(out_node):  # Output optimization
            if len(out_node.elts) == 0:
                out_node = ast.Expr(value=ast.Constant(value=None))
            elif len(out_node.elts) == 1:
                out_node = out_node.elts[0]
            return out_node

        for n_body, node in enumerate(body):
            if isinstance(node, ast.Expr):
                out_node.elts.append(node)
            elif isinstance(node, ast.For):
                handle_for(node)
            elif isinstance(node, ast.If):
                handle_if(node)
            elif isinstance(node, ast.Pass):
                pass
            elif isinstance(node, ast.Assign):
                handle_assign(node)
            elif isinstance(node, ast.AnnAssign):
                out_node.elts.append(ast.NamedExpr(node.target, node.value))
            elif isinstance(node, ast.AugAssign):
                handle_aug_assign(node)
            elif isinstance(node, ast.Import):
                handle_import(node)
            elif isinstance(node, ast.While):
                handle_while(node)
            elif isinstance(node, ast.Continue):
                handle_continue()
                break  # 中断
            elif isinstance(node, ast.Break):
                handle_break()
                break
            elif isinstance(node, ast.Return):
                handle_return(node)
                break
            elif isinstance(node, ast.FunctionDef):
                handle_def(node)
            else:
                raise ConvertError(
                    'Convert failed.\nError: "%s", line %d, Statement "%s" is not convertable.'
                    % (filename, node.lineno, type(node).__name__)
                )

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
                            body=self.convert(body[n_body + 1 :], recursion + 1),
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
                                body=self.convert(body[n_body + 1 :], recursion + 1),
                                orelse=ast.Constant(value=None),
                            )
                        )
                    break

        if recursion == 0:
            if self.isfunc:
                if self.have_return:
                    out_node.elts.insert(
                        0,
                        ast.NamedExpr(
                            target=self.not_return, value=ast.Constant(value=True)
                        ),
                    )

                out_node.elts.insert(
                    0,
                    ast.NamedExpr(
                        target=self.return_value, value=ast.Constant(value=None)
                    ),
                )

                out_node = ast.List(
                    elts=[
                        ast.Expr(
                            value=ast.Subscript(
                                value=ast.List(elts=[out_node, self.return_value]),
                                slice=ast.Constant(value=-1),
                            )
                        )
                    ]
                )

            elif usesing_itertools:
                inject_itertools()

        out_node = post_process(out_node)

        return out_node


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
        if not param in argv:
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

    main_body = ast.parse(script)
    c = Converter()
    result = ast.unparse(c.convert(main_body.body)).replace("\n", "")

    if output_file_name:
        with open(output_file_name, "w", encoding="utf8") as output_file:
            print(result, file=output_file)
    else:
        print(result)
    print("Script generated successfully.")
