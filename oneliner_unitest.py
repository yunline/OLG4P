import unittest
import os
import shutil
import sys
import subprocess
import io
import builtins

class NonFunctionConvertTest(unittest.TestCase):
    def setUp(self):
        self.testdir = "./__testtmp__"
        self.program = "./oneliner.py"
        self.original_file = os.path.join(self.testdir, "original.py")
        self.converted_file = os.path.join(self.testdir, "converted.py")
        self.python = sys.executable

        if not os.path.exists(self.testdir):
            os.mkdir(self.testdir)

    def tearDown(self):
        shutil.rmtree(self.testdir)
    
    def exec(self,code:str):
        io1=io.StringIO()
        def _print(*args,**kwargs):
            builtins.print(*args,file=io1,**kwargs)
        exec(code,{"print":_print})

        return io1.getvalue()

    def check_convert(self, input_script):
        with open(self.original_file, "w", encoding="utf8") as original:
            original.write(input_script)

        subprocess.run(
            [self.python, self.program, self.original_file, "-o", self.converted_file],
            timeout=1,
            check=1,
            capture_output=1,
        )

        result1=self.exec(input_script)

        result2 = subprocess.run(
            [self.python, self.converted_file], timeout=1, check=1, capture_output=1, text=1
        )

        self.assertEqual(result1, result2.stdout)

    def test_convert_expr(self):
        script = """
print([i.upper() for i in "hello"])
"""
        self.check_convert(script)

    def test_convert_if(self):
        script = """
i=%d
if i==0:
    print("xd")
elif i==1:
    print("OOOO")
else:
    print("oops")
"""
        for i in range(3):
            self.check_convert(script % i)

    def test_convert_for(self):
        script = """
for i in range(10):
    if i%2:
        print(i)
"""
        self.check_convert(script)

    def test_convert_for_continue_break(self):
        script = """
for i in range(10):
    if i%2:
        continue
    print(i)
    if i==8:
        print("break")
        break
    print("foo")
"""
        self.check_convert(script)

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
        continue
    print(i)
    if i>10:
        print("break")
        break
    print("foo")
    i=i+1
"""
        self.check_convert(script)
    
    def test_convert_nested_loop(self):
        pass


if __name__ == "__main__":
    unittest.main()
