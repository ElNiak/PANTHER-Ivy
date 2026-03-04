
```
object marcelo = {
        type t
        action hello(x:t) = {

        }
}
alias marcelo = marcelo.t

action world = {
        var x:t
        x.hello
}
```
