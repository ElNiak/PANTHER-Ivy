
```
var p : bool

after init {
    p := true
}

export action a(q:bool) = {
    p := p & q;
}

invariant p

proof [this] {
    tactic vcgen
}
```
