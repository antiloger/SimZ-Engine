is there issue with this:

```python
class ARegister:
  def __init__(self):

class Aparent(ABC):
  ARegister = {}

class A(Aparent):
    def __init__(self):
        self.a = 1
        self.b = 2
```

i want know if i want to store every init Aparent classes instance in register. how to do that. what is good way to do that. i want to store every instance of Aparent in ARegister. 
```
