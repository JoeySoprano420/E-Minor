Here are dead-simple **Windows CMD** build commands that turn the `eminorcc.cpp` you got from me into `eminorcc.exe`.

---

### Option A — MinGW-w64 (recommended, works with `bits/stdc++.h`)

1. Install a GCC toolchain (any of these works):

* **MSYS2** (recommended): [https://www.msys2.org/](https://www.msys2.org/)
  Then in MSYS2, install: `pacman -S --needed mingw-w64-ucrt-x86_64-gcc`
* or **WinLibs/TDM-GCC/CodeBlocks MinGW** (add its `bin` to your PATH)

2. In **CMD** (not MSYS shell), from the folder that contains `eminorcc.cpp`:

```cmd
g++ -std=gnu++17 -O2 -pipe eminorcc.cpp -o eminorcc.exe
```

Optional (smaller exe, fully static may fail on some setups):

```cmd
g++ -std=gnu++17 -O2 -s eminorcc.cpp -o eminorcc.exe
```

> If you see an old-GCC *filesystem* link error, add:
> `-lstdc++fs`
> so: `g++ -std=gnu++17 -O2 eminorcc.cpp -o eminorcc.exe -lstdc++fs`

Run it:

```cmd
eminorcc.exe your_source.eminor -o out
```

---

### One-shot build script (save as `build.bat` next to the .cpp)

```bat
@echo off
setlocal
rem Adjust this if gcc isn’t on PATH, e.g.:
rem set PATH=C:\msys64\ucrt64\bin;%PATH%
g++ -std=gnu++17 -O2 -pipe eminorcc.cpp -o eminorcc.exe
if errorlevel 1 (
  echo Build failed.
  exit /b 1
) else (
  echo Built eminorcc.exe
)
endlocal
```

Run:

```cmd
build.bat
```

---

### Option B — Microsoft Visual C++ (cl.exe)

MSVC doesn’t ship `bits/stdc++.h`. If you **want to use `cl`**, open the “x64 Native Tools Command Prompt for VS”, then either:

* **Quick fix:** replace the first line of the file

```cpp
#include <bits/stdc++.h>
```

with these standard headers:

```cpp
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <exception>
#include <filesystem>
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
```

Then compile:

```cmd
cl /std:c++17 /O2 /EHsc eminorcc.cpp /Fe:eminorcc.exe
```

---

### Smoke test

```cmd
type > hello.eminor <<EOF
@main {
  #init $A0
  #load $A0, 0xFF
  #call render, $A0
  #exit
}
EOF
eminorcc.exe hello.eminor -o out
type out\a.text.hex
type out\a.dis.txt
```

