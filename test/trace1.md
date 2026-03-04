
```
var p : bool
var q : bool

action a = {
    assume p & ~q;
    if p | q {
        assert false
    }
    else {
        assert false
    };
    p := true;
}

export a
```
