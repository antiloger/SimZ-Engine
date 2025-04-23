str_code = """
def add(value):
    return value+2

def run(c):
    out = c.get("me")
    out = add(out)
    print(out)
    return out
"""


class CME:
    value = {
        "me": 1,
    }

    def get(self, key):
        return self.value.get(key, None)


# Compile the string code
code_obj = compile(str_code, "<string>", "exec")

# Create a namespace to execute the code in
namespace = {}

# Execute the compiled code in the namespace
exec(code_obj, namespace)

# Get the run function from the namespace
run_func = namespace["run"]

# Create an instance of CME
c_instance = CME()

# Call the run function with the CME instance
result = run_func(c_instance)

# Verify the result
print(f"The final result is: {result}")
