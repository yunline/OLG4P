import ast
import random
random.seed(12345)

usesing_itertools=False
filename='<string>'

class ConvertError(Exception):
    pass

unique_id_set={''}
def unique_id():
    uid=''
    while uid in unique_id_set:
        uid=''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for i in range(10))
    return uid
                    
loop_control_stack=[]
# [[break_obj, continue_obj, have_break, have_continue], ...]

def convert(body: list,recursion: int=0):
    out_node=ast.List([])

    def inject_itertools():
        out_node.elts.insert(0,ast.NamedExpr(
            target=ast.Name(id='itertools'),  
            value=ast.Call(
                func=ast.Name(id='__import__'),
                args=[
                    ast.Constant(value='itertools')],      
                keywords=[])))
    
    def handle_while(while_statement:ast.While):
        global usesing_itertools
        usesing_itertools=True

        _id=unique_id()
        not_break=ast.Name(id='__ol_not_brk_'+_id)
        not_continue=ast.Name(id='__ol_not_cont_'+_id)
        # 中断指示器入栈
        loop_control_stack.append([not_break,not_continue,False,False])

        condition=while_statement.test
        payload=convert(while_statement.body,recursion+1)
        orelse=convert(while_statement.orelse,recursion+1)
        
        if loop_control_stack[-1][3]: # 如果包含continue
            reset_continue=ast.NamedExpr(
                target=not_continue,
                value=ast.Constant(value=True))

            if isinstance(payload,ast.List):
                payload.elts.insert(0,reset_continue)
            else:
                payload=ast.List(elts=[reset_continue,payload])

        if loop_control_stack[-1][2]: # 如果包含break
            condition=ast.BoolOp(
                op=ast.And(),
                values=[not_break,condition])
            
            out_node.elts.append(
                ast.NamedExpr(
                    target=not_break,
                    value=ast.Constant(value=True)))
        
        loop_control_stack.pop() # 弹出中断指示器
    
        out=ast.ListComp(
            elt=payload,
            generators=[
                ast.comprehension(
                    target=ast.Name(id='_'),
                    iter=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='itertools'),
                            attr='takewhile'),
                        args=[
                            ast.Lambda(
                                args=ast.arguments(
                                    posonlyargs=[],
                                    args=[ast.arg(arg='_')],
                                    kwonlyargs=[],
                                    kw_defaults=[],
                                    defaults=[]),
                                body=condition),
                            ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id='itertools'),
                                    attr='count'),
                                args=[],
                                keywords=[])],
                        keywords=[]),
                    ifs=[],
                    is_async=0)])

        out_node.elts.append(out)

    def handle_assign(assign:ast.Assign):
        _target=assign.targets[0]
        if type(_target)==ast.Name:
            out_node.elts.append(ast.NamedExpr(_target,assign.value))
        elif type(_target)==ast.Tuple:
            tmp_variable_name='__ol_assign_tmp_'+unique_id()
            out=ast.List(elts=[        
                ast.NamedExpr(
                    target=ast.Name(id=tmp_variable_name),
                    value=assign.value)],)
            for n,target in enumerate(_target.elts):
                single_assign=ast.NamedExpr(
                    target=target,
                    value=ast.Subscript(
                        value=ast.Name(id=tmp_variable_name),
                        slice=ast.Constant(value=n)))
                out.elts.append(single_assign)
            out_node.elts.append(out)
        else:
            raise Exception('Unknown assign type')       

    def handle_aug_assign(assign:ast.AugAssign):
        _op_dict={
            ast.Add:'__iadd__',
            ast.BitAnd:'__iand__',
            ast.FloorDiv:'__ifloordiv__',
            ast.LShift:'__ilshift__',
            ast.Mod:'__imod__',
            ast.Mult:'__imul__',
            ast.MatMult:'__imatmul__',
            ast.BitOr:'__ior__',
            ast.Pow:'__ipow__',
            ast.RShift:'__irshift__',
            ast.Sub:'__isub__',
            ast.Div:'__itruediv__',
            ast.BitXor:'__ixor__'
        }
        i_op_name=_op_dict[type(assign.op)]
        out = ast.Expr(
            value=ast.IfExp(
                test=ast.Call(
                    func=ast.Name(id='hasattr'),
                    args=[assign.target,
                        ast.Constant(value=i_op_name)],
                    keywords=[]),
                body=ast.Call(
                    func=ast.Attribute(
                        value=assign.target,
                        attr=i_op_name),
                    args=[assign.value],
                    keywords=[]),
                orelse=ast.NamedExpr(
                    target=assign.target,
                    value=ast.BinOp(
                        left=assign.target,
                        op=assign.op,
                        right=assign.value))))
        out_node.elts.append(out)

    def handle_for(for_statement:ast.For):
        _id=unique_id()
        not_break=ast.Name(id='__ol_not_brk_'+_id)
        not_continue=ast.Name(id='__ol_not_cont_'+_id)
        # 中断指示器入栈
        loop_control_stack.append([not_break,not_continue,False,False])

        payload=convert(node.body,recursion+1)
        _iter=node.iter

        if loop_control_stack[-1][3]: # 如果包含continue
            global usesing_itertools
            usesing_itertools=True
            reset_continue=ast.NamedExpr(
                target=not_continue,
                value=ast.Constant(value=True))

            if isinstance(payload,ast.List):
                payload.elts.insert(0,reset_continue)
            else:
                payload=ast.List(elts=[reset_continue,payload])

        if loop_control_stack[-1][2]: # 如果包含break
            _iter=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='itertools'),
                    attr='takewhile'),
                args=[
                    ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[
                                ast.arg(arg='_')],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[]),
                        body=not_break),
                    _iter],
                keywords=[])
            
            out_node.elts.append(
                ast.NamedExpr(
                    target=not_break,
                    value=ast.Constant(value=True)))
        
        loop_control_stack.pop() # 弹出中断指示器

        out=ast.ListComp(
            elt=payload,
            generators=[
                ast.comprehension(
                    target=node.target,
                    iter=_iter,
                    ifs=[],
                    is_async=False)])
        out_node.elts.append(out)

    def handle_import(import_statement:ast.Import):
        name_list=[alias.name for alias in node.names]
        asname_list=[alias.asname if not alias.asname is None
            else alias.name for alias in node.names]

        for n,asname in enumerate(asname_list):
            out=ast.NamedExpr(
                target=ast.Name(asname),
                value=ast.Call(
                    func=ast.Name('__import__'),
                    args=[ast.Constant(name_list[n])],
                    keywords=[]))
            out_node.elts.append(out)

    def handle_if(if_statement:ast.If):
        body=convert(if_statement.body,recursion+1)
        orelse=convert(if_statement.orelse,recursion+1)
        out=ast.IfExp(if_statement.test,body,orelse)
        out_node.elts.append(out)

    def handle_continue(continue_statement:ast.Continue):
        loop_control_stack[-1][3]=True # have continue
        out_node.elts.append(
            ast.NamedExpr(
                target=loop_control_stack[-1][1],
                value=ast.Constant(value=False)))
    
    def handle_break(continue_statement:ast.Continue):
        loop_control_stack[-1][2]=True # have break
        loop_control_stack[-1][3]=True # break includes continue
        out_node.elts.append(
            ast.NamedExpr(
                target=loop_control_stack[-1][1],
                value=ast.Constant(value=False)))
        out_node.elts.append(
            ast.NamedExpr(
                target=loop_control_stack[-1][0],
                value=ast.Constant(value=False)))

    def post_process(out_node): # Output optimization
        if len(out_node.elts)==0:
            out_node=ast.Expr(value=ast.Constant(value=None))
        elif len(out_node.elts)==1:
            out_node=out_node.elts[0]
        return out_node

    for n_body,node in enumerate(body):
        if type(node)==ast.Expr:
            out_node.elts.append(node)
        elif type(node)==ast.For:
            handle_for(node)
        elif type(node)==ast.If:
            handle_if(node)
            if loop_control_stack[-1][3] and body[n_body+1:]: 
                # 如果在分支中有continue/break且分支后还有语句
                # 则判断是否中断，再执行
                out_node.elts.append(
                    ast.IfExp(
                        test=loop_control_stack[-1][1],
                        body=convert(body[n_body+1:],recursion+1),
                        orelse=ast.Constant(value=None)))
                break
        elif type(node)==ast.Pass:
            pass
        elif type(node)==ast.Assign:
            handle_assign(node)
        elif type(node)==ast.AnnAssign:
            out_node.elts.append(
                ast.NamedExpr(node.target,node.value))
        elif type(node)==ast.AugAssign:
            handle_aug_assign(node)
        elif type(node)==ast.Import:
            handle_import(node)
        elif type(node)==ast.While:
            handle_while(node)
        elif type(node)==ast.Continue:
            handle_continue(node)
            break # 中断
        elif type(node)==ast.Break:
            handle_break(node)
            break
        else:
            raise ConvertError('Convert failed.\nError: "%s", line %d, Statement "%s" is not convertable.'\
                    %(filename,node.lineno,type(node).__name__))
    
    if recursion==0 and usesing_itertools:
        inject_itertools()

    out_node=post_process(out_node)

    return out_node

if __name__=='__main__':
    import sys
    import os

    output_file_name=''
    help_text='''Usage: oneliner.py [input file] [param [param option]] ...
Options:
    -h               -> get help info.
    -o [output path] -> set output script path
'''

    argv=sys.argv[1:]

    def parse_param(param,has_option=True):
        if not param in argv:
            return (False,'')
        index=argv.index(param)
        if not has_option:
            argv.pop(index)
            return (True,'')
        if index<len(argv)-1:
            option=argv[index+1]
            argv.pop(index)
            argv.pop(index)
            return (True,option)
        return (False,'')

    has_param,data=parse_param('-h',has_option=False)
    if has_param:
        print(help_text)
        sys.exit(0)

    has_param,data=parse_param('-o')
    if has_param:
        output_file_name=data
    
    if len(argv)==0:
        print('Error: No input file.')
        print(help_text)
        sys.exit(1)

    if not os.path.isfile(argv[0]):
        print('Error: Invalid input script path %s.'%argv[0])
        sys.exit(1)
    input_file_name=argv[0]
    filename=input_file_name

    with open(input_file_name,'r') as input_file:
        script=input_file.read()

    main_body=ast.parse(script)
    result=ast.unparse(convert(main_body.body)).replace('\n', '')
    
    if output_file_name:
        with open(output_file_name,'w') as output_file:
            print(result,file=output_file)
    else:
        print(result)
    print('Script generated successfully.')