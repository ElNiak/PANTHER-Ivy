
```
type t

var v : t
interpret t -> nat

action a = {
    while exists X. X < v {
	v := v - 1;
    }
}

export a
```
