
```
var x : bool

invariant x

after init {
    x := true
}

action a  = {
  x := ~x
}

export a
```
