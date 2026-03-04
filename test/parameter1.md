
```
type t
interpret t -> int

parameter p : t

action a returns (r:t) = {
    r := p
}

export a
```
