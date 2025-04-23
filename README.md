# SimZ-Engine

"""
import simpy
import random

env = simpy.Environment()
res = simpy.Resource(env, capacity=1)
res1 = simpy.Resource(env, capacity=1)

@dataclass
class GenType:
    id: int
    name: str
    value: int

def ResComp(res: simpy.Resource, data: GenType):
    with res.request() as req:
        yield req
        randTime = random.randint(1, 5)
        print(f"Resource  acquired at {env.now}")
        data.value += 1
        print(f"Data {data.id} - {data.name} updated to {data.value} at {env.now}")
        yield env.timeout(randTime)
        print(f"Resource data {data.name} released at {env.now}")
    env.process(ResComp1(res1, data))

def ResComp1(res: simpy.Resource, data: GenType):
    with res.request() as req:
        yield req
        randTime = random.randint(4, 8)
        print(f"Resource1  acquired at {env.now}")
        data.value += 1
        print(f"Data {data.id} - {data.name} updated to {data.value} at {env.now}")
        yield env.timeout(randTime)
        print(f"Resource1 data {data.name} released at {env.now}")

def mainLoop():
    for i in range(5):
        newData = GenType(i, f"Data-{i}", 0)
        print(f"create data {newData.name} at {env.now}")
        env.process(ResComp(res, newData))
        yield env.timeout(1)  # Simulate some delay between requests

env.process(mainLoop())
env.run()
"""
