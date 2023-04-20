import unittest
import io
import builtins
import threading
import time

import oneliner


class NonFunctionConvertTest(unittest.TestCase):
    def exec(self, code: str, external_globals, timeout=5):
        _io = io.StringIO()

        def _print(*args, **kwargs):
            builtins.print(*args, file=_io, **kwargs)

        err = None
        _globals = {"print": _print}
        _globals.update(external_globals)

        def _exec():
            nonlocal err
            try:
                exec(code, _globals)
            except Exception as _err:
                err = _err

        th = threading.Thread(target=_exec)
        th.daemon = True
        th.start()
        t0 = time.time()
        th.join(timeout=timeout + 0.2)
        if time.time() - t0 > timeout:
            raise TimeoutError("Execution timeout.")
        if not err is None:
            raise err

        return _io.getvalue()

    def check_convert(self, input_script, external_globals={}):
        result_original = self.exec(input_script, external_globals)
        converted = oneliner.convert_code_string(input_script)
        result_converted = self.exec(converted, external_globals)
        self.assertEqual(result_original, result_converted)

    def test_convert_expr(self):
        script = """
print([i.upper() for i in "hello"])
"""
        self.check_convert(script)

    def test_convert_if(self):
        script = """
i={}
j={}
if i==0:
    if j==1:
        print("xd")
    else:
        print("sb")
elif i==1:
    if j==1:
        print("oooo")
    else:
        print("OOOO")
else:
    print("oops")
"""
        for i in range(3):
            for j in range(2):
                self.check_convert(script.format(i, j))

    def test_convert_for(self):
        script = """
for i in range(10):
    if i%2:
        print(i)
"""
        self.check_convert(script)

    def test_convert_for_continue_break(self):
        script = """
for i in range(20):
    if i%3:
        if i>6:
            continue
        print("xxx")
    print(i)
    if i==8:
        print("break")
        break
    if i%2:
        print("aba")
    print("foo")
"""
        self.check_convert(script)

    def test_convert_for_else(self):
        script = """
brk={}
for i in range(10):
    if i%2:
        continue
    print(i)
    if i==8:
        print("break")
        if brk:
            break
    print("foo")
else:
    print("aaaaa")
"""
        self.check_convert(script.format("True"))
        self.check_convert(script.format("False"))

    def test_convert_while(self):
        script = """
i=0
while i<10:
    if i%2:
        print(i)
    i=i+1

while 0:
    print("Nope")
"""
        self.check_convert(script)

    def test_convert_while_continue_break(self):
        script = """
i=0
while 1:
    if i%2:
        i=i+1
        if i>6:
            continue
    print(i)
    if i>10:
        print("break")
        break
    print("foo")
    i=i+1
"""
        self.check_convert(script)

    def test_convert_while_else(self):
        script = """
i=0
brk={}
while i<10:
    if i%2:
        print(i)
    i=i+1
    if i==5 and brk:
        break
else:
    print("qwq")
"""
        self.check_convert(script.format("True"))
        self.check_convert(script.format("False"))

    def test_convert_nested_loop(self):
        script = """
for m in [10,20]:
    n=0
    while n<m:
        n=n+1
        for i in range(16):
            for j in range(8):
                if i==j:
                    continue
                print(i,j)
            if i==10-n:
                print("p1")
                break
        else:
            print("p2")
            break
    else:
        print("p3")
"""
        self.check_convert(script)

    def test_convert_assign(self):
        script = """
a=1
print(a)
a=2
print(a)
"""
        self.check_convert(script)

    def test_convert_aug_assign(self):
        script = """
a=1
a+=6
print(a)
a-=2
print(a)
a*=8
print(a)
a//=2
print(a)
a/=2
print(a)
a**=0.5
print(a)

a=1
a|=0xfe
print(a)
a&=0x08
print(a)
a^=0xcc
print(a)
a<<=2
print(a)
a>>=4
print(a)
"""
        self.check_convert(script)

    def test_convert_subscript_assign(self):
        script = """
l=[1,2,3]
l[0]=0
print(l)
l[::]=[1,3,5,7]
print(l)

l[0],l[2]=2,6
print(l)
"""
        self.check_convert(script)

    def test_convert_subscript_aug_assign(self):
        script = """
l=[1]
l[0]+=1
print(l[0])
"""
        self.check_convert(script)

    def test_convert_attribute_assign(self):
        script = """
a=cls()
a.b=0
print(a.b)
"""

        class Dummy:
            b = 1234

        self.check_convert(script, {"cls": Dummy})

    def test_convert_attribute_aug_assign(self):
        script = """
a=cls()
a.b+=2
print(a.b)
"""

        class Dummy:
            b = 1234

        self.check_convert(script, {"cls": Dummy})

    def test_convert_multiple_assign(self):
        script = """
a=cls()
c=[0,12]
a.b,c[0],d,e=range(4)
print(a.b,c,d,e)
a.b,c[0],d,e=e,d,c[1],a.b
print(a.b,c,d,e)
"""

        class Dummy:
            b = 1234

        self.check_convert(script, {"cls": Dummy})

    def test_convert_import(self):
        script = """
import sys
print(sys.argv)

import urllib.request as r
print(r)
print('urllib' in globals())
import urllib.request
print(urllib.request)
print('urllib' in globals())
"""

        self.check_convert(script)


if __name__ == "__main__":
    unittest.main()
