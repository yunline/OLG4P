import unittest
import os
import io
import builtins
import threading
import time
import traceback

import oneliner


class NonFunctionConvertTest(unittest.TestCase):
    def exec(self, code: str, timeout=1):
        _io = io.StringIO()

        def _print(*args, **kwargs):
            builtins.print(*args, file=_io, **kwargs)

        err = None

        def _exec():
            nonlocal err
            try:
                exec(code, {"print": _print})
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

    def check_convert(self, input_script):
        result_original = self.exec(input_script)
        converted = oneliner.convert_code_string(input_script)
        result_converted = self.exec(converted)
        self.assertEqual(result_original, result_converted)

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
