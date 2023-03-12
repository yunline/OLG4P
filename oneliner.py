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

def convert(body,recursion=0):
    global usesing_itertools

    out_node=ast.List([])

    def inject_itertools():
        out_node.elts.insert(0,ast.NamedExpr(
            target=ast.Name(id='itertools'),  
            value=ast.Call(
                func=ast.Name(id='__import__'),
                args=[
                    ast.Constant(value='itertools')],      
                keywords=[])))
    
    def handle_while_statement(while_statement:ast.While):
        condition=while_statement.test
        payload=convert(while_statement.body,recursion+1)
        orelse=convert(while_statement.orelse,recursion+1)
        out_node.elts.append(ast.ListComp(
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
                    is_async=0)]))

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

    for n_body,node in enumerate(body):
        if type(node)==ast.Expr:
            out_node.elts.append(node)
        elif type(node)==ast.For:
            elt=convert(node.body,recursion+1)
            _exp=ast.ListComp(elt,[ast.comprehension(node.target,node.iter,[],False)])
            out_node.elts.append(_exp)
        elif type(node)==ast.If:
            _body=convert(node.body,recursion+1)
            _orelse=convert(node.orelse,recursion+1)
            _exp=ast.IfExp(node.test,_body,_orelse)
            out_node.elts.append(_exp)
        elif type(node)==ast.Pass:
            pass
        elif type(node)==ast.Assign:
            handle_assign(node)
        elif type(node)==ast.AugAssign:
            handle_aug_assign(node)
        elif type(node)==ast.Import:
            _name_list=[_alias.name for _alias in node.names]
            _asname_list=[_alias.asname if not _alias.asname is None
                else _alias.name for _alias in node.names]

            for n,_id in enumerate(_asname_list):
                _assign=ast.Assign([ast.Name(_id)],
                    ast.Call(ast.Name('__import__'),
                        [ast.Constant(_name_list[n])],[]
                    )
                )
                handle_assign(_assign)
        elif type(node)==ast.While:
            usesing_itertools=True
            handle_while_statement(node)
        else:
            raise ConvertError('Convert failed.\nError: "%s", line %d, Statement "%s" is not convertable.'\
                    %(filename,node.lineno,type(node).__name__))
    
    if recursion==0 and usesing_itertools:
        inject_itertools()

    # Output optimizing
    if len(out_node.elts)==0:
        out_node=ast.Expr(value=ast.Constant(value=None))
    elif len(out_node.elts)==1:
        _value=out_node.elts[0]
        if type(_value)==ast.Expr:
            out_node=_value
        else:
            out_node=ast.Expr(value=_value)

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