import re, subprocess
path = r"C:\Users\dellg15\quantpulse-ai\backend\app\models\enums.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

lines = src.split("\n")
out = []
current_class = None
for line in lines:
    out.append(line)
    m = re.match(r"^class (\w+)\(str, Enum\):", line)
    if m:
        current_class = m.group(1)
        continue
    if current_class and re.match(r"^class \w+", line):
        current_class = None
        m2 = re.match(r"^class (\w+)\(str, Enum\):", line)
        if m2:
            current_class = m2.group(1)
    if current_class and re.match(r"^    (?:@property|def )", line):
        out.append("    @classmethod")
        out.append("    def _missing_(cls, value):")
        out.append('        """Tolerate str(enum) leftovers: str(Foo.X) == \'Foo.X\'."""')
        out.append("        if isinstance(value, str):")
        out.append("            prefix = cls.__name__ + '.'")
        out.append("            name = value.split('.', 1)[-1].lower() if value.startswith(prefix) else value.lower()")
        out.append("            for member in cls:")
        out.append("                if member.value == name or member.name.lower() == name:")
        out.append("                    return member")
        out.append("        return None")
        current_class = None

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
r = subprocess.run(["python", "-m", "py_compile", path], capture_output=True, text=True)
print(r.stderr or "COMPILE_OK")
