
```
type paramtype

isolate inonparam = {
    action myaction = {
    }

    export myaction
} with iparam

isolate iparam(p: paramtype) = {


} with inonparam
```
