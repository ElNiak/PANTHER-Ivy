
```
individual p : bool

action foo = {
    p := true;
    while p
    invariant true
    {
	p := false
    };
    assert ~p

}

export foo
```
