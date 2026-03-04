
```
type t

individual bit : bool

object foo(me:t) = {
    action flip = {
	bit := ~bit
    }
}

export foo.flip

extract iso_foo(me:t) = foo(me)
```
