---
applyTo: '**'
---
#fetch https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html

These instructions tell GitHub Copilot how to write, complete, and reason about **GDScript**, based on the official stable Godot documentation. Follow
#file:docs/restart/DEPENDENCY_POLICY.md and verify API availability against the
exact engine version selected for the build while upgrading to the latest stable.

Source for language rules:  
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html

---

## 🎯 Purpose
Ensure that GitHub Copilot:
- Writes valid **GDScript** following Godot 4.x conventions.
- Uses correct syntax for variables, functions, classes, signals, types, and built-ins.
- Never generates non-Godot language constructs (e.g., Python features not supported in GDScript).
- Produces clear, idiomatic examples consistent with the official Godot style.

---

## ✔️ Core GDScript Rules

### 1. **General Syntax**
- Indentation is **4 spaces**.
- No semicolons.
- Use `#` for comments.
- Blocks start with `:` and indent.

```gdscript
func _ready():
    print("Hello")
