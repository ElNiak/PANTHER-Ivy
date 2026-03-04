
```
type t

relation p(X:t)

type q = struct {foo : bool}

implement type t with q

definition p(X) = foo(X as q)
```
