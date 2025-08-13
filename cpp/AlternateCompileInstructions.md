If:

* you’re not on C++17 (or MSVC is using the experimental TS), or
* `<filesystem>` isn’t available and you need `<experimental/filesystem>`, or
* you referenced `filesystem::...` without bringing the right namespace into scope.

Here’s a small, **portable fix**: add a feature-detecting alias and use `fs::` everywhere.

---

### 1) Patch the top of `eminorcc.cpp`

Replace your single mega-include with explicit headers and the filesystem alias block:

```cpp
// --- replaces #include <bits/stdc++.h> ---
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <exception>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#if __has_include(<filesystem>)
  #include <filesystem>
  namespace fs = std::filesystem;
#elif __has_include(<experimental/filesystem>)
  #include <experimental/filesystem>
  namespace fs = std::experimental::filesystem;
#else
  #error "No <filesystem> or <experimental/filesystem> found. Use a C++17 compiler/lib."
#endif
```

(You can still keep `using namespace std;` if you want, but it’s not required for this fix.)

---

### 2) Replace all `filesystem::` with `fs::`

Search/replace these in the file:

```diff
- filesystem::create_directories(filesystem::path(path).parent_path());
+ fs::create_directories(fs::path(path).parent_path());

- string base = (filesystem::path(cmd.outDir)/"a").string();
+ string base = (fs::path(cmd.outDir)/"a").string();
```

If there are any other occurrences of `filesystem::...`, change them to `fs::...` as well.

---

### 3) Build commands that match your toolchain

**MinGW-w64 / GCC (Windows or Linux):**

```cmd
g++ -std=gnu++17 -O2 eminorcc.cpp -o eminorcc.exe
```

If your GCC is **< 9**, link the filesystem library explicitly:

```cmd
g++ -std=gnu++17 -O2 eminorcc.cpp -o eminorcc.exe -lstdc++fs
```

**Clang (macOS/Linux):**

```bash
clang++ -std=c++17 -O2 eminorcc.cpp -o eminorcc
```

**MSVC (Visual Studio “x64 Native Tools” prompt):**

```cmd
cl /std:c++17 /O2 /EHsc eminorcc.cpp /Fe:eminorcc.exe
```

If your MSVC only has the experimental TS, the alias block above will automatically use
`std::experimental::filesystem`.

---

### 4) Quick smoke test

```cmd
echo @main { #init $A0 #load $A0, 0xFF #call render, $A0 #exit } > hello.eminor
eminorcc.exe hello.eminor -o out
type out\a.text.hex
type out\a.dis.txt
```

---

