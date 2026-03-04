
```
type t

var p(X:t) : bool

after init {
  p(X) := true
}

action crash(self:t) = *

after crash {
   p(self) := true
}

invariant p(X)

export crash
```
