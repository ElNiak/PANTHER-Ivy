# Changelog

## 2025-05-23

### Other

- udpate the system model for QUIC -> minor update in network model -> still need to fix quic model and attack model

## 2025-05-19

### Other

- finxing bug nealry ok to apt

## 2025-03-03

### Other

- starting adding apt module -> still need to refactor old model

## 2025-02-19

### Other

- fixing field dataclass param + init HTTP pljugin

## 2024-12-15

### Other

- fixing package bugs

## 2024-12-12

### Other

- add some dc string

## 2024-12-11

### Other

- add packaged version -> still need to do test + udpate some path
- update for gperf

## 2024-12-10

### Other

- update with docker base image for services + execution env ok -> now need to implement MiniP
- refactor of the configuration part nearly finished -> ok for docker compose IUT + tester ivy -> still need to test other netenv -> then integrate execution env -> then improving docker build -> finisiliazing observers

## 2024-12-09

### Other

- continuing big config refactor
- update for new conf part

## 2024-12-08

### Other

- update for new service arch

## 2024-12-06

### Other

- Shadow nearly good -> still some hardcoded value to change for tester -> will be fixed with config update

## 2024-11-29

### Other

- ivy tester ok on docker compose

## 2024-11-28

### Other

- udpate for new panther -> still need to update some stuffs

## 2024-11-25

### Other

- Still improve integration of Tester -> nearly ok still need to move ivy file, update path -> Still need to generalise for multiple env

## 2024-11-23

### Other

- starting tester plugin

## 2024-09-16

### Other

- add AI generated function spec + init jinja refactoring
- add AI generated function spec + init jinja refactoring

## 2024-09-03

### Other

- update to python3.10 seems ok but strange stuff in ivTo_cpp.py
- merge from mcmillan -> still need to test

## 2024-08-25

### Other

- adding nordsec result

## 2024-08-18

### Other

- update system + minip test

## 2024-08-15

### Other

- fix old/new introduce bugs
- intermediary push

## 2024-08-12

### Other

- quic & minip attacker and mitm seem ok +- -> still bugs with mitn for quic

## 2024-08-08

### Other

- attacker +- ok -> implementing cve + starting system model

## 2024-08-06

### Other

- starting attacker model

## 2024-08-05

### Other

- pushing advancment for tls connection spoofing but still not working, focusing on simple attacker model now

## 2024-08-03

### Other

- encrypted version fast enough

## 2024-08-02

### Other

- Problem with encryption -> need to change packet format

## 2024-07-31

### Other

- fixed some bugs -> seems to have a problem in picoquic that send small initial packet -> TODO: do attacker api, merge attacker + mitm ? + do unified model for all protocols
- add basic mim method randomized + todo: merge attacker and mim endpoints + enable attacker to directly contact the victim + merge all protocol in one model

## 2024-07-30

### Other

- generation seems ok -> remind: no random generation from function poping element from array !

## 2024-07-29

### Other

- update before big update

## 2024-07-26

### Other

- forwarding short header +- ok
- short header and padding +- supported now for apt
- short header and padding +- supported now for apt
- quic apt +- ok -> still need to implement coalesed packet everywhere with arra of packet

## 2024-07-24

### Other

- minip + stream data ok -> quic nearly ok -> still need to merge everything

## 2024-07-23

### Other

- update endpoint
- update endpoint -> remove client_ep/server_ep etc to encaspulate in mim_agent -> next removing/merging attacker/mim ? + add sub object to do attacker for each protocol

## 2024-07-22

### Other

- using packet oject -> still need to fix a little bit stream_data_array + starting unifying model among different protocols

## 2024-07-17

### Other

- mim +- ok, now good ip

## 2024-06-06

### Other

- initiating minip attack template
- fix some bugs
- correct path
- update

## 2024-06-05

### Other

- fix apt refactor + remove old quic model

## 2024-06-03

### Other

- fix bugs on atp

## 2024-06-02

### Other

- fix path
- fix path

## 2024-05-29

### Other

- update path for new pfv arch
- starting adding http3

## 2024-05-28

### Other

- update packet & frame super object

## 2024-05-27

### Other

- starting unifying frame/packet
- add apt model -> still need to unify common interface

## 2024-05-21

### Other

- small udpate attacker
- small udpate

## 2024-04-29

### Other

- Update coap_endpoint.ivy file

Co-authored-by: AnonymousSEMA <anonymous.sema.git@gmail.com>
- Add new Ivy files for BGP/CoAP protocol testing

Co-authored-by: AnonymousSEMA <anonymous.sema.git@gmail.com >

## 2024-04-25

### Other

- update spec

## 2024-04-23

### Other

- update coap

## 2024-04-15

### Other

- update coap model

## 2024-04-12

### Other

- update coap bases

## 2024-03-22

### Other

- Update README.md

## 2024-03-18

### Other

- Update README.md
- Update README.md

## 2023-12-19

### Other

- base for coap
- remove bgp
- update bgp model

## 2023-11-24

### Other

- push avancement on bgp, still prop to implem + deser/ser mostly finish

## 2023-11-03

### Other

- add new protocol model

## 2023-10-23

### Other

- update fix

## 2023-10-18

### Other

- update for paper
- update for paper

## 2023-10-03

### Other

- update rfc9001 model + signal heuristic + ping pong example

## 2023-09-02

### Other

- fix some bugs - refactor extension + add props

## 2023-08-29

### Other

- big push for time compoenent + timeout test

## 2023-08-13

### Other

- quic_congestion and quic_rtt compile and seem working but need further integration and validation
- update base creating concept graph + quic_rtt + quic_congestion - error with quic_packet array and while loop -> now trying another approach to be more fast and do not modify ivy

## 2023-07-03

### Other

- update repo to work with newer ivy version for QUIC -> check ivy_to_cpp

## 2023-06-27

### Other

- update

## 2023-06-26

### Other

- push quic

## 2023-01-30

### Other

- remove debugging print
- fixing boolean quantifiers

## 2022-10-13

### Other

- changing pointer to web site in README.md
- adding macos workflow

## 2022-10-12

### Other

- fixed erase_unrefed bug, bump version to 1.8.24

## 2022-02-11

### Other

- fixing tcp_host and other bugs

## 2022-02-10

### Other

- fix invar checking in init

## 2022-02-06

### Other

- workflow messing
- workflow messing
- workflow messing

## 2022-02-05

### Other

- workflow messing
- workflow messing
- adding workflow

## 2021-12-10

### Other

- bumped version to 1.8.22
- z3_thunk seems to be working, maybe
- still working

## 2021-12-09

### Other

- z3_thunk works for no captured functions
- fixed destructor bug
- fixing z3_thunk

## 2021-12-08

### Other

- bump version to 1.8.21
- fix bug in unique ids of properties

## 2021-12-07

### Other

- bump version to 1.1.20
- fix import strip bug
- bump version to 1.1.19
- adding to keyval API

## 2021-12-03

### Other

- ordered_set fixes

## 2021-12-01

### Other

- adding lexord
- bump version to 1.1.18
- fixing ordered_set

## 2021-11-29

### Other

- bump version to 1.1.17
- fixes for 2D processes

## 2021-11-24

### Other

- bump version to 1.1.16
- fix to instantiate, add debug to trace"

## 2021-11-19

### Other

- testing invariant check fix

## 2021-11-18

### Other

- bump version to 1.8.15
- ops for bit vectors

## 2021-11-17

### Other

- bump to version 1.8.14
- fixed cast of int types top bv

## 2021-11-13

### Other

- bump to version 1.8.13
- fixes including process bug

## 2021-11-11

### Other

- version bump to 1.8.12
- many features

## 2021-10-25

### Other

- bumping version
- adding instance trace-back in error messages
- bump version
- bump version
- fix mod in numbers and order, issue #35
- fixing template isolate, adding counts to ivy_launch

## 2021-10-19

### Other

- version 1.8.8
- bug fixes and template isolate

## 2021-10-17

### Other

- bigger xterm fonts, remove impl from tcp_test

## 2021-10-13

### Other

- changes

## 2021-10-07

### Other

- added nat.mod, fixed cast
- adding cast operator to ivy_to_cpp

## 2021-10-06

### Other

- adding packaging commands
- bumping version
- empty init fix and adding runs to ivy_launch

## 2021-10-03

### Other

- improving reader randomization in test

## 2021-09-28

### Other

- some udp changes and fix broken unbounded_queue

## 2021-09-25

### Other

- fix tcp return address problem

## 2021-09-24

### Other

- version bump
- fixing randomization, bmc, nat, queue

## 2021-09-18

### Other

- about to try to fix randomization of range types

## 2021-09-09

### Other

- various bug fixes for class

## 2021-09-04

### Other

- version number

## 2021-09-02

### Other

- version number
- hack to prevent core dump at end of test on linux

## 2021-09-01

### Other

- fixes for Linux
- fixed saturation arithmetic bug

## 2021-08-22

### Other

- fix g++ vectot<bool> compat

## 2021-08-17

### Other

- moved up to version 1.8

## 2021-08-14

### Other

- homeworks up to 4 working

## 2021-08-12

### Other

- implemented class and for
- can bmc append example

## 2021-08-05

### Other

- bmc of append example is working

## 2021-08-02

### Other

- strange quantifier compilation bug

## 2021-07-27

### Other

- various fixes
- fixes to extract_aws

## 2021-07-10

### Other

- lamport_mutex test, proof and bmc are working

## 2021-07-09

### Other

- fix compiler bug
- fix to lamport_mutex
- various fixes

## 2021-07-07

### Other

- fix for named property bug

## 2021-07-03

### Other

- many testing fixes

## 2021-07-01

### Other

- fixed bug in handling of "this"

## 2021-06-27

### Other

- linmapdel is working

## 2021-06-21

### Other

- various language fixes

## 2021-06-17

### Other

- fix for string parameters
- added some comments

## 2021-06-10

### Other

- put/get consistency is working

## 2021-06-06

### Other

- handling error responses

## 2021-06-05

### Other

- working on concurrent transactions

## 2021-06-03

### Other

- cleaning up dangling threads
- added threaded callbacks

## 2021-06-02

### Other

- added txid
- first version of aws api generator
- working on parameterized networks

## 2021-05-29

### Other

- working on network and process
- can test put/get

## 2021-05-28

### Other

- add liveness examples from POPL'18, FMCAD'18 and FMSD'21 papers

## 2021-05-09

### Other

- starting aws api

## 2021-05-05

### Other

- adding ivy_launch

## 2021-05-02

### Other

- adding parameter substitution in submodules and network library

## 2021-04-29

### Other

- working on mc

## 2021-04-23

### Other

- fixing performance bug caused by definitions dependent on mutable variables

## 2021-04-21

### Other

- added explicit goal premises
- fix for relarray

## 2021-03-16

### Other

- l2s fixes
- added aiger and abc as submodules
- fixes for compilation on mac
- mac install updates

## 2021-03-15

### Other

- forgotten file
- working on builds on mac
- fixes to v3 compiler for mac

## 2021-03-14

### Other

- fixed error reporting bug and added lemma to number_theory.ivy because of Z3 performance regression

## 2021-03-13

### Other

- added aiger and abc as submodules
- small bugs

## 2021-03-10

### Other

- liveness example with quantifier works with mc
- working on l2s and mc

## 2021-03-05

### Other

- added mc tactic, working on l2s_full tactic

## 2021-02-27

### Other

- fixing compositional liveness proof problems

## 2021-02-17

### Other

- fixing skolemize tactic for temporal properties

## 2021-02-16

### Other

- test file
- starting liveness fixes

## 2021-02-10

### Other

- tentative l2s fix

## 2020-12-04

### Other

- build fixes for Darwin

## 2020-08-26

### Other

- fix regressions in arith_proofs branch
- number theory doc fixes
- number theory doc fixes
- number theory doc fixes
- forgotten file
- making doc page for number theory proofs

## 2020-08-22

### Other

- still on gcd

## 2020-08-21

### Other

- install doc bug

## 2020-08-19

### Other

- got some arith lemmas
- fixing arith proofs
- adding files
- working on arithmetic proofs

## 2020-08-07

### Other

- doc fixes
- spell check proving.ivy

## 2020-08-06

### Other

- fixed mc regression caused by adding labeled proofs
- working on fba

## 2020-08-03

### Other

- fixed bug in ivy_trace
- working on instantiate/witness

## 2020-07-31

### Other

- adding skolem tactic

## 2020-07-30

### Other

- adding labels in deduction
- added warning the associativity of if/then and implies are non-standard
- fix for bug in named proofs

## 2020-07-29

### Other

- doc fix
- added premise lables in deduction.ivy
- added vcgen examples
- ivy_proof regression

## 2020-07-27

### Other

- fix for issue #90
- working on proof documentation

## 2020-07-23

### Other

- working on function tactic

## 2020-07-18

### Other

- working on forward proof

## 2020-07-16

### Other

- added counterexample annotations to proof goals

## 2020-07-15

### Other

- added vcgen tactic

## 2020-07-14

### Other

- checking in std.ivy
- removed getelem
- fix for issue #88

## 2020-06-30

### Other

- got nbody benchmark working

## 2020-06-22

### Other

- making a mess

## 2020-06-17

### Other

- starting fp support

## 2020-06-15

### Other

- fix issue #75

## 2020-06-08

### Other

- fix for fix to issue #74
- fix for issue #74

## 2020-05-27

### Other

- fixing issue #73
- middle of things

## 2020-05-25

### Other

- fixes crash on match failure in ivy_proof

## 2020-05-20

### Other

- fixed issue #71
- fixed issue #70
- fixing
- fix for issue #68

## 2020-05-18

### Other

- fix for issue #67

## 2020-05-16

### Other

- fix for issue #65

## 2020-05-05

### Other

- starting isolate proofs

## 2020-04-19

### Other

- issue #60

## 2020-04-18

### Other

- issue63

## 2020-04-15

### Other

- strange tls api problem

## 2020-04-14

### Other

- fix for issue 62

## 2020-04-06

### Other

- boolean parameter fix
- ivy_solver.py fix from networking branch
- ivy_isolate.py fix from networking branch
- ivyc fix
- adding file
- adding ip files
- added bv random

## 2020-04-05

### Other

- chanhe test modelfil content
- change weighting of generate and receive in testing
- forgotten file
- fixi testing bug
- testing fixes
- moving hash_h to end of ivy_to_cpp.py

## 2020-03-22

### Other

- allow module definitions in objects

## 2020-03-20

### Other

- add broadcast shim example

## 2020-03-15

### Other

- fixed missing parentheses in printed expressions, and printing of interpreted functions in trafes

## 2020-02-26

### Other

- update chord2s example

## 2020-02-20

### Other

- forgot pydot

## 2020-02-19

### Other

- separate v2 comiler build
- fix for v2 compiler bootstrap
- fix install on mac typo
- fixing leader election test

## 2020-02-07

### Other

- doc fixes
- fixed regression in diagram caused by annotations

## 2020-02-03

### Other

- add build for v2 compiler

## 2020-01-28

### Other

- fixed two l2s regressions
- fix invariant regression
- fixing cid overflow problem

## 2020-01-27

### Other

- added bmc method
- testing fix

## 2020-01-23

### Other

- fix for leader tutorial

## 2020-01-22

### Other

- remove debugging
- changed operator syntax

## 2020-01-21

### Other

- finite sorts
- explicit

## 2020-01-20

### Other

- got borrow example working
- forgotten file
- forgotten file
- fixes for multi-paxos

## 2020-01-18

### Other

- fixing mc traces
- more mc fixes

## 2020-01-10

### Other

- adding REST files

## 2019-12-24

### Other

- added leader liveness example

## 2019-12-20

### Other

- l2s tactic fixes -- test_liveness2.ivy now passes

## 2019-12-19

### Other

- new liveness example
- l2s_fixes
- l2s tactic syntax examples
- uncomment save in l2s
- working on l2s tactic

## 2019-12-02

### Other

- Add missing pydot dependency

The `ivy` executable ends up importing ivy_graphviz, which requires
pydot to be installed.
- Fix PYTHONPATH dir in scripts/setup/z3.sh

The correct directory to add to PYTHONPATH is <z3 build dir>/python.
Previously was just <z3 build dir> in z3.sh.

## 2019-11-27

### Other

- serializer fix
- fix typos in doc/examples/networking
- leader tutorial finished

## 2019-11-26

### Other

- changes
- continuing retire connection id implementation
- leader tutorial

## 2019-11-25

### Other

- more mc fixes

## 2019-11-22

### Other

- working on mc and trace fixes
- fixing mc issues

## 2019-11-20

### Other

- removing extra commited files to avoid being overwritten by checkout

## 2019-11-19

### Other

- commiting changes after installing forked version
- fixed ack credit incrementing and decrementing condition

## 2019-11-18

### Other

- new connection id and retire connection id frame events
- fix for g++ flag
- commiting changes to ivy_to_cpp
- added retire_connection_id frame codec
- mistake

## 2019-11-15

### Other

- ACK Rule

## 2019-11-14

### Other

- windows install doc

## 2019-11-13

### Other

- fixes for windows port
- fixed regression in unrolling

## 2019-11-12

### Other

- windows install docs
- ip_spec.ivy changes
- windows build

## 2019-11-08

### Other

- starting windows port
- more mac fixes

## 2019-11-07

### Other

- mac build fix
- another example
- adding ip_spec example

## 2019-11-04

### Other

- regression test for issue #49
- issue #49

## 2019-10-31

### Other

- fix issue #48 in docs

## 2019-10-29

### Other

- regression from fix to issue #46
- issue #46

## 2019-10-28

### Other

- issue #47

## 2019-10-25

### Other

- picoquic instructions

## 2019-10-24

### Other

- logs for picoquic issue #969
- picoquic issue #969

## 2019-10-23

### Other

- fixes issue #43
- language doc and regressions

## 2019-10-22

### Other

- fixes issue #44

## 2019-10-18

### Other

- docs

## 2019-10-17

### Other

- issue #42

## 2019-10-15

### Other

- ui fixes
- doc fixes
- add doc images
- mac doc

## 2019-10-14

### Other

- more docs

## 2019-10-10

### Other

- more docs
- more docs
- more docs
- more docs

## 2019-10-09

### Other

- docs

## 2019-10-08

### Other

- leader election example works again

## 2019-10-07

### Other

- handling fail

## 2019-10-05

### Other

- many fixes

## 2019-09-24

### Other

- fixing server testers
- fix for g++-5

## 2019-09-16

### Other

- Improved Formatting.
- Typos on #48 & #254 & #256 & #535

## 2019-09-13

### Other

- picoquic
- z3 submodule update
- more build details
- adding picotls as submodule

## 2019-09-12

### Other

- improving quic event logging
- updating to z3 4.7.1
- fixing wheel build
- fiddling with z3 lib location
- setup.py
- fixing submodules
- adding setup

## 2019-09-11

### Other

- finding submodule z3 in test
- adding submodule build
- stop trying to strip constructors
- error message error

## 2019-09-10

### Other

- fixed initial key setup

## 2019-09-05

### Other

- working on stripping inits
- mac install change

## 2019-09-03

### Other

- trying to fix website https
- fixing mac install instructions
- updated mac install from source instructions

## 2019-08-17

### Other

- in the middle of big changes

## 2019-08-15

### Other

- factoring out protocol layers

## 2019-08-02

### Other

- cleaning up quic18

## 2019-07-31

### Other

- another INSTALL.md

## 2019-07-30

### Other

- INSTALL.md fixes

## 2019-07-03

### Other

- added native inline section

## 2019-06-27

### Other

- working on borrowing

## 2019-06-21

### Other

- fixing mod_roots

## 2019-06-20

### Other

- fixed move of refernce parameters, compiles up to s6
- implementing move

## 2019-06-15

### Other

- added some error checking to s2/s3 compilers

## 2019-06-12

### Other

- Fixing corner cases in argument passing

## 2019-06-10

### Other

- removed file
- sys.command
- stage 1,2,3 compilers separated

## 2019-06-07

### Other

- bootstraps
- fixed object slicing problem, ivy_to_cpp works
- pass_typeinfer works

## 2019-06-06

### Other

- pass_flat works
- added constructor functions and their axioms
- reader works
- working on reader
- write and file exist
- read_file

## 2019-06-05

### Other

- getenv
- can parse and print syntax.ivy
- compiler fixes

## 2019-06-03

### Other

- hash.ivy and some fixes for bootstrap

## 2019-06-01

### Other

- cow pointers

## 2019-05-28

### Other

- unown

## 2019-05-27

### Other

- doc fix
- working
- autoinstance

## 2019-05-26

### Other

- logvar
- fixed undefined check for dot
- file annotations
- starting on file annotations
- before fixing destructors
- working
- working on var assignments

## 2019-05-25

### Other

- starting var assignments
- working
- fixing ifst, whilest, type contexts
- tuple assignments
- working on tuples

## 2019-05-24

### Other

- method call by reference
- method call by reference
- working on method call by reference
- working on call by reference

## 2019-05-23

### Other

- working on prototypes

## 2019-05-22

### Other

- prototypes
- resize
- starting resize
- cow in v1 compiler

## 2019-05-21

### Other

- name mangling
- fixing ite and vector
- syntax errors, ite

## 2019-05-20

### Other

- include path and traits for native types
- forgotten file
- forgotten file
- fix ivy_to_cpp
- fix function decl

## 2019-05-18

### Other

- collections,order
- function

## 2019-05-17

### Other

- standard traits
- enums and structs

## 2019-05-16

### Other

- function representation
- verison, comments, standard library

## 2019-05-15

### Other

- fixing zero-ary actions
- still working on foreign functions

## 2019-05-14

### Other

- working on foreign functions

## 2019-05-13

### Other

- fixed flattening of interpret
- adding dense representation

## 2019-05-12

### Other

- dereference arrow
- bottom-up type inference and dot
- working on type inference

## 2019-05-11

### Other

- working on variants

## 2019-05-10

### Other

- this
- namespaces and prototypes

## 2019-05-09

### Other

- namespace
- install instructions fixes
- adding quic documentation
- adding quic documentation
- fixing test.py
- fixing install docs
- fixing flattening
- objects

## 2019-05-08

### Other

- instantiate

## 2019-05-07

### Other

- include
- interpret
- headers

## 2019-04-30

### Other

- install instructions
- working
- install changes
- working on destructor
- working on classes
- working
- ../../doc/INSTALL.md
- working

## 2019-04-28

### Other

- added prog
- added vardc, typedc

## 2019-04-27

### Other

- adding error.ivy
- working on ivy_to_cpp

## 2019-04-26

### Other

- type_elide seems to work
- op type fix
- starting on builtins
- simple type infer working

## 2019-04-25

### Other

- added hash
- starting typeinf

## 2019-04-24

### Other

- added app
- ivy_to_cpp
- adding cpp

## 2019-04-22

### Other

- adding property tactic

## 2019-04-19

### Other

- decl groups
- action parses
- starting action
- fixing skip and ite
- added skip and ite

## 2019-04-18

### Other

- added asgn and sequence
- pretty printing
- still on pretty printing
- pretty printing

## 2019-04-17

### Other

- improving encoder
- fixing multiple output parameters
- recursive variants and multiple returns

## 2019-04-15

### Other

- added forgotten file

## 2019-04-12

### Other

- more windows porting
- windows porting
- fixing quadratic construction of Ite trees

## 2019-04-09

### Other

- fixing echo
- handle retransmission of client hello

## 2019-04-05

### Other

- working on modular temporal proofs

## 2019-04-03

### Other

- using temporals to prove temporals

## 2019-04-02

### Other

- starting on temporal tactics

## 2019-03-30

### Other

- still working on quic18 client tester

## 2019-03-25

### Other

- starting on client tester

## 2019-03-22

### Other

- quic18 before changing encoding of crypto streams

## 2019-03-19

### Other

- added some docs to ivy/README.md
- adding _finalize for test
- added some docs to ivy/README.md

## 2019-03-18

### Other

- quic8 stream frames must respect rst_stream final length
- removed application close from quic_server_test_max
- handle one-byte payload length in quic18

## 2019-03-13

### Other

- putting app close and stop_sending back in to quic_server_test_max

## 2019-03-06

### Other

- quic18 add SNI, fix max stream id, error message on sendto fail

## 2019-03-05

### Other

- switched to draft-18

## 2019-03-01

### Other

- fixing regressions

## 2019-02-20

### Other

- working on fraft-17

## 2019-02-19

### Other

- echo example

## 2019-02-16

### Other

- quic17 somewhat working

## 2019-02-15

### Other

- anomaly24
- fixes for bft

## 2019-02-13

### Other

- working on quic17

## 2019-02-12

### Other

- quic17 work

## 2019-02-09

### Other

- moving to draft-17

## 2019-02-08

### Other

- anomaly24

## 2019-01-17

### Other

- not sure

## 2018-12-21

### Other

- quic16 anomaly22

## 2018-12-20

### Other

- fixed problem with long integers in test

## 2018-12-19

### Other

- working on max_data

## 2018-12-18

### Other

- fixed precondition of connection_close

## 2018-12-17

### Other

- adding flexibility to quic test script

## 2018-12-12

### Other

- working on max data in quic

## 2018-12-08

### Other

- quic16 added stop_sending frame

## 2018-12-07

### Other

- adding some command line parameters to quic tester

## 2018-12-06

### Other

- adding parameter defaults
- forgotten file

## 2018-12-05

### Other

- changes for multiple stream in quic16

## 2018-11-29

### Other

- quic15 anomalies 19,20

## 2018-11-28

### Other

- quic15 anomalies 17,18
- quic15 anomaly16

## 2018-11-27

### Other

- working on getting key establishment info from TLS
- add build directory to ivy_to_cpp
- fix to interference check

## 2018-11-24

### Other

- quic15 anomaly15
- quant issues

## 2018-11-23

### Other

- more forgotten files
- more forgotten files
- more forgotten files
- adding forgotten files

## 2018-11-22

### Other

- working on quic15 and quant

## 2018-11-20

### Other

- doc fixes
- quic15 doc fix
- quic15 anomaly11
- working on testing quant

## 2018-11-17

### Other

- fixed action= option

## 2018-11-16

### Other

- quic15 finishes one full test with encryption

## 2018-11-10

### Other

- quic15 sent encrypted packet

## 2018-11-09

### Other

- working on QUIC encryption

## 2018-11-08

### Other

- fix bug in serdes

## 2018-11-07

### Other

- quic15 merge passes tests
- fixed bug with old

## 2018-11-06

### Other

- working on explicit invariants

## 2018-11-05

### Other

- can extract keys from ptls
- working on tc1

## 2018-11-02

### Other

- starting on proofs for conjectures

## 2018-11-01

### Other

- working on picotls

## 2018-10-31

### Other

- added tls_picotls
- weaken the requirement that migration is only detected on receiving a highest-numbered packet so that only 1rtt packets are considered;
- various fixes to fragment checker and interference checker

## 2018-10-30

### Other

- fixed trace for if some

## 2018-10-26

### Other

- working on picotls

## 2018-10-25

### Other

- fixed missing returns in ivy_fragment

## 2018-10-24

### Other

- some comments
- updates on quic15 anomaly10
- quic15 anomaly10

## 2018-10-23

### Other

- fixed bug implicit universal quantifiers in fragment checker
- adding migration rules
- fixed bug in path_response in quic15
- fixed bug with return_context and boolean ops

## 2018-10-19

### Other

- diagnosed picoquic anomaly9
- Update setup.py

* add a long description from README
* use codecs to prevent the crash during the installation on machines with non-standard locales.

## 2018-10-17

### Other

- updating transport parameters to quic15

## 2018-10-16

### Other

- serdes fixes for quic15
- about to switch to version 15

## 2018-10-15

### Other

- quic15 changes
- adding ivy_libs.py

## 2018-10-12

### Other

- picoquic anomaly9
- two client endpoints in quic15 tester
- working on migration in quic15

## 2018-10-11

### Other

- adding new_connection_id in quic15

## 2018-10-09

### Other

- anomaly8
- more on testing
- working on quic test framework

## 2018-10-08

### Other

- ivy-mode.el: clean up

* use standard source layout
* add packaging directives
* use defconst/defvar for top-level variables
* add customize-group for and customize variables for user-editable
  variables

## 2018-10-04

### Other

- working on stream frame testing in quic14
- testing max_stream_data in quic14

## 2018-10-03

### Other

- quic14 connectino close seems to work
- details for quic14 anomaly7
- quic14 anomaly7
- modified quic14 spec for anomaly6
- quic14 anomaly6
- small fixes
- more graphviz problems

## 2018-10-02

### Other

- fixed problem with bmc in cti mode and initializers
- fixes to ivy_graphviz
- Update README.md

Added installation commands for linux and windows.

## 2018-09-27

### Other

- working on parsing partial TLS messages in quic14

## 2018-09-26

### Other

- quic14 test rst_stream seems to work
- working on rst_stream in quic14
- quic14 packet number problem temporarily fixed

## 2018-09-25

### Other

- in quic14 test, can send stream frames, but packet number decoding is incorrect

## 2018-09-24

### Other

- acks seem to work in quic14 test

## 2018-09-22

### Other

- working on acks in quic14 tester

## 2018-09-20

### Other

- extending macro instantiation
- trying to send bytes to tls in quic14

## 2018-09-19

### Other

- got up to tls_recv_event on quic14 test
- got one quic14 packet sent to server

## 2018-09-18

### Other

- small fixes for quic14 tester
- working on tester for quic14

## 2018-09-17

### Other

- can monitor picoquic.pcap

## 2018-09-15

### Other

- working on picoquic.pcap

## 2018-09-13

### Other

- working on quic14 deser

## 2018-09-12

### Other

- some changes for CORE
- fix handling of cids in quic

## 2018-09-11

### Other

- performance fixes for quic_server_test
- minquic anomaly
- fixing up dependent parameters and quic_server_test

## 2018-09-07

### Other

- adding constructor axioms

## 2018-09-06

### Other

- finishing window_adt

## 2018-09-05

### Other

- creport2.ivy
- fixing mc merge
- creport example

## 2018-09-03

### Other

- adding file

## 2018-08-23

### Other

- working on dependend fields

## 2018-08-11

### Other

- working on dependent input fields

## 2018-08-10

### Other

- in the middle of adding dependent inputs in test

## 2018-08-09

### Other

- quic_server_test can generate data packet, but very slowly

## 2018-08-08

### Other

- more gnutls

## 2018-08-07

### Other

- working on gnutls

## 2018-08-04

### Other

- updating install instructions

## 2018-08-03

### Other

- testing gnutls

## 2018-07-31

### Other

- quic tls work

## 2018-07-26

### Other

- working on quic_server_test, adding extensions to tls

## 2018-07-25

### Other

- forgotten files

## 2018-07-04

### Other

- fol command is actually fo

## 2018-06-29

### Other

- reverse breaking change to array spec
- working on quic_server_test
- adding deserializer for quic

## 2018-06-27

### Other

- added serializer/deserializer parameters to udp_impl
- adding udp_impl

## 2018-06-25

### Other

- update udp_test to 1.7, remove debugging from ivy_parser

## 2018-06-19

### Other

- can generate full tls handshake, z3 slow

## 2018-06-18

### Other

- hooking tls up to quic

## 2018-06-17

### Other

- moving to QUIC version 11

## 2018-06-16

### Other

- working on quic generation

## 2018-06-12

### Other

- adding intbv

## 2018-06-10

### Other

- small ivy_to_cpp fix

## 2018-06-09

### Other

- refactored quic_connection into smaller actions

## 2018-06-08

### Other

- added override attribute
- fixing test bugs

## 2018-06-07

### Other

- added inference of TLS events

## 2018-06-06

### Other

- starting quic test branch

## 2018-06-05

### Other

- adding tls

## 2018-05-31

### Other

- adding quic traces
- more quic frames

## 2018-05-30

### Other

- added quic max_stream_data frames
- working on quic close connection frame

## 2018-05-29

### Other

- adding parsers for quic stream_reset and max_stream_id frames
- adding parsers for quic stream_reset and max_stream_id frames
- forgotten file

## 2018-05-28

### Other

- updating docs
- update some examples for new array module
- fixing ivy_to_cpp problem
- some work on back pressure in quic

## 2018-05-26

### Other

- quic spec additions
- fixing parser problem (combining term and fmla)

## 2018-05-25

### Other

- working on transport parameters

## 2018-05-24

### Other

- tls_deser starting to work

## 2018-05-23

### Other

- adding fragment tests, fixing list_reverse doc

## 2018-05-22

### Other

- checking in ivy_to_md
- fixes to fragment checker

## 2018-05-21

### Other

- doc fixes

## 2018-05-18

### Other

- starting decidability doc

## 2018-05-17

### Other

- fixing some problems with ivy_to_cpp
- theorem branch passes tests
- handle weird quoting of names in recent z3
- handling finite types in new fragment checker

## 2018-05-16

### Other

- fixing up proving doc
- fixing induction example in indexset
- ivy_prover problems

## 2018-05-15

### Other

- sht works again

## 2018-05-12

### Other

- sht still not working
- fixing bugs in new fragment checker

## 2018-05-11

### Other

- passes run_expects
- working on new fragment checker

## 2018-05-10

### Other

- working on new fragment checker

## 2018-05-09

### Other

- indexset works
- trying to get indexset to work again

## 2018-05-08

### Other

- working on array reverse example

## 2018-05-07

### Other

- adding normalize_ops

## 2018-05-05

### Other

- working on alpha conversion bugs

## 2018-05-04

### Other

- working on example theorems

## 2018-05-03

### Other

- fixing proof order
- fixing ivy_to_md
- proving.ivy almost works

## 2018-05-02

### Other

- working on proving doc

## 2018-05-01

### Other

- fixing quic instructions
- stashing
- stashing again

## 2018-04-30

### Other

- stashing

## 2018-04-28

### Other

- working on proving.md

## 2018-04-27

### Other

- working on dox

## 2018-04-26

### Other

- fixing list_reverse.md
- fixing list_reverse.md
- fixing list_reverse.md
- adding list_reverse.md
- quic readme fix
- spelling
- adding README.md
- adding dox
- forgotten file
- working on array reversal example

## 2018-04-25

### Other

- alpha conversion seems to be working
- working on alpha conversion

## 2018-04-24

### Other

- working on capture
- fix for matching
- working on capture in ivy_proof

## 2018-04-23

### Other

- fixing tactic compilation

## 2018-04-21

### Other

- still on theorem prover

## 2018-04-20

### Other

- working on assume tactic

## 2018-04-19

### Other

- working on prover

## 2018-04-18

### Other

- fixing some fragment checker bugs

## 2018-04-17

### Other

- autoinstance and struct
- implementing autoinstance
- adding TLS records
- starting TLS interface

## 2018-04-16

### Other

- fixed unsoundness: added detection of free variables in if conditions
- something for quic
- testing markdown syntax
- working on ivy_to_md
- quic to md
- adding ivy_to_md

## 2018-04-15

### Other

- quic anomalies
- anomaly in minquic

## 2018-04-13

### Other

- added "isa"
- small cleanup to quic

## 2018-04-11

### Other

- fixed glitch in example
- fixing tcp thread leak problems

## 2018-04-07

### Other

- removed Z3 paths from repl compile
- more on quic

## 2018-04-06

### Other

- fixes for object continuations, C++ thunks, quic
- fixed broken packet nuymber decode in quic
- fix for ivyc
- adding ivyc command

## 2018-04-05

### Other

- fixing large integer constants
- forgot ip.ivy
- forgot pcap.ivy
- getting quic running
- adding quic files
- middle of something

## 2018-04-04

### Other

- fixed socket leak in tcp
- quic stream packets parse

## 2018-04-03

### Other

- fixing some error messages in ivy_isolate
- tcp send queueing seems to be working
- messing with queueing tcp sends

## 2018-04-02

### Other

- added "segment" module to collections
- messing with deser

## 2018-03-30

### Other

- starting on frame parsing

## 2018-03-29

### Other

- fix to bug in ivy_socket_deser affecting tcp

## 2018-03-24

### Other

- moving some files

## 2018-03-23

### Other

- small doc change
- parsing the QUIC packet headers and tracking packet number seem to work
- small changes for testing TCP

## 2018-03-22

### Other

- relaxed interference rule for initializers
- adding hex output

## 2018-03-13

### Other

- working on disk_token_ring

## 2018-03-12

### Other

- still working on thunk

## 2018-03-10

### Other

- working on thunk
- variants seem to be sort of working

## 2018-03-09

### Other

- disk sync callbacks seem to work

## 2018-03-08

### Other

- file works in crashpong1
- adding disk impl to crashpong1

## 2018-03-07

### Other

- added crashpong example
- adding crash

## 2018-03-06

### Other

- added TCP_NODELAY
- tcp support added to stdlib
- tcp seems to be working

## 2018-03-05

### Other

- fixed unsoundness in interference check
- still working on tcp

## 2018-03-02

### Other

- working on tcp

## 2018-02-27

### Other

- fixed bug in get_isolate_attr
- small change to ivy_mc
- fixed error message in ivy_isolate
- finite model checking working for flash2

## 2018-02-24

### Other

- fixing model checking cex output
- fixing mc macro bug

## 2018-02-23

### Other

- added attributes method and separate
- added mc schemata to std include
- implemented separate option

## 2018-02-22

### Other

- fixing up vsync_paxos

## 2018-02-21

### Other

- fixed isolate parameter check bug
- fixed but introduced by multiple inits
- fixed with in ivy_isolate.py

## 2018-02-20

### Other

- adding if tactic

## 2018-02-18

### Other

- fixed strlit deser

## 2018-02-17

### Other

- allowing multiple after and before mixins for a given action in same name space
- fixed bug that spuriously added undefined "with" arguments to hierarchy

## 2018-02-16

### Other

- added trace option to docs
- fixed broken test
- still on trace

## 2018-02-14

### Other

- improved error message about invariants
- compile quantifiers over iterable
- adding seed and incremental options

## 2018-02-13

### Other

- fixed bug in VC generator that caused formulas with many quantifiers
- fixed error message on inconsistent axioms/initial conditions
- fixes bug with type object alias and with

## 2018-02-08

### Other

- fixing proof syntax
- fix for timeout.ivy

## 2018-02-07

### Other

- fix FAIL PASS problem
- doc fix
- added some command-line docs

## 2018-02-06

### Other

- making assert=lineno option apply to invariants
- added option for z3 macro_finder
- turn off run-time checking of invariants
- fixed problem with asserts at same line number in different actions

## 2018-02-05

### Other

- messing with yacc bugs

## 2018-01-29

### Other

- removing unneeded lemmas from vsync_paxos_ms

## 2018-01-24

### Other

- ibm-cache-N works with invariants
- starting on ibm-cache-N with invariants
- toma8.ivy works
- vsync_paxos works, needs cleanup

## 2018-01-23

### Other

- still working on vsync_paxos
- still on vsync_paxos

## 2018-01-22

### Other

- still working on vsync_paxos

## 2018-01-21

### Other

- problem with quantifiers in assumptions in mc

## 2018-01-20

### Other

- working on vsync_paxos_mc

## 2018-01-19

### Other

- starting vsync_paxos
- flash2_mc works

## 2018-01-18

### Other

- flash2 invariant works
- working on flash with induction

## 2018-01-17

### Other

- flash_mc works
- working on flash_mc

## 2018-01-16

### Other

- toma8_mc works
- working on assert in mc

## 2018-01-15

### Other

- toma8_mc reservation ststaino properties ok
- stop logic.py from commuting disjunctions

## 2018-01-13

### Other

- working on tomasulo

## 2018-01-12

### Other

- fixing let tactic

## 2018-01-11

### Other

- added let tactic, invariant proofs

## 2018-01-03

### Other

- got rid of some extraneous stvars in mc

## 2018-01-02

### Other

- schema instantiation works for ibm-cache-N
- schema instantiation works for client_server_mc3
- forgotten
- adding German cache model
- working on schemata in mc

## 2018-01-01

### Other

- client_server_mc2 works

## 2017-12-29

### Other

- forgotten
- forgotten files
- more fixes for enums in gui

## 2017-12-28

### Other

- fix bug in ivy_graph.py
- abstract conterexample OK on client_server_mc.ivy

## 2017-12-27

### Other

- working on model checking counterexamples

## 2017-12-23

### Other

- starting to add annotations to transition relatiosns
- about to work on trace generation
- Typo on #29

And some minor fixes (proposal)
- Typo on #01
- Update URL
- Typos
- useless commit

## 2017-12-22

### Other

- getting possibly good abstract counterexample for client_server_mc.ivy

## 2017-12-21

### Other

- nowhere
- quantifier instantation in mc partly works

## 2017-12-20

### Other

- axiom instantiation partly works
- starting on propositional abstraction

## 2017-12-19

### Other

- fix "if *" regression
- working on enumerated types
- fixed skolemization bug

## 2017-12-18

### Other

- working on encoding finite sorts

## 2017-12-16

### Other

- starting on ivy_mc

## 2017-12-15

### Other

- workaround for Jekyll relative path bug
- jekyll test
- jekyll test
- some doc updates for 1.7
- toy_consensus now compiles and runs

## 2017-12-14

### Other

- fixed tilelink regression
- working on parameter

## 2017-12-13

### Other

- toy_consensus compiles
- toy_consensus verifies but does not compile

## 2017-12-12

### Other

- working on method call with variables
- still working on toy_consensus

## 2017-12-10

### Other

- working on toy_consensus

## 2017-12-09

### Other

- working on toy_consensus

## 2017-12-08

### Other

- invariant seems to work, updating docs
- forgotten file
- working in invariant

## 2017-12-07

### Other

- working on invariant
- implemented require and ensure
- specifiction, implementation, private seem ok
- implememting specifiction, implementation, private

## 2017-12-06

### Other

- fixing reporting of implementations and monitors
- updating docs for summary
- added back assert= feature
- passes tests

## 2017-12-05

### Other

- foo

## 2017-12-04

### Other

- adding "type this"

## 2017-12-01

### Other

- further cleanup of sht table and docs
- cleaning up sht table
- sht table is working again
- trying to get sht to work again

## 2017-11-30

### Other

- working on updateing docs to 1.7

## 2017-11-29

### Other

- three soundness fixes seem to work

## 2017-11-28

### Other

- working on unsoundness
- cone passes tests

## 2017-11-27

### Other

- temporary
- still working on cone

## 2017-11-23

### Other

- working on cone reduction

## 2017-11-21

### Other

- fixed tester to unlovk object after construction
- fixed call with variable on lhs
- getting call by reference to work with method calls

## 2017-11-18

### Other

- working on parameter aliasing

## 2017-11-17

### Other

- fixed bug in sequence_iterator

## 2017-11-16

### Other

- adding inplace modification

## 2017-11-14

### Other

- fixing UDP config problems

## 2017-11-07

### Other

- adding config to udp
- some fixes for class extraction
- cancel threads on class destructor
- added sleep to class example
- class creation might be working
- threads might be working

## 2017-11-03

### Other

- do not havoc parameters if compiling

## 2017-11-02

### Other

- reinstanted z3 macro_finder option

## 2017-10-31

### Other

- fixed fragment checker bug

## 2017-10-16

### Other

- fixed in/out parameter bug and array.set bug, removed Z3 macro_finder option which produced bad models

## 2017-10-04

### Other

- fixed unsoundness in function definitions
- integrating liveness

## 2017-10-02

### Other

- integrating odedp liveness branch

## 2017-09-27

### Other

- fix

## 2017-08-10

### Other

- fixed regressions

## 2017-08-05

### Other

- fixes for testing vsp

## 2017-08-04

### Other

- changed isolate semantics for properties

## 2017-08-03

### Other

- working on extracting vsp

## 2017-08-02

### Other

- fixing fragment checker

## 2017-08-01

### Other

- workaround for MBQI looping in z3

## 2017-07-31

### Other

- debugging fragment checker

## 2017-07-21

### Other

- working on vsp

## 2017-07-20

### Other

- fix error messages
- working on vsp

## 2017-07-18

### Other

- adding ivy/README.md
- fixing fragment checker to allow quantifiers over finite sorts

## 2017-07-13

### Other

- removed debug pring
- fixed module reference in ivy_show

## 2017-07-12

### Other

- fix indexset3.ivy

## 2017-07-10

### Other

- fixing fragment checker and prover

## 2017-07-09

### Other

- adding comments
- working on fragment checker, indexset3.ivy

## 2017-07-08

### Other

- working on theory fragment checker

## 2017-07-07

### Other

- remove debugging assert
- working on fragment check

## 2017-07-05

### Other

- fixed problem with alias in native code
- fix for hang in get_small_model when axioms are not EPR
- misc fixes
- fix for cal with method syntax

## 2017-07-04

### Other

- fix error messages
- install doc fix
- temporary fix for parser infinite loop
- fixing indexset2.ivy

## 2017-07-03

### Other

- working on prover

## 2017-07-01

### Other

- working on prover

## 2017-06-29

### Other

- add file
- fixes for matching
- working on prover documentation

## 2017-06-28

### Other

- extending isolate
- working on named

## 2017-06-26

### Other

- working on recursion
- fix for run_expects
- fix for z3-4.5.0

## 2017-06-25

### Other

- working on recursion

## 2017-06-24

### Other

- forgotten file
- working on recursive definitions

## 2017-06-21

### Other

- toy_consensus and fixes

## 2017-06-12

### Other

- Fixed trace=true in an action without parameters
- proof of majority property

## 2017-06-11

### Other

- cardinality tests

## 2017-06-10

### Other

- fix for udp and tcp
- removing tabs from MSV examples
- adding MSV examples
- small doc fix

## 2017-06-06

### Other

- doc fixes

## 2017-05-22

### Other

- adding file

## 2017-05-21

### Other

- updating installation documentation
- support built-in z3

## 2017-05-19

### Other

- added empty transition target in scenario
- fix for mixin parameter inference

## 2017-05-18

### Other

- remove debug prints
- fixing scenario bugs
- adding scenario after transitions
- small fix

## 2017-05-16

### Other

- clarification in installation instructions.

## 2017-05-15

### Other

- initial implementation iof scenario

## 2017-05-12

### Other

- fixes for windows
- clarification in installation instructions.
- fix typos.
- update `README.md` with installation instructions.

## 2017-05-11

### Other

- update `.vscode/settings.json` with more ignore patterns.
- open text files with newline translation support (missing files from previous commit).
- open text files with newline translation support (mode `rU` instead of `r`).
- adjust z3 PYTHONPATH setting to be compatible with version of z3 used.
- separate ivy dependencies from other apt packages.
- checkout compatible z3 submodule commit.
- got ivy gui working over ssh with x11 forwarding.

## 2017-05-09

### Other

- cross-pollinate with flutterbye vagrant/installation scripts.

## 2017-05-08

### Other

- working on windows release
- working on windows release

## 2017-05-05

### Other

- fix bugs in python environment setup.
- rename `scripts/setup/userspace.sh` to `.../userland.sh`.
- add python to path.

## 2017-05-04

### Other

- tests now pass

## 2017-05-03

### Other

- from class dry run
- updated `Vagrantfile` from latest in `flutterbye` repository.

## 2017-04-19

### Other

- partially fixing strbv overflow problem

## 2017-04-15

### Other

- allow native quote in after, improve loop bound detection

## 2017-04-11

### Other

- added bit vector ops

## 2017-03-30

### Other

- fixes for MSV

## 2017-03-29

### Other

- adding VS solutions for MSV
- working on MSV exercises

## 2017-03-28

### Other

- fixes for windows and udp.ivy
- working on MSV examples

## 2017-03-27

### Other

- visual studio extension
- visual studio integration

## 2017-03-26

### Other

- changes for vs and multiple compile

## 2017-03-25

### Other

- working on tutorial
- fix to nested destructor assignment

## 2017-03-22

### Other

- working on nested field references

## 2017-03-18

### Other

- forgotten file
- forgotten file
- repstore3 is working

## 2017-03-17

### Other

- repstore2 and repstore2bug are working
- repstore2 and repstore2bug are working
- adding sequential repstore

## 2017-03-16

### Other

- repstore seems to be working
- still working on repstore example
- sorking on repstore example

## 2017-03-15

### Other

- working on variants

## 2017-03-14

### Other

- working on replicated key/value store example

## 2017-03-13

### Other

- working on chain rep example

## 2017-03-12

### Other

- adding options to tester
- forgotten file

## 2017-03-11

### Other

- fixing many bugs

## 2017-03-07

### Other

- working on variants
- fixed error in setup.py

## 2017-03-05

### Other

- trying to make symbolic execution more efficient
prompt

## 2017-03-03

### Other

- about to try improving symbolic execution
prompt

## 2017-03-02

### Other

- update z3 submodule

## 2017-02-28

### Other

- simplify `Vagrantfile`.

## 2017-02-23

### Other

- more fixes for ivyspec

## 2017-02-22

### Other

- update `.gitattributes` for shell scripts.
- some fixes for ivyspec
- exclude files in vscode workspace settings.

## 2017-02-20

### Other

- fixes

## 2017-02-19

### Other

- z3 now works in vagrant environment.

## 2017-02-17

### Other

- use git root detection instead of relative paths in provisioning scripts.

## 2017-02-16

### Other

- added vagrantfile, z3 submodule, and setup scripts.

## 2017-02-11

### Other

- handle empty struct

## 2017-02-02

### Other

- fix to parsing of numeric arrays in repl

## 2017-01-30

### Other

- fixed but in integer constant thunks

## 2017-01-27

### Other

- various fixes

## 2017-01-25

### Other

- changed assert to exit on strbv overflow

## 2017-01-24

### Other

- fix for redirect on windows
- fixing redirect
- adding output redirect for test
- changed null_type module to use 0x7fffffff for null value

## 2017-01-23

### Other

- fixed bug in to_solver for arrays
- generation bug

## 2017-01-20

### Other

- serialization fixes

## 2017-01-17

### Other

- add encoding feature

## 2017-01-12

### Other

- fixes for var bug and method call
- event parsing fixes

## 2017-01-10

### Other

- some fixes for repl on windows

## 2017-01-05

### Other

- working on var
- windows porting

## 2017-01-03

### Other

- some changes for z3.py changes

## 2016-12-31

### Other

- working on var
- strbv type seems to work

## 2016-12-30

### Other

- adding strbv, delegate is not working...

## 2016-12-26

### Other

- working on gen for strings

## 2016-12-25

### Other

- working on loop unrolling

## 2016-12-24

### Other

- removing -lz3 from repl compile

## 2016-12-23

### Other

- fixing field handling, extending to actions

## 2016-12-22

### Other

- still trying to break dependency
- still trying to break dependency

## 2016-12-21

### Other

- trying to remove dependency on pygraphviz
- added destructor references with dot notation

## 2016-12-20

### Other

- fixing repl with trace

## 2016-12-19

### Other

- adding isolate = this

## 2016-12-17

### Other

- working on event viewer

## 2016-12-14

### Other

- more repl tests

## 2016-12-13

### Other

- more repl tests
- cleaning up
- workiong on testing repls

## 2016-12-08

### Other

- not much
- testing tests pass

## 2016-12-06

### Other

- adding testing regression tests

## 2016-12-05

### Other

- unknown

## 2016-12-04

### Other

- eliminating unused definitions in test gen
- adding before_exports

## 2016-12-03

### Other

- arraygen.ivy
- unknown

## 2016-11-29

### Other

- working on testing

## 2016-11-19

### Other

- fixing up target=test

## 2016-11-18

### Other

- working on compiling strings, enums

## 2016-11-17

### Other

- fixing bugs
- adding string type

## 2016-11-15

### Other

- working on event viewer
- working on event viewer

## 2016-11-14

### Other

- adding event viewer

## 2016-11-12

### Other

- adding event parser

## 2016-11-11

### Other

- testing fixes

## 2016-11-08

### Other

- fixing test bugs

## 2016-10-25

### Other

- removed some debug prints
- fixed problems with implicit imports

## 2016-10-21

### Other

- fixing up chord example

## 2016-10-20

### Other

- typo

## 2016-10-19

### Other

- fixed run_expects
- fixed bug with abstracted "after init"

## 2016-10-17

### Other

- more changes
- change

## 2016-10-09

### Other

- changed cycle counting for timeouts
- reduced timeout for test harness to 1ms
- fixed bug reported no im[plementation for imported action
- removed () from test logs
- removed ext: from test logs
- fixed import action bug in ivy_isolate.py

## 2016-10-04

### Other

- fixed ivy_to_cpp thunk bug
- tests pass
- fixed bug in ivy_isolate.pu

## 2016-10-03

### Other

- fixed bug in interference check

## 2016-10-01

### Other

- working on testing tutorial

## 2016-09-29

### Other

- works testing buggy transport layer

## 2016-09-28

### Other

- simple example of generating structures is working
- more on generating structs
- working on token ring example

## 2016-09-26

### Other

- working on hash thunk

## 2016-09-25

### Other

- adding hash thunk

## 2016-09-21

### Other

- finished leader example in testing tutorial

## 2016-09-20

### Other

- working on testing tutorial

## 2016-09-19

### Other

- working on testing tutorial

## 2016-09-17

### Other

- working on target=test

## 2016-09-15

### Other

- passes regressions
- sht tutorial completed
- sharded hash table tutorial runs
- sht tutorial example checks
- working on sht tutorial

## 2016-09-14

### Other

- added doc page on sht trans
- reworking sht queue

## 2016-09-13

### Other

- adding trans module to sht tutorial

## 2016-09-12

### Other

- reworking delmap

## 2016-09-11

### Other

- adding table doc

## 2016-09-10

### Other

- table_test works
- adding files
- adding file
- fixing bugs for sht example

## 2016-09-09

### Other

- adding files
- starting tutorial on sht

## 2016-09-08

### Other

- all tests pass and tutorial examples run
- more bug fixing
- more bug fixes
- bug fixing

## 2016-09-07

### Other

- bug fix
- cleaning up bugs

## 2016-09-06

### Other

- working on arrayset

## 2016-09-05

### Other

- working on bounded quantifiers, arrayest example

## 2016-09-03

### Other

- working on arrays

## 2016-09-01

### Other

- sht running multi-process

## 2016-08-31

### Other

- added reply messages to sht
- really fixing sht liveness bug
- sht liveness fix
- sht compiles
- working on compiling sht

## 2016-08-30

### Other

- putting sht together

## 2016-08-29

### Other

- sht trans checks
- workin on sht table

## 2016-08-28

### Other

- working on sht

## 2016-08-27

### Other

- working on sht table proof
- working on per-assertion checking

## 2016-08-26

### Other

- working on definition unfolding
- working on definition unfolding

## 2016-08-25

### Other

- sht table is tested
- test_table compiles
- working on sht

## 2016-08-24

### Other

- working on struct
- working on structs

## 2016-08-23

### Other

- adding while

## 2016-08-20

### Other

- working on "for some" and collections.ivy

## 2016-08-19

### Other

- fixing target=gen problem"
- addint initializers

## 2016-08-18

### Other

- working in parameterized init

## 2016-08-17

### Other

- working on networking doc

## 2016-08-16

### Other

- working on C++ callbacks

## 2016-08-14

### Other

- working on udp

## 2016-08-13

### Other

- working on select in runtime
- working on extract

## 2016-08-12

### Other

- working on leader in REPL

## 2016-08-11

### Other

- adding helloworld section
- working on native code and repl

## 2016-08-08

### Other

- adding foreign function interface and REPL support

## 2016-08-06

### Other

- adding leader section to doc, improving diagram

## 2016-08-05

### Other

- still working on prettifying

## 2016-08-04

### Other

- working on prettier formula printing

## 2016-08-03

### Other

- lots of debugging, fixing model_to_diagram

## 2016-08-02

### Other

- fixing issues with instance paramenters and implicit parameters to mixins

## 2016-08-01

### Other

- fix for issue #1
- fix broken link

## 2016-07-30

### Other

- adding doc example
- adding property

## 2016-07-29

### Other

- adding types in objects and inequality macros

## 2016-07-27

### Other

- improving coverage check messages
- adding implement

## 2016-07-26

### Other

- added before and after declarations

## 2016-07-16

### Other

- fixing completeness check

## 2016-07-15

### Other

- adding completeness check

## 2016-07-14

### Other

- fixing interference check
- fixing sht example, fixing boolean locals

## 2016-07-09

### Other

- starting check_interference

## 2016-07-08

### Other

- add "private"

## 2016-07-07

### Other

- fixing ivy_check and some bmc problems
- fixing ivy_check

## 2016-07-06

### Other

- modified tilelink test makefile to keep up with tilelink refactoring
- pulled out boilerplate into std
- factored out ordered_set structure

## 2016-07-05

### Other

- sht_abs working with stripping
- working on stripping isolate parameters
- sht delegationmap impl proof works but messy

## 2016-07-04

### Other

- working on sht delegation map

## 2016-07-02

### Other

- working on maximizing/minimizing

## 2016-07-01

### Other

- updated tests for new project structure
- updated tests for new project structure
- modified tilelink spec to require ordered release beats
- adding destructor and some

## 2016-06-29

### Other

- fixing inconsistency in sht example

## 2016-06-25

### Other

- working on destructors

## 2016-06-23

### Other

- fixed tilelink spec handle grants without data

## 2016-06-14

### Other

- fixing ivy_theory and working on sht refinement

## 2016-06-13

### Other

- fixing cti regression
- workaround for Z3 EPR incompleteness
- workaround for z3.py regression in z3 4.4.2
- fixed file not found reporting
- fixing plugin loading regression
- fixing error reporting in ivy_to_cpp

## 2016-06-10

### Other

- starting to refine network model in sht

## 2016-06-09

### Other

- added test for ivy_to_cpp
- fixed some regressions in ivy_to_cpp

## 2016-06-08

### Other

- added Mac installation notes

## 2016-06-07

### Other

- adding Windows install documentation
- fixing up for python packaging

## 2016-06-04

### Other

- fixing ivy_test
- reorg for python package

## 2016-06-03

### Other

- fixing projections in new ui, adding test
- working on sharded hash table

## 2016-06-01

### Other

- forgotten file
- raft log model changes

## 2016-05-31

### Other

- adding raft_logs example

## 2016-05-28

### Other

- adding diagram to cti

## 2016-05-27

### Other

- fixing home page again
- fixing home page again
- fixing home page
- fixing README
- fixing up regression tests

## 2016-05-26

### Other

- invariant example and cti issues
- working on induction example

## 2016-05-25

### Other

- adding docs

## 2016-05-24

### Other

- adding website deployment cruft
- trying to fix github url problem
- adding web site
- adding assertion check to cti tui and some docs

## 2016-05-21

### Other

- working on language features

## 2016-05-20

### Other

- adding to language doc

## 2016-05-19

### Other

- removed some prints
- still fixing regressions in gui_refactor
- fixing regressions in gui_refactor
- fix for zero size pane in tk gui

## 2016-05-18

### Other

- give line numbers of asserts in ivy_to_cpp, fixed serialization issue in tilelink testbench
- cleanup for tilelink unit tester

## 2016-05-17

### Other

- cleaning up tilelink tester
- fixed some regressions on tilelink unit tester

## 2016-05-13

### Other

- added instructions for getting uncore configs from kenmcmil fork
- removed old targets from tilelink/unit_test/Makefile
- fixed backward compat problem parsing concept spaces

## 2016-05-06

### Other

- new gui does leader example pretty well

## 2016-05-05

### Other

- working on leader example

## 2016-05-04

### Other

- working on ivy_ui_cti.py
- created ivy_ui_cti.py
- still working on transition widget in new gui
- working on transition widget in new gui

## 2016-05-03

### Other

- adding ui plugins

## 2016-05-02

### Other

- fixing transitive relations in new gui

## 2016-04-29

### Other

- fixing new gui problems

## 2016-04-28

### Other

- fixed tilelink proof

## 2016-04-27

### Other

- fixing "delegate to"
- adding mixord and "delegate to"

## 2016-04-26

### Other

- fix to ivy_to_cpp
- working on check

## 2016-04-25

### Other

- working on gui refactor

## 2016-04-22

### Other

- working on check

## 2016-04-21

### Other

- adding ivy_check

## 2016-04-20

### Other

- working on theory checking

## 2016-04-19

### Other

- working on toy_lock proof
- got toy_lock working over UDP

## 2016-04-15

### Other

- working on code extraction

## 2016-04-14

### Other

- working on emitting code for toy lock example

## 2016-04-13

### Other

- gui refactor, working on ART

## 2016-04-12

### Other

- refactoring gui, adding tests
- still in ui refactor

## 2016-04-11

### Other

- still on gui refactor

## 2016-04-10

### Other

- still on gui refactor

## 2016-04-09

### Other

- still in ui refactor

## 2016-04-08

### Other

- rearranging example files and adding gitignore files
- still on concept graph refactor

## 2016-04-07

### Other

- starting concept graph refactor

## 2016-04-06

### Other

- still refactoring ui
- refactoring GUI to use MVC pattern

## 2016-04-04

### Other

- added emacs mode
- refactoring ui

## 2016-04-03

### Other

- fixing some ui issues

## 2016-04-02

### Other

- working on bit vectors

## 2016-04-01

### Other

- refining toy lock model
- more on refinement

## 2016-03-30

### Other

- adding after mixins
- still working on integer support

## 2016-03-29

### Other

- adding integer support
- bigger example
- adding int support

## 2016-03-23

### Other

- adding forgotten file

## 2016-03-21

### Other

- fixes for l2

## 2016-03-20

### Other

- working on tilelink progress properties

## 2016-03-19

### Other

- working on progress properties

## 2016-03-17

### Other

- adding workaround for uncached op problem

## 2016-03-16

### Other

- updated README
- shows uncore issue 29
- handling derived predicates in test gen

## 2016-03-15

### Other

- adding language doc

## 2016-03-12

### Other

- adding testbench support for uncached tilelink clients
- Makefile
- update README

## 2016-03-11

### Other

- update README
- shows uncore issue 23

## 2016-03-10

### Other

- not much

## 2016-03-09

### Other

- getting BroadcastHub to work again
- small tilelink changes

## 2016-03-08

### Other

- making compatible with tilelink uncore unit-testing branch

## 2016-03-07

### Other

- shows uncore issue 20
- install fixes

## 2016-03-06

### Other

- adding ivytocpp
- adding install instructions

## 2016-03-03

### Other

- working on L2 cache

## 2016-03-02

### Other

- L2CACHE bug #1

## 2016-03-01

### Other

- some tilelink spec refactoring

## 2016-02-29

### Other

- BroadcastHub running without issues

## 2016-02-27

### Other

- working on multi-client tilelink spec

## 2016-02-26

### Other

- added manager txids to tilelink spec
- working on BroadcastHub, about to change txids in tilelink_concrete_spec
- working on BroadcastHub

## 2016-02-25

### Other

- working on coherence manager tester

## 2016-02-24

### Other

- working on test harness to tilelink coherence manager

## 2016-02-22

### Other

- working on tilelink tester
- adding Makefile for tilelink tester
- working on tilelink tester

## 2016-02-20

### Other

- working on c++ test generation

## 2016-02-19

### Other

- working on c++ test generation

## 2016-02-15

### Other

- Cleaned up examples/pldi16
- Better structure_renaming for nicer projections.
- Fixed off by 1 bug in bmc_conjecture.
- Fixed bug in ivy_bmc.py
- Added ivy_bmc.py and hide redundent graphs and buttons from IvyMain widget.
- Converted leader election to ivy1.3 + started converting database_chain_replication.

## 2016-02-14

### Other

- Added fixing of random seeds, and fixed bug causing gray edges.
- Added missing file: widget_cy_graph_iframe.html
- Started to convert pldi16 examples to ivy1.3
- More adjustments to the new UI.
- Added .gitignore
- Updated the new UI and the CTI based interaction mode to work with function symbols.

For now, switched to numerals=False, since numerals break the assumptions of the type inference, which is used by concept.py.

## 2016-02-13

### Other

- adding ivy_to_cpp

## 2016-02-12

### Other

- fix learning switch example

## 2016-01-29

### Other

- comments

## 2016-01-22

### Other

- protocol props checked for tilelink_concrete_directory.ivy
- working on tilelink directory model
- adding tilelink directory example

## 2016-01-21

### Other

- protocol props checked for tilelink_concrete_snoopy.ivy
- cleaning up tilelink spec
- protocol props checked for tilelink_concrete_unordered_channel.ivy
- working on tilelink invariants
- working on tilelink invariant

## 2016-01-20

### Other

- working on tilelink invariants
- working on tilelink invariant

## 2016-01-19

### Other

- working on tilelink invariants
- working on tilelink invariant

## 2016-01-18

### Other

- working on tilelink invariants

## 2016-01-17

### Other

- fixing tilelink invariant

## 2016-01-16

### Other

- fixing tilelink invariant
- wotking on tilelink invariant

## 2016-01-15

### Other

- working on tilelink invariants

## 2016-01-14

### Other

- fixing tilelink spec

## 2016-01-13

### Other

- fixing tilelink spec

## 2016-01-12

### Other

- adding tilelink_concrete_snoopy

## 2016-01-11

### Other

- added logic option, worked on tilelink

## 2016-01-09

### Other

- adding forgotten file
- fixing tilelink specs

## 2016-01-08

### Other

- fixing tilelink specs

## 2016-01-07

### Other

- decomposing failure actions

## 2016-01-06

### Other

- fixing bugs in decompose

## 2016-01-05

### Other

- line number improvements

## 2016-01-04

### Other

- line number tracking fixes
- removed a print
- improved formatting of edge labels in ART
- adding view source
- adding file name tracking
- adding action decomposition

## 2016-01-03

### Other

- fix to tilelink concrete spec
- concept graph color fix
- working on ui

## 2016-01-02

### Other

- working on concrete tilelink

## 2016-01-01

### Other

- working on tilelink_concrete_spec.ivy

## 2015-12-28

### Other

- adding examples, notebooks
- adding ivy2 sources
- adding ivy sources
- adding license.txt
- adding .gitattributes
- Initial commit
