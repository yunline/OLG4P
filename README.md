# One-Liner Generator for Python

A simple script that converts python scripts into only one line. 

## Example
**InputFile:**
```python
import random
y,h=0,2
msg='hello_world'
while y<h*2:
    for x in range(len(msg)+2):
        print(random.choice('/\\'),end='')
    y=y+1
    if y==h:
        print('\n %s '%msg)
    else:
        print('')
```
**Generated:**
```python
[(itertools := __import__('itertools')), (random := __import__('random')), (lambda y, h: [(msg := 'hello_world'), [[[[print(random.choice('/\\'), end='')] for x in range(len(msg) + 2)], (y := (y + 1)), [print('\n %s ' % msg)] if y == h else [print('')]] for _ in itertools.takewhile(lambda _: y < h * 2, itertools.count())]])(*(0, 2))]
```

## Usage
`python oneliner.py [input file] -o [output file]`  
Or use `python oneliner.py -h` for help.

## Limitation
This script requires python3.8+. Many statements are not convertable.  
Here are the statements that have already been implemented.
|statement|example|
|-|-|
|Expr|`print((1+1)*2)`|
|Assign<sub> 1</sub>|`a=1` or `a,b=b,a`|
|If|`if a==0: ...`<br>`elif a>1: ...`<br>`else: ...`|
|For<sub> 2</sub>|`for i in range(10): ...`|
|While<sub> 2</sub>|`While a<100: ...`|
|Pass|`while 1: pass`|
|Import<sub> 3</sub>|`import math` or `import os,sys`|

Remarks:
1. 'AugAssign' (e.g. `a+=1`) is not implmented.
2. 'while-else', 'for-else', 'continue' and 'break' are not implmented.
3. 'from-import' is not implmented.