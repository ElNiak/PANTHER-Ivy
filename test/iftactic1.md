
```
var p : bool
var q : bool

type t
var x : t
var y : t

action a  = {
    assert p
    proof {
        let Y = y;
        if q {let X = x}
        else {}
    }
}

export a
```
