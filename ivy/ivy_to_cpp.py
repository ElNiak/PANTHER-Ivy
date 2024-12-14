#! /usr/bin/env python
#
# Copyright (c) Microsoft Corporation. All Rights Reserved.
#

from . import ivy_init
from . import ivy_logic as il
from . import ivy_module as im
from . import ivy_utils as iu
from . import ivy_actions as ia
from . import logic as lg
from . import logic_util as lu
from . import ivy_solver as slv
from . import ivy_transrel as tr
from . import ivy_logic_utils as ilu
from . import ivy_compiler as ic
from . import ivy_isolate as iso
from . import ivy_ast
import itertools
from . import ivy_cpp
from . import ivy_cpp_types
from . import ivy_fragment as ifc
import sys
import os
import platform

from collections import defaultdict
from operator import mul
import re
from functools import reduce


def all_state_symbols():
    """
    Returns a list of all state symbols excluding constructors.

    Returns:
        list: A list of state symbols.
    """
    syms = il.all_symbols()
    return [s for s in syms if s not in il.sig.constructors and slv.solver_name(il.normalize_symbol(s)) != None]

# A relation is extensional if:
#
# 1) It is not derived
# 2) It is initialized to all false
# 3) Every update is either to a simple point, or to false
# 

def extensional_relations():
    """
    Returns a list of extensional relations in the module.

    Extensional relations are defined as relations that are initialized and not modified
    within the module. This function iterates through all actions in the module and checks
    if the action is an assignment, havoc, or call action. For assignment actions, it checks
    if the left-hand side (lhs) is not a destructor sort and if the right-hand side (rhs) is
    not a false value or all lhs arguments are not variables. For havoc actions, it checks
    if the lhs is not a destructor sort and if all lhs arguments are not variables. For call
    actions, it checks if the lhs is not a destructor sort and if all lhs arguments are not
    variables. It then collects all the extensional relations and returns them as a list.

    Returns:
        res (list): A list of extensional relations in the module.
    """
    bad = set()
    for action in list(im.module.actions.values()):
        for sub in action.iter_subactions():
            if isinstance(sub,ia.AssignAction):
                lhs,rhs = sub.args
                if lhs.rep.name not in im.module.destructor_sorts:
                    if not(il.is_false(rhs) or all(not il.is_variable(a) for a in lhs.args)):
                        bad.add(lhs.rep)
            elif isinstance(sub,ia.HavocAction):
                lhs = sub.args[0]
                if lhs.rep.name not in im.module.destructor_sorts:
                    if not(all(not il.is_variable(a) for a in lhs.args)):
                        bad.add(lhs.rep)
            elif isinstance(sub,ia.CallAction):
                for lhs in sub.args[1:]:
                    if lhs.rep.name not in im.module.destructor_sorts:
                        if not(all(not il.is_variable(a) for a in lhs.args)):
                            bad.add(lhs.rep)
    def get_inited(action,inited):
        if isinstance(action,ia.Sequence):
            for act in action.args:
                get_inited(act,inited)
        elif isinstance(action,ia.AssignAction):
            lhs,rhs = action.args
            if lhs.rep.name not in im.module.destructor_sorts:
                if il.is_false(rhs) and all(il.is_variable(a) for a in lhs.args):
                    inited.add(lhs.rep)
    inited = set()
    for name,ini in im.module.initializers:
        get_inited(ini,inited)
    res = [x for x in all_state_symbols() if x in inited and x not in bad]
    return res

def sort_card(sort):
    """
    Returns the cardinality of the given sort.

    Args:
        sort: The sort for which the cardinality is to be determined.

    Returns:
        The cardinality of the sort.

    Raises:
        IvyError: If the sort has no finite interpretation.
    """
    if hasattr(sort,'card'):
        return sort.card
    if sort.is_relational():
        return 2
    if sort in sort_to_cpptype:
        return sort_to_cpptype[sort].card()
    card = slv.sort_card(sort)
#    if card and card > (2 ** 32):
#        card = None
    return card
    if hasattr(sort,'name'):
        name = sort.name
        if name in il.sig.interp:
            sort = il.sig.interp[name]
            if isinstance(sort,il.EnumeratedSort):
                return sort.card
            card = slv.sort_card(sort)
            if card != None:
                return card
    raise iu.IvyError(None,'sort {} has no finite interpretation'.format(sort))
    
indent_level = 0

def indent(header):
    header.append(indent_level * '    ')

def get_indent(line):
    lindent = 0
    for char in line:
        if char == ' ':
            lindent += 1
        elif char == '\t':
            lindent = (lindent + 8) // 8 * 8
        else:
            break
    return lindent

def indent_code(header,code):
    code = code.rstrip() # remove trailing whitespace
    nonempty_lines = [line for line in code.split('\n') if line.strip() != ""]
    indent = min(get_indent(line) for line in nonempty_lines) if nonempty_lines else 0
    for line in code.split('\n'):
        header.append((indent_level * 4 + get_indent(line) - indent) * ' ' + line.strip() + '\n')

def sym_decl(sym,c_type = None,skip_params=0,classname=None,isref=False,ival=None):
    """
    Generate a declaration string for a symbol.

    Parameters:
        sym (Symbol): The symbol for which the declaration string is generated.
        c_type (str, optional): The C type of the symbol. Defaults to None.
        skip_params (int, optional): The number of parameters to skip. Defaults to 0.
        classname (str, optional): The name of the class. Defaults to None.
        isref (bool, optional): Indicates if the symbol is a reference. Defaults to False.
        ival (str, optional): The initial value of the symbol. Defaults to None.

    Returns:
        str: The declaration string for the symbol.
    """
    name, sort = sym.name,sym.sort
    dims = []
    the_c_type,dims = ctype_function(sort,skip_params=skip_params,classname=classname)
    res = (c_type or the_c_type) + ' '
    if isref:
        res += '(&'
    res += memname(sym) if skip_params else varname(sym.name)
    if isref:
        res += ')'
    for d in dims:
        res += '[' + str(d) + ']'
    if ival is not None:
        res += ' = '+ival;
    return res
    
def declare_symbol(header,sym,c_type = None,skip_params=0,classname=None,isref=False,ival=None):
    """
    Declare a symbol in the header.

    Args:
        header (list): The list representing the header file.
        sym (str): The symbol to declare.
        c_type (str, optional): The C type of the symbol. Defaults to None.
        skip_params (int, optional): The number of parameters to skip. Defaults to 0.
        classname (str, optional): The name of the class. Defaults to None.
        isref (bool, optional): Whether the symbol is a reference. Defaults to False.
        ival (str, optional): The initial value of the symbol. Defaults to None.

    Returns:
        None: If the symbol is interpreted, it is skipped.

    Description:
        This function is used to declare a symbol in the header file. It appends the declaration
        of the symbol to the provided header list.

    Pre:
        - The header list is a valid list representing a header file.
        - The sym parameter is a valid symbol name.
        - The c_type parameter, if provided, is a valid C type.
        - The skip_params parameter is a non-negative integer.
        - The classname parameter, if provided, is a valid class name.
        - The isref parameter is a boolean value.
        - The ival parameter, if provided, is a valid initial value.

    Post:
        - If the symbol is interpreted, it is skipped and no declaration is added to the header list.
        - If the symbol is not interpreted, its declaration is added to the header list.
    """
    if slv.solver_name(sym) == None:
        return # skip interpreted symbols
    header.append('    '+sym_decl(sym,c_type,skip_params,classname=classname,isref=isref,ival=ival)+';\n')

special_names = {
    '<' : '__lt',
    '<=' : '__le',
    '>' : '__gt',
    '>=' : '__ge',
}

puncs = re.compile('[\.\[\]]')

def varname(name):
    """
    Convert a variable name to a valid C++ identifier.

    Args:
        name (str or object): The variable name or object.

    Returns:
        str: The converted variable name.

    """
    global special_names
    if not isinstance(name,str):
        name = name.name
    if name in special_names:
        return special_names[name]
    if name.startswith('"'):
        return name
    
    name = name.replace('loc:', 'loc__') \
            .replace('ext:', 'ext__') \
            .replace('___branch:', '__branch__') \
            .replace('__prm:', 'prm__') \
            .replace('prm:', 'prm__') \
            .replace('__fml:', '') \
            .replace('fml:', '') \
            .replace('ret:', '')
            
    name = re.sub(puncs,'__',name).replace('@@','.')
    return name.replace(':','__COLON__')
#    return name.split(':')[-1]

def other_varname(name):
    """
    Returns the variable name with the global classname prepended if it exists.

    Parameters:
        name (str): The name of the variable.

    Returns:
        str: The variable name with the global classname prepended if it exists, otherwise the variable name itself.
    """
    if global_classname is not None:
        return global_classname + '::' + varname(name)
    return varname(name)
    

def funname(name):
    """
    Returns a modified version of the given name.

    Parameters:
    name (str or object): The name to be modified.

    Returns:
    str: The modified name.

    Raises:
    IvyError: If the name is a quoted string.

    """
    if not isinstance(name,str):
        name = name.name
    if name[0].isdigit():
        return '__num' + name
    if name[0] == '-':
        return '__negnum'+name
    if name[0] == '"':
        raise IvyError(None,"cannot compile a function whose name is a quoted string")
    return varname(name)
        

def mk_nondet(code,v,rng,name,unique_id):
    """
    Generates a non-deterministic assignment statement in the given code.

    Parameters:
        code (list): The list of code lines to append the assignment statement to.
        v: The variable to assign a non-deterministic value to.
        rng: The range of possible values for the non-deterministic assignment.
        name (str): The name of the non-deterministic assignment.
        unique_id: The unique identifier for the non-deterministic assignment.

    Returns:
        None
    """
    global nondet_cnt
    indent(code)
    ct = 'int' if isinstance(v,str) else ctype(v.sort)
    code.append(varname(v) + ' = ('+ct+')___ivy_choose(' + str(0) + ',"' + name + '",' + str(unique_id) + ');\n')

def is_native_sym(sym):
    """
    Check if a symbol is a native symbol.

    Args:
        sym: The symbol to be checked.

    Returns:
        bool: True if the symbol is a native symbol, False otherwise.
    """
    assert hasattr(sym.sort,'rng'),sym
    return il.is_uninterpreted_sort(sym.sort.rng) and sym.sort.rng.name in im.module.native_types    


def mk_nondet_sym(code,sym,name,unique_id):
    """
    Generates a non-deterministic symbol and assigns it a value.

    Args:
        code (str): The code to be generated.
        sym: The symbol to be assigned a value.
        name (str): The name of the symbol.
        unique_id: The unique identifier of the symbol.

    Returns:
        None
    """
    global nondet_cnt
    if is_native_sym(sym) or ctype(sym.sort.rng) == '__strlit' or sym.sort.rng in sort_to_cpptype:
        return  # native classes have their own initializers
    if is_large_type(sym.sort):
        code_line(code,varname(sym) + ' = ' + make_thunk(code,variables(sym.sort.dom),HavocSymbol(sym.sort.rng,name,unique_id)))
        return
    fun = lambda v: (('('+ctype(v.sort)+')___ivy_choose(' + '0' + ',"' + name + '",' + str(unique_id) + ')')
                     if not (is_native_sym(v) or ctype(v.sort) == '__strlit' or v.sort in sort_to_cpptype) else None)
    dom = sym.sort.dom
    if dom:
        vs = variables(dom)
        open_loop(code,vs)
        term = sym(*(vs))
        ctext = varname(sym) + ''.join('['+varname(a)+']' for a in vs)
        assign_symbol_value(code,[ctext],fun,term,same=True)
        close_loop(code,vs)
    else:
        assign_symbol_value(code,[varname(sym)],fun,sym,same=True)

def assign_zero_symbol(code,sym):
    """
    Assigns a zero symbol to the given code and symbol.

    Parameters:
    - code (str): The code to assign the zero symbol to.
    - sym (str): The symbol to assign the zero value to.

    Returns:
    None
    """
    fun = lambda v: (('('+ctype(v.sort)+')0')
                     if not (is_native_sym(v) or ctype(v.sort) == '__strlit' or v.sort in sort_to_cpptype) else None)
    assign_symbol_value(code,[varname(sym)],fun,sym,same=True)
    

def field_eq(s,t,field):
    """
    Check if the field of two objects are equal.

    Args:
        s: The first object.
        t: The second object.
        field: The field to compare.

    Returns:
        bool: True if the field of the two objects are equal, False otherwise.
    """
    vs = [il.Variable('X{}'.format(idx),sort) for idx,sort in enumerate(field.sort.dom[1:])]
    if not vs:
        return il.Equals(field(s),field(t))
    return il.ForAll(vs,il.Equals(field(*([s]+vs)),field(*([t]+vs))))

def memname(sym):
    """
    Returns the memory name of a symbol.

    Parameters:
        sym (str or Symbol): The symbol whose memory name is to be retrieved.

    Returns:
        str: The memory name of the symbol.

    """
    if not(isinstance(sym,str)):
        sym = sym.name
    return field_names.get(sym,sym.split('.')[-1])

def basename(name):
    return name.split('::')[-1]

def ctuple(dom,classname=None):
    """
    Generates a C++ tuple representation of the given domain.

    Parameters:
    - dom (list): The domain to be converted into a tuple.
    - classname (str, optional): The name of the class to be prepended to the tuple elements.

    Returns:
    - tuple: The C++ tuple representation of the domain.
    """
    if len(dom) == 1:
        return ctypefull(dom[0],classname=classname)
    return (classname+'::' if classname else '') + '__tup__' + '__'.join(basename(ctypefull(s).replace(" ","_")) for s in dom)

declared_ctuples = set()

def declare_ctuple(header,dom):
    """
    Declare a C++ struct representing a tuple with the given domain.

    Args:
        header (list): The list to append the struct declaration to.
        dom (list): The domain of the tuple.

    Returns:
        None
    """
    if len(dom) == 1:
        return
    t = ctuple(dom)
    if t in declared_ctuples:
        return
    declared_ctuples.add(t)
    header.append('struct ' + t + ' {\n')
    for idx,sort in enumerate(dom):
        sym = il.Symbol('arg{}'.format(idx),sort)
        declare_symbol(header,sym)
    header.append(t+'(){}')
    header.append(t+'('+','.join('const '+ctypefull(d)+' &arg'+str(idx) for idx,d in enumerate(dom))
                  + ') : '+','.join('arg'+str(idx)+'(arg'+str(idx)+')' for idx,d in enumerate(dom))
                  + '{}\n')
    header.append("        size_t __hash() const { "+struct_hash_fun(['arg{}'.format(n) for n in range(len(dom))],dom) + "}\n")
    header.append('};\n')

def ctuple_hash(dom):
    if len(dom) == 1:
        return 'hash<'+ctypefull(dom[0])+'>'
    else:
        return 'hash__' + ctuple(dom)

def declare_ctuple_hash(header,dom,classname):
    """
    Declare a hash function for a custom tuple type.

    Args:
        header (list): The header file to append the hash function declaration to.
        dom (list): The domain of the custom tuple type.
        classname (str): The name of the class containing the custom tuple type.

    Returns:
        None
    """
    t = ctuple(dom)
    the_type = classname+'::'+t
    header.append("""
class the_hash_type {
    public:
        size_t operator()(const the_type &__s) const {
            return the_val;
        }
    };
""".replace('the_hash_type',ctuple_hash(dom)).replace('the_type',the_type).replace('the_val','+'.join('hash_space::hash<{}>()(__s.arg{})'.format(hashtype(s),i,classname=classname) for i,s in enumerate(dom))))

                  
def declare_hash_thunk(header):
    """
    Declare a hash thunk structure.

    Args:
        header (list): The list to which the declaration code will be appended.

    Returns:
        None
    """
    header.append("""
template <typename D, typename R>
struct thunk {
    virtual R operator()(const D &) = 0;
    int ___ivy_choose(int rng,const char *name,int id) {
        return 0;
    }
};
template <typename D, typename R, class HashFun = hash_space::hash<D> >
struct hash_thunk {
    thunk<D,R> *fun;
    hash_space::hash_map<D,R,HashFun> memo;
    hash_thunk() : fun(0) {}
    hash_thunk(thunk<D,R> *fun) : fun(fun) {}
    ~hash_thunk() {
//        if (fun)
//            delete fun;
    }
    R &operator[](const D& arg){
        std::pair<typename hash_space::hash_map<D,R>::iterator,bool> foo = memo.insert(std::pair<D,R>(arg,R()));
        R &res = foo.first->second;
        if (foo.second && fun)
            res = (*fun)(arg);
        return res;
    }
};
""")        

def all_members():
    """
    Returns an iterator that yields all symbols that are members and have a non-null solver name.

    Returns:
        Iterator: An iterator that yields symbols.
    """
    for sym in il.all_symbols():
        if sym_is_member(sym) and not slv.solver_name(sym) == None:
            yield sym

def all_ctuples():
    """
    Generates all possible ctuples.

    Returns:
        Generator: A generator that yields all possible ctuples.

    Example:
        >>> for ctuple in all_ctuples():
        ...     print(ctuple)
        ...
        (dom1, dom2, dom3)
        (dom4, dom5, dom6)
        ...
    """
    done = set()
    for sym in all_members():
        if hasattr(sym.sort,'dom') and len(sym.sort.dom) > 1 and is_large_type(sym.sort):
            res = tuple(sym.sort.dom)
            name = ctuple(res)
            if name in done:
                continue
            done.add(name)
            yield res
    
def all_hash_thunk_domains(classname):
    """
    Generates the names of all hash thunk domains for a given class.

    Parameters:
    - classname (str): The name of the class.

    Yields:
    - str: The name of a hash thunk domain.

    """
    done = set()
    for sym in all_members():
        if hasattr(sym.sort,'dom') and len(sym.sort.dom) == 1 and is_large_type(sym.sort):
            res = sym.sort.dom[0]
            name = ctype(res,classname=classname)
            if name in done:
                continue
            done.add(name)
            yield name

def declare_all_ctuples(header):
    for dom in all_ctuples():
        declare_ctuple(header,dom)

def declare_all_ctuples_hash(header,classname):
    done = set()
    for dom in all_ctuples():
        name = ctuple(dom)
        if name in done:
            continue
        done.add(name)
        declare_ctuple_hash(header,dom,classname)

def hashtype(sort,classname=None):
    if isinstance(sort,il.EnumeratedSort):
        return 'int'
    return ctype(sort,classname)
    
def has_string_interp(sort):
    return il.sort_interp(sort) == 'strlit'    

def is_numeric_range(sort):
    s = sort.extension[0]
    return s[0].isdigit() or (s[0] == '-' and len(s) > 1 and s[1].isdigit)


def ctype_remaining_cases(sort,classname):
    """
    Determines the C type for the remaining cases of a given sort.

    Parameters:
    - sort: The sort to determine the C type for.
    - classname: The name of the class (optional).

    Returns:
    - The C type for the remaining cases of the given sort.

    Raises:
    - IvyError: If the sort is too large to represent with a machine integer.
    """
    if isinstance(sort,il.EnumeratedSort):
        if is_numeric_range(sort):
            return 'int'
        return ((classname+'::') if classname != None else '') + varname(sort.name)
    if sort.is_relational():
        return 'bool'
    if has_string_interp(sort):
        return '__strlit'
    if sort in sort_to_cpptype:
        sn = sort_to_cpptype[sort].short_name()
        return sn
        return ((classname+'::') if classname != None else '') + sn
    card = slv.sort_card(sort)
    if card is None:
        if hasattr(sort,'name'):
            name = sort.name
            if name in il.sig.interp:
                if il.sig.interp[name] == 'nat':
                    return 'unsigned long long'
        return 'int'   # for uninterpreted sorts, can be anything
    if card <= 2**32:
        return 'unsigned'
    if card <= 2**64:
       return 'unsigned long long'
    if card <= 2**128:
       return 'uint128_t'
    raise iu.IvyError(None,'sort {} is too large to represent with a machine integer'.format(sort))


global_classname = None

# Parameter passing types

class ValueType(object):  # by value
    def make(self,t):
        return t
class ConstRefType(object):  # by const reference
    def make(self,t):
        return 'const ' + t + '&'
class RefType(object): # by non-const reference
    def make(self,t):
        return t + '&'

class ReturnRefType(object): # return by reference in argument position "pos"
    def __init__(self,pos):
        self.pos = pos
    def make(self,t):
        return 'void'
    def __repr__(self):
        return "ReturnRefType({})".format(self.pos)

def ctype(sort,classname=None,ptype=None):
    """
    Converts the given sort to its corresponding C++ type.

    Parameters:
        sort (Sort): The sort to be converted.
        classname (str, optional): The name of the class. Defaults to None.
        ptype (ValueType, optional): The value type. Defaults to None.

    Returns:
        ValueType: The converted C++ type.

    Raises:
        None

    Examples:
        # Convert an uninterpreted sort to C++ type
        ctype(sort)

        # Convert an uninterpreted sort to C++ type with a specific class name
        ctype(sort, classname="MyClass")

        # Convert an uninterpreted sort to C++ type with a specific value type
        ctype(sort, ptype=ValueTye())

        # Convert an uninterpreted sort to C++ type with a specific class name and value type
        ctype(sort, classname="MyClass", ptype=ValueTye())
    """
    ptype = ptype or ValueType()
    classname = classname or global_classname
    if il.is_uninterpreted_sort(sort):
        if sort.name in im.module.native_types or sort.name in im.module.sort_destructors:
            return ptype.make(((classname+'::') if classname != None else '') + varname(sort.name))
    return ptype.make(ctype_remaining_cases(sort,classname))
    
def ctypefull(sort,classname=None):
    classname = classname or global_classname
    if il.is_uninterpreted_sort(sort):
        if sort.name in im.module.native_types:
            if classname==None:
#                return native_type_full(im.module.native_types[sort.name])
                return varname(sort.name)
            return classname+'::'+varname(sort.name)
        if sort.name in im.module.sort_destructors:
            return ((classname+'::') if classname != None else '') + varname(sort.name)
    return ctype_remaining_cases(sort,classname)

def native_type_full(self):
    return self.args[0].inst(native_reference_in_type,self.args[1:])    

large_thresh = 1024

def is_large_destr(sort):
    if hasattr(sort,'dom') and any(not is_any_integer_type(s) for s in sort.dom[1:]):
        return True
    cards = list(map(sort_card,sort.dom[1:] if hasattr(sort,'dom') else []))
    return not(all(cards) and reduce(mul,cards,1) <= large_thresh)

def is_large_type(sort):
    if hasattr(sort,'dom') and any(not is_any_integer_type(s) for s in sort.dom):
        return True
    cards = list(map(sort_card,sort.dom if hasattr(sort,'dom') else []))
    return not(all(cards) and reduce(mul,cards,1) <= large_thresh)

def is_large_lhs(term):
    freevars = lu.free_variables(term)
    if any(not is_any_integer_type(v.sort) for v in freevars):
        return True
    cards = [sort_size(v.sort) for v in lu.free_variables(term)]
    return not(all(cards) and reduce(mul,cards,1) <= large_thresh)
    

def ctype_function(sort,classname=None,skip_params=0):
    cards = list(map(sort_card,sort.dom[skip_params:] if hasattr(sort,'dom') else []))
    cty = ctypefull(sort.rng,classname)
    if all(cards) and reduce(mul,cards,1) <= large_thresh:
        if not(hasattr(sort,'dom') and any(not is_any_integer_type(s) for s in sort.dom[skip_params:])):
            return (cty,cards)
    cty = 'hash_thunk<'+ctuple(sort.dom[skip_params:],classname=classname)+','+cty+'>'
    return (cty,[])
    
native_expr_full = native_type_full

thunk_counter = 0


def expr_to_z3(expr,prefix=''):
    fmla = '(assert ' + slv.formula_to_z3(expr).sexpr().replace('|!1','!1|').replace('\\|','').replace('\n',' "\n"') + ')'
    return 'z3::expr(g.ctx,Z3_parse_smtlib2_string({}ctx, "{}", {}sort_names.size(), &{}sort_names[0], &{}sorts[0], {}decl_names.size(), &{}decl_names[0], &{}decls[0]))'.format(prefix,fmla,prefix,prefix,prefix,prefix,prefix,prefix)

def expr_to_z3_no_type_cnst(expr,prefix=''):
    fmla = '(assert ' + slv.formula_to_z3_int(expr).sexpr().replace('|!1','!1|').replace('\\|','').replace('\n',' "\n"') + ')'
    return 'z3::expr(g.ctx,Z3_parse_smtlib2_string({}ctx, "{}", {}sort_names.size(), &{}sort_names[0], &{}sorts[0], {}decl_names.size(), &{}decl_names[0], &{}decls[0]))'.format(prefix,fmla,prefix,prefix,prefix,prefix,prefix,prefix)



def gather_referenced_symbols(expr,res,ignore=[]):
    """
    Gathers the referenced symbols from the given expression.

    Parameters:
    - expr: The expression to analyze.
    - res: A set to store the referenced symbols.
    - ignore: A list of symbols to ignore.

    Returns:
    None
    """
    for sym in ilu.used_symbols_ast(expr):
        if (not sym.is_numeral() and not slv.solver_name(sym) == None
            and sym.name not in im.module.destructor_sorts and sym not in res and sym not in ignore):
            res.add(sym)
            if sym in is_derived:
                ldf = is_derived[sym]
                if ldf is not True:
                    gather_referenced_symbols(ldf.formula.args[1],res,ldf.formula.args[0].args)
                
skip_z3 = False

def is_numeric_or_enumerated_constant(s):
    return s.is_numeral() or il.is_constant(s) and il.is_enumerated(s)


def make_thunk(impl,vs,expr):
    """
    Create a thunk object for the given implementation, variables, and expression.
    
    Thunks are useful in object-oriented programming platforms that allow a class to inherit multiple interfaces, 
    leading to situations where the same method might be called via any of several interfaces. 

    Args:
        impl: The implementation object.
        vs: A list of variables.
        expr: The expression.

    Returns:
        A hash_thunk object.

    Raises:
        None.
    """
    global the_classname
    dom = [v.sort for v in vs]
    D = ctuple(dom,classname=the_classname)
    R = ctypefull(expr.sort,classname=the_classname)
    global thunk_counter
    name = '__thunk__{}'.format(thunk_counter)
    thunk_counter += 1
    thunk_class = 'z3_thunk' if target.get() in ["gen","test"] else 'thunk'
    open_scope(impl,line='struct {} : {}<{},{}>'.format(name,thunk_class,D,R))
    if target.get() in ["gen","test"]:
        code_line(impl,'int __ident')
    syms = set()
    gather_referenced_symbols(expr,syms)
    env = [sym for sym in syms if sym not in is_derived]
    funs = [sym for sym in syms if sym in is_derived]
    for sym in env:
        declare_symbol(impl,sym,classname=the_classname)
    for fun in funs:
        ldf = is_derived[fun]
        if ldf is True:
            emit_constructor(None,impl,fun,the_classname,inline=True)
        else:
            with ivy_ast.ASTContext(ldf):
                emit_derived(None,impl,ldf.formula,the_classname,inline=True)
    envnames = [varname(sym) for sym in env]
    open_scope(impl,line='{}({}) {} {}'.format(name,','.join(sym_decl(sym,classname=the_classname) for sym in env)
                                             ,':' if envnames else ''
                                             ,','.join('{}({})'.format(n,n) for n in envnames))),
    if target.get() in ["gen","test"]:
        code_line(impl,'__ident = z3_thunk_counter')
        code_line(impl,'z3_thunk_counter++')
    close_scope(impl)
    open_scope(impl,line='{} operator()(const {} &arg)'.format(R,D))
    subst = {vs[0].name:il.Symbol('arg',vs[0].sort)} if len(vs)==1 else dict((v.name,il.Symbol('arg@@arg{}'.format(idx),v.sort)) for idx,v in enumerate(vs))
    orig_expr = expr
    expr = ilu.substitute_ast(expr,subst)
    code_line(impl,'return ' + code_eval(impl,expr))
    close_scope(impl)
    if target.get() in ["gen","test"]:
        open_scope(impl,line = 'z3::expr to_z3(gen &g, const z3::expr &v)')
        if is_primitive_sort(expr.sort) or False and isinstance(expr,HavocSymbol) or skip_z3:
            code_line(impl,'return g.ctx.bool_val(true)')
        else:
            if not lu.free_variables(expr) and all(is_numeric_or_enumerated_constant(s) for s in ilu.used_symbols_ast(expr)):
                if expr.sort in sort_to_cpptype or hasattr(expr.sort,'name') and (expr.sort.name in im.module.sort_destructors or
                                                                                  expr.sort.name in im.module.native_types):
                    code_line(impl,'z3::expr res = __to_solver(g,v,{})'.format(code_eval(impl,expr)))
                else:
                    cty = '__strlit' if has_string_interp(expr.sort) else 'int'
                    code_line(impl,'z3::expr res = v == g.int_to_z3(g.sort("{}"),({})({}))'.format(expr.sort.name,cty,code_eval(impl,expr)))
            else:
                code_line(impl,'std::ostringstream __ss')
                code_line(impl,'__ss << __ident')
                def make_symbol(sym):
                    sym_name = 'loc_'+varname(sym.name) 
                    code_line(impl,'std::string {} = std::string("__loc_") + __ss.str() + std::string("__") + "{}"'.format(sym_name,sym.name))
                    open_scope(impl,line='if (g.decls_by_name.find({}) == g.decls_by_name.end())'.format(sym_name))
                    emit_decl(impl,sym,sym_name=sym_name+'.c_str()',prefix='g.')
                    close_scope(impl)
                    return sym_name
                vsyms = [il.Symbol(name+'_arg_{}'.format(idx),v.sort) for idx,v in enumerate(vs)] 
                rsym = il.Symbol(name+'_res_{}'.format(0),expr.sort) # chris: error here with idx instead of 0 len(list(enumerate(vs)))
                envsyms = [il.Symbol(name+'_env_{}'.format(idx),v.sort) for idx,v in enumerate(env)]
                for v in vsyms+envsyms+[rsym]:
                    open_scope(impl,line='if (g.decls_by_name.find("{}") == g.decls_by_name.end())'.format(v.name))
                    emit_decl(impl,v,prefix='g.')
                    close_scope(impl)
                subst = dict((x.name,y) for x,y in zip(vs,vsyms))
                orig_expr = ilu.substitute_ast(orig_expr,subst)
                subst = dict(list(zip(env,envsyms)))
                orig_expr = ilu.rename_ast(orig_expr,subst)
#                def solver_add(impl,text):
#                    code_line(impl,'res = res && {}'.format(text))
                def solver_add(impl,text):
                    code_line(impl,'g.slvr.add({})'.format(text))
                code_line(impl,'z3::expr res = g.ctx.bool_val(true)')
                code_line(impl,'hash_map<std::string,std::string> rn')
                for sym,envsym in zip(env,envsyms):
                    locv = make_symbol(sym)
                    emit_set(impl,sym,solver_add=solver_add,csname=locv+'.c_str()',cvalue=varname(sym),prefix='g.',obj='',gen='g') 
                    code_line(impl,'rn["{}"]={}.c_str()'.format(envsym.name,locv))
#                code_line(impl,'std::cout << "check 1" << std::endl')
#                code_line(impl,'g.ctx.check_error()')
                code_line(impl, 'z3::expr the_expr = {}'.format(expr_to_z3_no_type_cnst(il.Equals(rsym,orig_expr),prefix='g.')))
#                code_line(impl,'std::cout << "the_expr = " << the_expr << std::endl')
                code_line(impl, 'the_expr = __z3_rename(the_expr,rn)')
#                code_line(impl,'std::cout << "check 2" << std::endl')
                code_line(impl,'g.ctx.check_error()')
                code_line(impl,'z3::expr_vector src(g.ctx)')
                code_line(impl,'z3::expr_vector dst(g.ctx)')
                for idx,v in enumerate(vs):
                    code_line(impl,'src.push_back(g.ctx.constant("{}",g.sort("{}")));'.format(vsyms[idx].name,v.sort.name))
                    code_line(impl,'dst.push_back(v.arg({}));'.format(idx))
#                code_line(impl,'std::cout << "check 3" << std::endl')
                code_line(impl,'src.push_back(g.ctx.constant("{}",g.sort("{}")));'.format(rsym.name,rsym.sort.name))
                code_line(impl,'dst.push_back(v);'.format(idx))
                code_line(impl,'g.ctx.check_error()')
                code_line(impl,'res = the_expr.substitute(src,dst)')
#                code_line(impl,'std::cout << "check 4" << std::endl')
                code_line(impl,'g.ctx.check_error()')
#                code_line(impl,'std::cout << "res = " << res << std::endl')
            code_line(impl,'return res')
        close_scope(impl)
    close_scope(impl,semi=True)
    return 'hash_thunk<{},{}>(new {}({}))'.format(D,R,name,','.join(envnames))

# def struct_hash_fun(field_names,field_sorts):
#     if len(field_names) == 0:
#         return '0'
#     return '+'.join('hash_space::hash<{}>()({})'.format(hashtype(s),varname(f)) for s,f in zip(field_sorts,field_names))

def struct_hash_fun(field_names,field_sorts):
    """
    Calculates the hash value for a struct based on its field names and field sorts.

    Args:
        field_names (list): A list of field names.
        field_sorts (list): A list of field sorts.

    Returns:
        str: The calculated hash value for the struct.
    """
    code = []
    code_line(code,'size_t hv = 0')
    for sort,f in zip(field_sorts,field_names):
        domain = sort_domain(sort)[1:]
        if not is_large_destr(sort):
            vs = variables(domain)
            open_loop(code,vs)
            code_line(code,'hv += ' + 'hash_space::hash<{}>()({})'.format(hashtype(sort.rng),varname(f) + ''.join('['+varname(a)+']' for a in vs)))
            close_loop(code,vs)
    code_line(code,'return hv')
    return ''.join(code)
    

def emit_struct_hash(header,the_type,field_names,field_sorts):
    """
    Generates a hash function specialization for a given struct type.

    Args:
        header (list): The header list to append the generated code to.
        the_type (str): The name of the struct type.
        field_names (list): The list of field names in the struct.
        field_sorts (list): The list of field sorts in the struct.

    Returns:
        None
    """
    header.append("""
    template<> class hash<the_type> {
        public:
            size_t operator()(const the_type &__s) const {
                the_val
             }
    };
""".replace('the_type',the_type).replace('the_val',struct_hash_fun(['__s.'+n for n in field_names],field_sorts)))

def is_primitive_sort(sort):
    """
    Check if the given sort is a primitive sort.

    Parameters:
    sort (Sort): The sort to be checked.

    Returns:
    bool: True if the sort is a primitive sort, False otherwise.
    """
    if not sort.dom:
        name = sort.name
        if name in im.module.native_types:
            nt = native_type_full(im.module.native_types[name]).strip()
            return nt.startswith('primitive ')
    return False
            
def emit_cpp_sorts(header):
    """
    Emits C++ code for the sorts defined in the module.

    Args:
        header (list): The list to which the C++ code will be appended.

    Returns:
        None
    """
    for name in im.module.sort_order:
        if name in im.module.native_types:
            nt = native_type_full(im.module.native_types[name]).strip()
            if nt.startswith('primitive '):
                nt = nt[10:]
                header.append("    typedef " + nt + ' ' + varname(name) + ";\n");
            elif nt in ['int','bool']:
                header.append("    typedef " + nt + ' ' + varname(name) + ";\n");
            else:
                if nt == 'std::vector<bool>':
                    nt = 'std::vector<int>'
                header.append("    class " + varname(name) + ' : public ' + nt +  "{\n")
                header.append("        public: size_t __hash() const { return hash_space::hash<"+nt+" >()(*this);};\n")
                header.append("    };\n");
        elif name in im.module.sort_destructors:
            header.append("    struct " + varname(name) + " {\n");
            destrs = im.module.sort_destructors[name]
            for destr in destrs:
                declare_symbol(header,destr,skip_params=1)
            header.append("        size_t __hash() const { "+struct_hash_fun(list(map(memname,destrs)),[d.sort for d in destrs]) + "}\n")
            header.append("    };\n");
        elif isinstance(il.sig.sorts[name],il.EnumeratedSort):
            sort = il.sig.sorts[name]
            if not is_numeric_range(sort):
                header.append('    enum ' + varname(name) + '{' + ','.join(varname(x) for x in sort.extension) + '};\n');
            elif name in il.sig.interp and isinstance(il.sig.interp[name],il.EnumeratedSort):
                sort = il.sig.interp[name]
                header.append('    enum ' + varname(name) + '{' + ','.join(varname(x) for x in sort.extension) + '};\n');
        elif name in im.module.variants:
            sort = il.sig.sorts[name]
            cpptype = ivy_cpp_types.VariantType(varname(name),sort,[(s,ctypefull(s,classname=the_classname)) for s in im.module.variants[name]])
            cpptypes.append(cpptype)
            sort_to_cpptype[il.sig.sorts[name]] = cpptype
        elif name in il.sig.interp:
            itp = il.sig.interp[name]
            if not (isinstance(itp,il.EnumeratedSort) or isinstance(itp,il.RangeSort) or itp.startswith('{') or itp.startswith('bv[') or itp in ['int','nat','strlit']):
                cpptype = ivy_cpp_types.get_cpptype_constructor(itp)(varname(name))
                cpptypes.append(cpptype)
                sort_to_cpptype[il.sig.sorts[name]] = cpptype
        else:
            il.sig.interp[name] = 'int'


def emit_sorts(header):
    """
    Emits the sorts to the given header file.

    Args:
        header (list): The list representing the header file.

    Returns:
        None

    Raises:
        None

    Notes:
        - This function iterates over the sorts in the il.sig.sorts dictionary.
        - It skips the "bool" sort.
        - If the sort has an interpretation in il.sig.interp, it uses that interpretation.
        - If the interpretation is an EnumeratedSort or a RangeSort, it uses that as the sort.
        - If the sort is not an EnumeratedSort, it checks if it has an interpretation in il.sig.interp.
        - If the interpretation is 'int', 'nat', or a RangeSort, it adds code to the header to create an integer sort.
        - If the interpretation is in the form 'bv[n]', where n is an integer, it adds code to the header to create a bitvector sort of width n.
        - If the interpretation is 'strlit', it adds code to the header to create a string sort.
        - If the sort has an interpretation in sort_to_cpptype and is not in im.module.variants, it adds code to the header to create an enum sort.
        - If the sort is an EnumeratedSort, it adds code to the header to create an enum sort with the given values.
    """
    for name,sort in il.sig.sorts.items():
        if name == "bool":
            continue
        if name in il.sig.interp:
            sortname = il.sig.interp[name]
            if isinstance(sortname,il.EnumeratedSort) or isinstance(sortname,il.RangeSort):
                sort = sortname
        if not isinstance(sort,il.EnumeratedSort):
            if name in il.sig.interp:
                sortname = il.sig.interp[name]
#            print "name: {} sortname: {}".format(name,sortname)
                if sortname in ['int','nat'] or isinstance(sort,il.RangeSort) :
                    indent(header)
                    header.append('mk_int("{}");\n'.format(name))
                    if isinstance(sortname,il.RangeSort):
                        lb,ub = sort_bounds(il.sig.sorts[name],obj='obj')
                        code_line(header,'int_ranges["{}"] = std::pair<unsigned long long, unsigned long long>({},{}-1)'.format(name,lb,ub))
                    continue
                if sortname.startswith('bv[') and sortname.endswith(']'):
                    width = int(sortname[3:-1])
                    indent(header)
                    header.append('mk_bv("{}",{});\n'.format(name,width))
                    continue
                if sortname == 'strlit':
                    indent(header)
                    header.append('mk_string("{}");\n'.format(name))
                    continue
            if sort in sort_to_cpptype and sort.name not in im.module.variants:
                indent(header)
                header.append('enum_sorts.insert(std::pair<std::string, z3::sort>("'+ name + '",'+ctype(sort)+'::z3_sort(ctx)));\n')
                continue
            header.append('mk_sort("{}");\n'.format(name))
            continue
#            raise iu.IvyError(None,'sort {} has no finite interpretation'.format(name))
        card = sort.card
        cname = varname(name)
        indent(header)
        header.append("const char *{}_values[{}]".format(cname,card) +
                      " = {" + ','.join('"{}"'.format(slv.solver_name(il.Symbol(x,sort))) for x in sort.extension) + "};\n");
        indent(header)
        header.append('mk_enum("{}",{},{}_values);\n'.format(name,card,cname))

def emit_decl(header,symbol,sym_name=None,prefix=''):
    """
    Emits a declaration in the header file.

    Args:
        header (list): The list representing the header file.
        symbol: The symbol to emit the declaration for.
        sym_name (str, optional): The name of the symbol. Defaults to None.
        prefix (str, optional): The prefix to use in the declaration. Defaults to ''.

    Returns:
        None

    Raises:
        None

    Notes:
        - If the symbol is interpreted in some theory, the declaration is not emitted.
        - If the symbol name is '*>', the declaration name will be '__pto__' + the first domain sort name + '__' + the second domain sort name. Otherwise, the declaration name will be the symbol name.
        - If the sort is relational, the range name will be 'Bool'. Otherwise, the range name will be the name of the range sort.
        - If the domain of the sort is empty, a constant declaration is emitted using the symbol name or the provided symbol name.
        - If the domain of the sort is not empty, a declaration with the domain is emitted using the symbol name or the provided symbol name.

    """
    name = symbol.name
    sname = slv.solver_name(symbol)
    if sname == None:  # this means the symbol is interpreted in some theory
        return 
    cname = '__pto__' + varname(symbol.sort.dom[0].name) + '__' + varname(symbol.sort.dom[1].name)  if symbol.name == '*>' else varname(name)
    sort = symbol.sort
    rng_name = "Bool" if sort.is_relational() else sort.rng.name
    domain = sort_domain(sort)
    if len(domain) == 0:
        indent(header)
        if sym_name is not None:
            header.append('{}mk_const({},"{}");\n'.format(prefix,sym_name,rng_name))
        else:            
            header.append('{}mk_const("{}","{}");\n'.format(prefix,sname,rng_name))
    else:
        card = len(domain)
        indent(header)
        tname = new_temp_name()
        header.append("const char *{}_domain[{}]".format(tname,card) + " = {"
                      + ','.join('"{}"'.format(s.name) for s in domain) + "};\n");
        indent(header)
        if sym_name is not None:
            header.append('{}mk_decl({},{},{}_domain,"{}");\n'.format(prefix,sym_name,card,tname,rng_name))
        else:
            header.append('{}mk_decl("{}",{},{}_domain,"{}");\n'.format(prefix,sname,card,tname,rng_name))
        
def emit_sig(header):
    emit_sorts(header)
    for symbol in all_state_symbols():
        emit_decl(header,symbol)

def sort_domain(sort):
    if hasattr(sort,"domain"):
        return sort.domain
    return []

def int_to_z3(sort,val):
    if il.is_uninterpreted_sort(sort):
        raise iu.IvyError(None,"cannot produce test generator because sort {} is uninterpreted".format(sort))
    return 'int_to_z3(sort("'+sort.name+'"),'+val+')'

def emit_eval(header,symbol,obj=None,classname=None,lhs=None): 
    """
    Emit the evaluation code for a symbol in C++.

    Args:
        header (list): The list to store the generated C++ code.
        symbol: The symbol to be evaluated.
        obj: The object on which the symbol is evaluated.
        classname: The name of the class.
        lhs: The left-hand side of the evaluation.

    Returns:
        None
    """
    global indent_level
    name = symbol.name
    sname = slv.solver_name(symbol)
    cname = varname(name) if lhs is None else code_eval(header,lhs)
    sort = symbol.sort
    domain = sort_domain(sort)
    for idx,dsort in enumerate(domain):
        bds = sort_bounds(dsort,obj=obj)
        if bds is None:
            return
        lb,ub = bds
#        dcard = sort_card(dsort)
        indent(header)
        header.append("for (int X{} = {}; X{} < {}; X{}++)\n".format(idx,lb,idx,ub,idx))
        indent_level += 1
    indent(header)
    if sort.rng.name in im.module.sort_destructors or sort.rng.name in im.module.native_types or sort.rng in sort_to_cpptype:
        code_line(header,'__from_solver<'+classname+'::'+varname(sort.rng.name)+'>(*this,apply("'+sname+'"'+''.join(','+int_to_z3(s,'X{}'.format(idx)) for idx,s in enumerate(domain))+'),'+(obj + '.' if obj else '')+cname+''.join('[X{}]'.format(idx) for idx in range(len(domain)))+')')
    else:
        header.append((obj + '.' if obj else '')
                      + cname + ''.join("[X{}]".format(idx) for idx in range(len(domain)))
                      + ' = ({})eval_apply("{}"'.format(ctype(sort.rng,classname=classname),sname)
                      + ''.join(",X{}".format(idx) for idx in range(len(domain)))
                      + ");\n")
    for idx,dsort in enumerate(domain):
        indent_level -= 1    

def var_to_z3_val(v):
    return int_to_z3(v.sort,varname(v))

def solver_add_default(header,text):
    code_line(header,'slvr.add({})'.format(text))

def emit_set_field(header,symbol,lhs,rhs,nvars=0,solver_add=solver_add_default,prefix='',obj='obj.',gen='*this'):
    """
    Emits code to set the value of a field in a header object.

    Parameters:
    - header: The header object.
    - symbol: The symbol representing the field.
    - lhs: The left-hand side of the assignment.
    - rhs: The right-hand side of the assignment.
    - nvars: The number of variables.
    - solver_add: The solver add function.
    - prefix: The prefix for the apply function.
    - obj: The object name.
    - gen: The generation name.

    Returns:
    None
    """
    global indent_level
    name = symbol.name
    sname = '"' + slv.solver_name(symbol) + '"'
    cname = varname(name)
    sort = symbol.sort
    domain = sort.dom[1:]
    vs = variables(domain,start=nvars)
    open_loop(header,vs)
    lhs1 = prefix+'apply('+sname+''.join(','+s for s in ([lhs]+list(map(var_to_z3_val,vs)))) + ')'
    rhs1 = rhs + ''.join('[{}]'.format(varname(v)) for v in vs) + '.' + memname(symbol)
    if sort.rng.name in im.module.sort_destructors:
        destrs = im.module.sort_destructors[sort.rng.name]
        for destr in destrs:
            emit_set_field(header,destr,lhs1,rhs1,nvars+len(vs),solver_add,prefix,obj,gen)
    else:
#        code_line(header,'slvr.add('+lhs1+'=='+int_to_z3(sort.rng,rhs1)+')')
        solver_add(header,'__to_solver({},'.format(gen)+lhs1+','+rhs1+')')
    close_loop(header,vs)

def emit_set(header,symbol,solver_add=solver_add_default,csname=None,cvalue=None,prefix='',obj='obj.',gen='*this'): 
    """
    Emits code to set the value of a symbol in the header file.

    Args:
        header (str): The header file to emit the code into.
        symbol (Symbol): The symbol to set the value for.
        solver_add (function, optional): The solver add function. Defaults to solver_add_default.
        csname (str, optional): The custom symbol name. Defaults to None.
        cvalue (str, optional): The custom value name. Defaults to None.
        prefix (str, optional): The prefix for the code. Defaults to ''.
        obj (str, optional): The object name. Defaults to 'obj.'.
        gen (str, optional): The generation name. Defaults to '*this'.

    Returns:
        None
    """
    global indent_level
    name = symbol.name
    sname = '"' + slv.solver_name(symbol) + '"' if csname is None else csname 
    cname = varname(name) if cvalue is None else cvalue
    sort = symbol.sort
    domain = sort_domain(sort)
    if sort.rng.name in im.module.sort_destructors and not is_large_type(sort):
    # all(is_finite_iterable_sort(s) for s in domain):
        destrs = im.module.sort_destructors[sort.rng.name]
        for destr in destrs:
            vs = variables(domain)
            open_loop(header,vs)
            lhs = prefix+'apply('+sname+''.join(','+s for s in map(var_to_z3_val,vs)) + ')'
            rhs = obj + varname(symbol) + ''.join('[{}]'.format(varname(v)) for v in vs)
            emit_set_field(header,destr,lhs,rhs,len(vs),solver_add,prefix,obj,gen)
            close_loop(header,vs)
        return
    if is_large_type(sort):
        vs = variables(sort.dom)
        cvars = ','.join('{}ctx.constant("{}",{}sort("{}"))'.format(prefix,varname(v),prefix,v.sort.name) for v in vs)
        open_scope(header)
        code_line(header,'std::vector<z3::expr> __quants;');
        for v in vs:
            code_line(header,'__quants.push_back({}ctx.constant("{}",{}sort("{}")));'.format(prefix,varname(v),prefix,v.sort.name));
        solver_add(header,'forall({},__to_solver({},{}apply({},{}),{}{}))'.format("__quants",gen,prefix,sname,cvars,obj,cname))
        close_scope(header)
        return
    for idx,dsort in enumerate(domain):
        lb,ub = sort_bounds(dsort,obj='obj')
#        dcard = sort_card(dsort)
        indent(header)
        header.append("for (int X{} = {}; X{} < {}; X{}++)\n".format(idx,lb,idx,ub,idx))
        indent_level += 1
    solver_add(header,'__to_solver({},{}apply({}'.format(gen,prefix,sname)
                  + ''.join(','+int_to_z3(domain[idx],'X{}'.format(idx)) for idx in range(len(domain)))
                  + '),{}{}'.format(obj,cname)+ ''.join("[X{}]".format(idx) for idx in range(len(domain)))
                  + ')')
    # header.append('set({}'.format(sname)
    #               + ''.join(",X{}".format(idx) for idx in range(len(domain)))
    #               + ",{}obj.{}".format(prefix,cname)+ ''.join("[X{}]".format(idx) for idx in range(len(domain)))
    #               + ");\n")
    for idx,dsort in enumerate(domain):
        indent_level -= 1    

def sym_is_member(sym):
    global is_derived
    res = sym not in is_derived and sym.name not in im.module.destructor_sorts
    return res

def emit_eval_sig(header,obj=None,used=None,classname=None):
    for symbol in all_state_symbols():
        if slv.solver_name(symbol) != None and symbol.name not in im.module.destructor_sorts: # skip interpreted symbols
            global is_derived
            if symbol not in is_derived:
                if used == None or symbol in used:
                    emit_eval(header,symbol,obj,classname=classname)

def emit_clear_progress(impl,obj=None):
    for df in im.module.progress:
        vs = list(lu.free_variables(df.args[0]))
        open_loop(impl,vs)
        code = []
        indent(code)
        if obj != None:
            code.append('obj.')
        df.args[0].emit(impl,code)
        code.append(' = 0;\n')
        impl.extend(code)
        close_loop(impl,vs)

def mk_rand(sort,classname=None,obj=None):
    bds = sort_bounds(sort,obj=obj)
#    card = sort_card(sort)
    return '('+ctype(sort,classname=classname)+')' + ('(rand() % (({})-({})) + ({}))'.format(bds[1],bds[0],bds[0]) if bds
                                                      else '((rand()%2) ? "a" : "b")' if has_string_interp(sort)
                                                      else sort_to_cpptype[sort].rand() if sort in sort_to_cpptype
                                                      else "0")

def emit_init_gen(header,impl,classname):
    """
    Generates the initialization code for the `init_gen` class.

    Args:
        header (list): The list to append the header code to.
        impl (list): The list to append the implementation code to.
        classname (str): The name of the class.

    Returns:
        None
    """
    global indent_level
    global global_classname
    global_classname = classname
    header.append("""
class init_gen : public gen {
public:
    init_gen(""" + classname + """&);
""")
    header.append("    bool generate(" + classname + "&);\n")
    header.append("    void execute(" + classname + "&){}\n};\n")
    impl.append("init_gen::init_gen(" + classname + " &obj){\n");
    indent_level += 1
    emit_sig(impl)
    indent(impl)
    impl.append('add("(assert (and\\\n')
    constraints = [im.module.init_cond.to_formula()]
    for a in im.module.axioms:
        constraints.append(a)
    for ldf in im.relevant_definitions(ilu.symbols_asts(constraints)):
        constraints.append(fix_definition(ldf.formula).to_constraint())
    for c in constraints:
        fmla = slv.formula_to_z3(c).sexpr().replace('|!1','!1|').replace('\\|','').replace('\n',' "\n"')
        indent(impl)
        impl.append("  {}\\\n".format(fmla))
    indent(impl)
    impl.append('))");\n')
    indent_level -= 1
    impl.append("}\n");
    used = ilu.used_symbols_asts(constraints)
    impl.append("bool init_gen::generate(" + classname + "& obj) {\n")
    indent_level += 1
    for cpptype in cpptypes:
        code_line(impl,cpptype.short_name()+'::prepare()')
    code_line(impl,'alits.clear()')
    for sym in all_state_symbols():
        if slv.solver_name(il.normalize_symbol(sym)) != None: # skip interpreted symbols
            global is_derived
            if sym_is_member(sym):
                if sym in used:
                    if sym in im.module.params:
                        emit_set(impl,sym)  # parameters are already set in constructor
                    else:
                        emit_randomize(impl,sym,classname=classname)
                else:
                    if sym not in im.module.params and not is_primitive_sort(sym.sort.rng):
                        if is_large_type(sym.sort):
                            code_line(impl,'obj.'+varname(sym) + ' = ' + make_thunk(impl,variables(sym.sort.dom),HavocSymbol(sym.sort.rng,sym.name,0)))
                        elif not is_native_sym(sym):
                            fun = lambda v: (mk_rand(v.sort,classname=classname,obj='obj') if not is_native_sym(v) else None)
                            assign_array_from_model(impl,sym,'obj.',fun)
    indent_level -= 1
    impl.append("""
    // std::cout << slvr << std::endl;
    bool __res = solve();
    if (__res) {
""")
    indent_level += 2
    emit_eval_sig(impl,'obj',used = used,classname=classname)
    emit_clear_progress(impl,'obj')
    indent_level -= 2
    impl.append("""
    }
""")
    for cpptype in cpptypes:
        code_line(impl,cpptype.short_name()+'::cleanup()')
    impl.append("""
    obj.___ivy_gen = this;
    obj.__init();
    return __res;
}
""")
    global_classname = None
    
def emit_randomize(header,symbol,classname=None):
    """
    Generates randomization code for a given symbol in C++.

    Args:
        header (list): The list to store the generated code.
        symbol (Symbol): The symbol to be randomized.
        classname (str, optional): The name of the class. Defaults to None.

    Raises:
        IvyError: If the type of the symbol is uninterpreted.

    Returns:
        None
    """
    global indent_level
    name = symbol.name
    sname = slv.solver_name(symbol)
    cname = varname(name)
    sort = symbol.sort
    domain = sort_domain(sort)
    for idx,dsort in enumerate(domain):
        bds = sort_bounds(dsort,obj='obj')
        if bds is None:
            return
        lb,ub = bds
#        dcard = sort_card(dsort)
        indent(header)
        header.append("for (int X{} = {}; X{} < {}; X{}++)\n".format(idx,lb,idx,ub,idx))
        indent_level += 1
    if sort.rng.name in im.module.sort_destructors or sort.rng.name in im.module.native_types or sort.rng in sort_to_cpptype:
        code_line(header,'__randomize<'+classname+'::'+varname(sort.rng.name)+'>(*this,apply("'+sname+'"'+''.join(','+int_to_z3(s,'X{}'.format(idx)) for idx,s in enumerate(domain))+'),"'+sort.rng.name+'")')
    else:
        indent(header)
        if il.is_uninterpreted_sort(sort.rng):
            raise iu.IvyError(None,'cannot create test generator because type {} is uninterpreted'.format(sort.rng))
        header.append('randomize("{}"'.format(sname)
                      + ''.join(",X{}".format(idx) for idx in range(len(domain)))
                      + ',"'+sort.rng.name+'");\n')
    for idx,dsort in enumerate(domain):
        indent_level -= 1    

#    indent(header)
#    header.append('randomize("{}");\n'.format(slv.solver_name(symbol)))


def is_local_sym(sym):
    sym = il.normalize_symbol(sym)
    return not il.sig.contains_symbol(sym) and slv.solver_name(il.normalize_symbol(sym)) != None and sym not in il.sig.constructors

def fix_definition(df):
    if all(il.is_variable(v) for v in df.args[0].args):
        return df
    subst = dict((s,il.Variable('X__{}'.format(idx),s.sort)) for idx,s in enumerate(df.args[0].args) if not il.is_variable(s))
    return ilu.substitute_constants_ast(df,subst)

# An action input x is 'defined' by the action's precondition if the precondition is
# of the form P & x = expr, where x does not occur in P. Here, we remove the defined inputs from
# the precondition, to improve the performance of the solver. We also return a list of
# the definitions, so the values of the defined inputs can be computed.

def extract_defined_parameters(pre_clauses,inputs):
    """
    Extracts defined parameters from the given pre_clauses and inputs.

    Args:
        pre_clauses (ilu.Clauses): The pre_clauses containing formulas and definitions.
        inputs (list): The list of input parameters.

    Returns:
        tuple: A tuple containing the modified pre_clauses and the list of extracted parameter definitions.

    Raises:
        None

    Example:
        pre_clauses = ilu.Clauses([f1, f2, f3], [d1, d2])
        inputs = ['x', 'y']
        result = extract_defined_parameters(pre_clauses, inputs)
        # result: (modified_pre_clauses, extracted_defs)
    """
    change = True
    inputset = set(inputs)
    defmap = {}
    for fmla in pre_clauses.fmlas:
        if il.is_eq(fmla) and fmla.args[0] in inputset:
            defmap[fmla.args[0]] = fmla
    inpdefs = []
    while change:
        change = False
        for input,fmla in list(defmap.items()):
            if (all(input not in ilu.used_symbols_ast(f) or f == fmla for f in pre_clauses.fmlas)
                and all(input not in ilu.used_symbols_ast(d) for d in pre_clauses.defs)):
                pre_clauses = ilu.Clauses([f for f in pre_clauses.fmlas if f != fmla],pre_clauses.defs)
                del defmap[input]
                inpdefs.append(fmla)
                change = True
                pre_clauses = ilu.trim_clauses(pre_clauses)
    inpdefs.reverse()
    return pre_clauses,inpdefs

def collect_used_definitions(pre,inpdefs,ssyms):
    """
    Collects used definitions from the given input definitions and returns a list of used definitions and unused symbols.

    Parameters:
    - pre: The preprocessor object containing definitions.
    - inpdefs: A list of input definitions.
    - ssyms: A set of symbols.

    Returns:
    - res: A list of used definitions.
    - usyms: A list of unused symbols.

    Example:
    >>> pre = Preprocessor()
    >>> inpdefs = [def1, def2, def3]
    >>> ssyms = {'sym1', 'sym2', 'sym3'}
    >>> collect_used_definitions(pre, inpdefs, ssyms)
    ([def1, def2], ['sym3'])
    """
    defmap = dict((d.defines(),d) for d in pre.defs)
    used = set()
    res = []
    usyms = []
    def recur(d):
        for sym in ilu.used_symbols_ast(d.args[1]):
            if sym not in used:
                used.add(sym)
                if sym in defmap:
                    d = defmap[sym]
                    recur(d)
                    res.append(d)
                elif sym in ssyms:
                    usyms.append(sym)
    for inpdef in inpdefs:
        recur(inpdef)
    return res,usyms
    

def emit_defined_inputs(pre,inpdefs,code,classname,ssyms,fsyms):
    """
    Emits defined inputs based on the given parameters.

    Args:
        pre (str): The preprocessor code.
        inpdefs (list): List of input definitions.
        code (str): The code to emit.
        classname (str): The name of the class.
        ssyms (list): List of symbols.
        fsyms (dict): Dictionary of symbols.

    Returns:
        None
    """
    global delegate_enums_to
    delegate_enums_to = classname
    udefs,usyms = collect_used_definitions(pre,inpdefs,ssyms)
    global is_derived
    for sym in usyms:
        if sym not in is_derived:
            declare_symbol(code,sym,classname=classname,isref=True,ival='obj.'+code_eval(code,sym))
    global skip_z3
    skip_z3 = True
    for dfn in udefs:
        sym = dfn.defines()
        declare_symbol(code,sym,classname=classname)
        emit_assign(dfn,code)
    skip_z3 = False
    global delegate_methods_to
    for param_def in inpdefs:
        lhs = param_def.args[0]
        lhs = fsyms.get(lhs,lhs)
        rhs = ilu.substitute_constants_ast(param_def.args[1],fsyms)
        delegate_methods_to = 'obj.'
        code_line(code,code_eval(code,lhs) + ' = ' + code_eval(code,rhs))
        delegate_methods_to = ''
    delegate_enums_to = ''
    
def minimal_field_references(fmla,inputs):
    """
    Returns a dictionary containing minimal field references for a given formula and inputs.

    Parameters:
    - fmla (Formula): The formula for which minimal field references are to be determined.
    - inputs (list): The list of input variables.

    Returns:
    - dict: A dictionary where the keys are input variables and the values are sets of minimal field references.

    Example:
    >>> fmla = Formula(...)
    >>> inputs = ['x', 'y', 'z']
    >>> minimal_refs = minimal_field_references(fmla, inputs)
    >>> print(minimal_refs)
    {'x': {<FieldReference1>, <FieldReference2>}, 'y': {<FieldReference3>}, 'z': set()}
    """
    inpset = set(inputs)
    res = defaultdict(set)
    def field_ref(f):
        if il.is_app(f):
            if f.rep.name in im.module.destructor_sorts and len(f.args) == 1:
                return field_ref(f.args[0])
            if f.rep in inpset:
                return f.rep
        return None
            
    def recur(f):
        if il.is_app(f):
            if f.rep.name in im.module.destructor_sorts and len(f.args) == 1:
                inp = field_ref(f.args[0])
                if inp is not None:
                    res[inp].add(f)
                    return
            if il.is_constant(f) and f.rep in inpset:
                res[f.rep].add(f.rep)
                return
        for x in f.args:
            recur(x)
        
    def get_minima(refs):
        def lt(x,y):
            return len(y.args) == 1 and (x == y.args[0] or lt(x,y.args[0]))
        return set(y for y in refs if all(not(lt(x,y)) for x in refs))
            
    recur(fmla)
    res = dict((inp,get_minima(refs)) for inp,refs in res.items())
    return res
                
def minimal_field_siblings(inputs,mrefs):
    """
    Returns a dictionary containing the minimal field siblings for each input.

    Parameters:
    - inputs (list): A list of input values.
    - mrefs (dict): A dictionary mapping inputs to their corresponding field references.

    Returns:
    - dict: A dictionary where the keys are the inputs and the values are sets of minimal field siblings.

    Example:
    >>> inputs = ['A', 'B', 'C']
    >>> mrefs = {'A': ['F1', 'F2'], 'B': ['F3'], 'C': []}
    >>> minimal_field_siblings(inputs, mrefs)
    {'A': {'D1', 'D2'}, 'B': {'B'}, 'C': {'C'}}
    """
    res = defaultdict(set)
    for inp in inputs:
        if inp in mrefs:
            for f in mrefs[inp]:
                if len(f.args) == 1:
                    sort = f.rep.sort.dom[0]
                    destrs = im.module.sort_destructors[sort.name]
                    for d in destrs:
                        res[inp].add(d(f.args[0]))
                else:
                    res[inp].add(inp)
        else:
            res[inp].add(inp)
    return res

def extract_input_fields(pre_clauses,inputs):
    """
    Extracts input fields from pre_clauses and returns modified pre_clauses, inputs, and fsyms.

    Parameters:
    - pre_clauses (ilu.Clauses): The pre_clauses object containing formulas and definitions.
    - inputs (list): The list of input fields.

    Returns:
    - pre_clauses (ilu.Clauses): The modified pre_clauses object with updated formulas and definitions.
    - inputs (list): The list of input fields.
    - fsyms (dict): A dictionary mapping field symbol names to their corresponding symbols.

    Description:
    This function extracts input fields from pre_clauses by performing the following steps:
    1. Calls minimal_field_references to obtain minimal field references from the formula in pre_clauses.
    2. Calls minimal_field_siblings to obtain minimal field siblings from the inputs and minimal field references.
    3. Defines a field_symbol_name function to generate field symbol names based on the arguments of the field.
    4. Constructs a dictionary fsyms that maps field symbol names to their corresponding symbols.
    5. Constructs a reverse dictionary rfsyms that maps symbols to their corresponding field symbol names.
    6. Defines a recur function to recursively process the formula and update it based on the minimal field references.
    7. Updates pre_clauses by applying the recur function to its formulas and definitions.
    8. Updates inputs with the keys of fsyms.
    9. Returns the modified pre_clauses, inputs, and fsyms.

    Note:
    - The function assumes the existence of the following modules: il, ilu, and im.
    - The function assumes the existence of the following functions: minimal_field_references and minimal_field_siblings.
    """
    mrefs = minimal_field_references(pre_clauses.to_formula(),inputs)
    mrefs = minimal_field_siblings(inputs,mrefs)
    def field_symbol_name(f):
        if len(f.args) == 1:
            return field_symbol_name(f.args[0]) + '__' + f.rep.name
        return f.rep.name
    fsyms = dict((il.Symbol(field_symbol_name(y),y.sort),y) for l in list(mrefs.values()) for y in l)
    rfsyms  = dict((y,x) for x,y in fsyms.items())
    def recur(f):
        if il.is_app(f):
            if f.rep in mrefs or f.rep.name in im.module.destructor_sorts and len(f.args) == 1:
                if f in rfsyms:
                    return rfsyms[f]
        return f.clone(list(map(recur,f.args)))
    pre_clauses = ilu.Clauses(list(map(recur,pre_clauses.fmlas)),list(map(recur,pre_clauses.defs)))
    inputs = list(fsyms.keys())
    return pre_clauses,inputs,fsyms

def expand_field_references(pre_clauses):
    """
    Expands field references in the given pre_clauses.

    Args:
        pre_clauses (ilu.Clauses): The pre_clauses to expand field references in.

    Returns:
        ilu.Clauses: The expanded pre_clauses.

    Raises:
        None

    Notes:
        - This function expands field references in the given pre_clauses.
        - Field references are expanded based on a mapping defined in the function.
        - The mapping is created by extracting certain clauses from the pre_clauses.
        - The function recursively expands field references until no more expansions are possible.
        - The expanded pre_clauses are returned as the result.

    Example:
        pre_clauses = ilu.Clauses(...)
        expanded_clauses = expand_field_references(pre_clauses)
    """
    defmap = dict((x.args[0].rep,x.args[1]) for x in pre_clauses.defs
                  if len(x.args[0].args) == 0 and il.is_app(x.args[1])
                      and  (len(x.args[1].args) == 0 or
                            len(x.args[1].args) == 1 and
                                x.args[1].rep.name in im.module.destructor_sorts))
    def recur(f):
        if il.is_app(f) and f.rep in defmap:
            return recur(defmap[f.rep])
        return f.clone(list(map(recur,f.args)))
    def recur_def(d):
        return d.clone([d.args[0],recur(d.args[1])])
    dfs = list(map(recur,pre_clauses.defs))
    dfs = [df for df in dfs if df.args[0] != df.args[1]]
    return ilu.Clauses(list(map(recur,pre_clauses.fmlas)),dfs)

def get_lib_dirs(with_z3=True):
    import platform
    def file_dir_path(x):
        return os.path.dirname(os.path.abspath(x))
    files = [__file__]
#    if sys.version_info[0] >= 3 and with_z3:
#        files.append(z3.__file__)
    dirs = [file_dir_path(x) for x in files]
    if platform.system() == 'Darwin':
        dirs.append('/usr/local/opt/openssl')  # work around Mac openssl bug
    if with_z3 and 'Z3DIR' in os.environ:
        dirs.append('$Z3DIR')
    return dirs


def emit_action_gen(header,impl,name,action,classname):
    """
    Emits the code for generating an action in C++.

    Args:
        header (list): The list to append the header code to.
        impl (list): The list to append the implementation code to.
        name (str): The name of the action.
        action (Action): The action object.
        classname (str): The name of the class.

    Returns:
        None
    """
    global indent_level
    global global_classname
    global_classname = classname
    caname = varname(name)
    if name in im.module.before_export:
        action = im.module.before_export[name]
    # print "-------------------"
    # print name
    # print classname
    # print action
    def card(sort):
#        res = sort_card(sort)
#        if res is not None:
#            return res
        if hasattr(sort,'name') and iu.compose_names(sort.name,'cardinality') in im.module.attributes:
            return int(im.module.attributes[iu.compose_names(sort.name,'cardinality')].rep)
        return sort_card(sort)
        
#    action = action.unroll_loops(card)
    if name in im.module.ext_preconds:
        orig_action = action
        action = ia.Sequence(ia.AssumeAction(im.module.ext_preconds[name]),action)
        action.lineno = orig_action.lineno
        action.formal_params = orig_action.formal_params
        action.formal_returns = orig_action.formal_returns
        
    with ia.UnrollContext(card):
        upd = action.update(im.module,None)
    pre = tr.reverse_image(ilu.true_clauses(),ilu.true_clauses(),upd)
    orig_pre = pre
    pre_clauses = ilu.trim_clauses(pre)
    pre_clauses = expand_field_references(pre_clauses)
    inputs = [x for x in ilu.used_symbols_clauses(pre_clauses) if is_local_sym(x) and not x.is_numeral()]
    inputset = set(inputs)
    for p in action.formal_params:
        p = p.prefix('__')
        if p not in inputset:
            inputs.append(p)
    pre_clauses, inputs, fsyms = extract_input_fields(pre_clauses,inputs)
    old_pre_clauses = pre_clauses
    pre_clauses, param_defs = extract_defined_parameters(pre_clauses,inputs)
    rdefs = im.relevant_definitions(ilu.symbols_clauses(pre_clauses))
    pre_clauses = ilu.and_clauses(pre_clauses,ilu.Clauses([fix_definition(ldf.formula).to_constraint() for ldf in rdefs]))
    pre_clauses = ilu.and_clauses(pre_clauses,ilu.Clauses(im.module.variant_axioms()))
    pre = pre_clauses.to_formula()
    used = set(ilu.used_symbols_ast(pre))
    used_names = set(varname(s) for s in used)
    defed_params = set(f.args[0] for f in param_defs)
    for x in used:
        if x.is_numeral() and il.is_uninterpreted_sort(x.sort):
            raise iu.IvyError(None,'Cannot compile numeral {} of uninterpreted sort {}'.format(x,x.sort))
    syms = inputs
    header.append("class " + caname + "_gen : public gen {\n  public:\n")
    decld = set()
    def get_root(f):
        return get_root(f.args[0]) if len(f.args) == 1 else f
    for sym in syms:
        if sym in fsyms:
            sym = get_root(fsyms[sym])
        #print sym
        if sym not in decld: # chris: TODO check impact of this hasattr(sym,'name') and
            if not sym.name.startswith('__ts') and sym not in old_pre_clauses.defidx and sym.name != '*>':
                declare_symbol(header,sym,classname=classname)
            decld.add(sym)
    header.append("    {}_gen(".format(caname) + classname + "&);\n")
    header.append("    bool generate(" + classname + "&);\n");
    header.append("    void execute(" + classname + "&);\n};\n");
    impl.append(caname + "_gen::" + caname + "_gen(" + classname + " &obj){\n");
    indent_level += 1
    emit_sig(impl)
    to_decl = set(syms)
    to_decl.update(s for s in used if s.name == '*>')
    for sym in to_decl:
        emit_decl(impl,sym)
    indent(impl)
    import platform
    if platform.system() == 'Windows':
        winfmla = slv.formula_to_z3(pre).sexpr().replace('|!1','!1|').replace('\\|','')
        impl.append('std::string winfmla = "(assert ";\n');
        for winline in winfmla.split('\n'):
            impl.append('winfmla.append("{} ");\n'.format(winline))
        impl.append('winfmla.append(")");\n')
        impl.append('add(winfmla);\n')
    else:
        impl.append('add("(assert {})");\n'.format(slv.formula_to_z3(pre).sexpr().replace('|!1','!1|').replace('\\|','').replace('\n',' "\n"')))
#    impl.append('__ivy_modelfile << slvr << std::endl;\n')
    indent_level -= 1
    impl.append("}\n");
    impl.append("bool " + caname + "_gen::generate(" + classname + "& obj) {\n    push();\n")
    indent_level += 1
    for cpptype in cpptypes:
        code_line(impl,cpptype.short_name()+'::prepare()')
    pre_used = ilu.used_symbols_ast(pre)
    for psym in im.module.params:
        if not psym.sort.dom:
            itp = il.sig.interp.get(psym.sort.name,None)
            if isinstance(itp,il.RangeSort) and psym in [itp.lb,itp.ub]:
                pre_used.add(psym)
    for sym in all_state_symbols():
        if sym in pre_used and sym not in old_pre_clauses.defidx: # skip symbols not used in constraint
            if slv.solver_name(il.normalize_symbol(sym)) != None: # skip interpreted symbols
                if sym_is_member(sym):
                    emit_set(impl,sym)
    code_line(impl,'alits.clear()')
    for sym in syms:
        if not sym.name.startswith('__ts') and sym not in old_pre_clauses.defidx  and sym.name != '*>':
            emit_randomize(impl,sym,classname=classname)
#    impl.append('    std::cout << "generating {}" << std::endl;\n'.format(caname))
    impl.append("""
    // std::cout << slvr << std::endl;
    bool __res = solve();
    if (__res) {
""")
    indent_level += 1
    for sym in syms:
        if not sym.name.startswith('__ts') and sym not in old_pre_clauses.defidx and sym.name != '*>':
            if sym not in defed_params:
                emit_eval(impl,sym,classname=classname,lhs=fsyms.get(sym,sym))
    ssyms = set()
    for sym in all_state_symbols():
#        if sym_is_member(sym):
        if sym.name not in im.module.destructor_sorts:
            ssyms.add(sym)
    emit_defined_inputs(orig_pre,param_defs,impl,classname,ssyms,fsyms)
    indent_level -= 2
    impl.append("""
    }""")
    for cpptype in cpptypes:
        code_line(impl,cpptype.short_name()+'::cleanup()')
    impl.append("""
    pop();
    obj.___ivy_gen = this;
    return __res;
}
""")
    open_scope(impl,line="void " + caname + "_gen::execute(" + classname + "& obj)")
    if action.formal_params:
        code_line(impl,'__ivy_out << "> {}("'.format(name.split(':')[-1]) + ' << "," '.join(' << {}'.format(varname(p)) for p in action.formal_params) + ' << ")" << std::endl')
    else:
        code_line(impl,'__ivy_out << "> {}"'.format(name.split(':')[-1]) + ' << std::endl')
    if opt_trace.get():
        code_line(impl,'__ivy_out << "{" << std::endl')
    call = 'obj.{}('.format(caname) + ','.join(varname(p) for p in action.formal_params) + ')'
    if len(action.formal_returns) == 0:
        code_line(impl,call)
        if opt_trace.get():
            code_line(impl,'__ivy_out << "}" << std::endl')
    else:
        if opt_trace.get():
            code_line(impl,ctypefull(action.formal_returns[0].sort,classname=classname)+' __res = '+call)
            code_line(impl,'__ivy_out << "}" << std::endl')
            code_line(impl,'__ivy_out << "= " << __res <<  std::endl')
        else:
            code_line(impl,'__ivy_out << "= " << ' + call + ' <<  std::endl')
    close_scope(impl)
    global_classname = None


def emit_derived(header,impl,df,classname,inline=False):
    """
    Emits a derived function in C++ code.

    Parameters:
    - header (str): The header file to write the function declaration to.
    - impl (str): The implementation file to write the function definition to.
    - df (DerivedFunction): The derived function object.
    - classname (str): The name of the class the function belongs to.
    - inline (bool, optional): Whether to declare the function as inline. Defaults to False.

    Returns:
    None

    Raises:
    None

    Description:
    This function takes in a DerivedFunction object and emits the corresponding C++ code for the derived function.
    It writes the function declaration to the specified header file and the function definition to the specified implementation file.
    The function name is determined by the name attribute of the DerivedFunction object.
    The function body is generated based on the arguments and expression of the DerivedFunction object.
    The formal parameters and return type of the function are extracted from the arguments and expression of the DerivedFunction object.
    The emitted code includes the necessary includes, namespace, and class scope.
    If the inline parameter is set to True, the function is declared as inline in the header file.

    Example:
    emit_derived("my_header.h", "my_impl.cpp", derived_function, "MyClass", inline=True)
    """
    name = df.defines().name
    sort = df.defines().sort.rng
    retval = il.Symbol("ret:val",sort)
    vs = df.args[0].args
    ps = [ilu.var_to_skolem('fml:',v) for v in vs]
    mp = dict(list(zip(vs,ps)))
    rhs = ilu.substitute_ast(df.args[1],mp)
    action = ia.AssignAction(retval,rhs)
    action.formal_params = ps
    action.formal_returns = [retval]
    emit_some_action(header,impl,name,action,classname,inline)

def emit_constructor(header,impl,cons,classname,inline=False):
    """
    Emits a constructor for a given class.

    Args:
        header (str): The header file where the constructor will be emitted.
        impl (str): The implementation file where the constructor will be emitted.
        cons (Cons): The constructor object.
        classname (str): The name of the class.
        inline (bool, optional): Whether the constructor should be inline or not. Defaults to False.
    """
    name = cons.name
    sort = cons.sort.rng
    retval = il.Symbol("ret:val",sort)
    vs = [il.Variable('X{}'.format(idx),s) for idx,s in enumerate(cons.sort.dom)]
    ps = [ilu.var_to_skolem('fml:',v) for v in vs]
    destrs = im.module.sort_destructors[sort.name]
    asgns = [ia.AssignAction(d(retval),p) for idx,(d,p) in enumerate(zip(destrs,ps))]
    action = ia.Sequence(*asgns);
    action.formal_params = ps
    action.formal_returns = [retval]
    emit_some_action(header,impl,name,action,classname,inline)


def native_split(string):
    """
    Splits a string into a tag and the remaining content.

    Parameters:
    - string (str): The input string to be split.

    Returns:
    - tuple: A tuple containing the tag and the remaining content.
        - tag (str): The tag extracted from the string. If no tag is found, it defaults to "member".
        - content (str): The remaining content after the tag.

    Example:
    >>> native_split("tag\ncontent")
    ('tag', 'content')

    >>> native_split("content")
    ('member', 'content')
    """
    split = string.split('\n',1)
    if len(split) == 2:
        tag = split[0].strip()
        return ("member" if not tag else tag),split[1]
    return "member",split[0]

def native_type(native):
    """
    Returns the tag of the native type.

    Parameters:
    native (object): The native type object.

    Returns:
    str: The tag of the native type.

    """
    tag,code = native_split(native.args[1].code)
    return tag

def native_declaration(atom):
    """
    Generate the native declaration for the given atom.

    Parameters:
    - atom: The atom for which the native declaration is generated.

    Returns:
    - res: The native declaration string.

    Raises:
    - iu.IvyError: If an array cannot be allocated over a non-finite sort.

    """
    if atom.rep in im.module.sig.sorts:
        res = ctype(im.module.sig.sorts[atom.rep],classname=native_classname)
#        print 'type(atom): {} atom.rep: {} res: {}'.format(type(atom),atom.rep,res)
        return res
    vname = varname(atom.rep)
    res = ((native_classname + '::') if (native_classname and not vname[0].isdigit() and not vname[0] == '"') else '') + vname
    for arg in atom.args:
        sort = arg.sort if isinstance(arg.sort,str) else arg.sort.name
        card = sort_card(im.module.sig.sorts[sort])
        if card is None:
            raise iu.IvyError(atom,'cannot allocate an array over sort {} because it is not finite'.format(im.module.sig.sorts[sort]))
        res += '[' + str(card) + ']'
    return res

thunk_counter = 0

def action_return_type(action):
    return ctype(action.formal_returns[0].sort) if action.formal_returns else 'void'

def thunk_name(actname):
    return 'thunk__' + varname(actname)

def create_thunk(impl,actname,action,classname):
    """
    Creates a thunk struct for the given action.

    Args:
        impl (list): The implementation list to append the generated code to.
        actname (str): The name of the action.
        action (Action): The action object.
        classname (str): The name of the class.

    Returns:
        None
    """
    tc = thunk_name(actname)
    impl.append('struct ' + tc + '{\n')
    impl.append('    ' + classname + ' *__ivy' + ';\n')
    
    params = [p for p in action.formal_params if p.name.startswith('prm:')]
    inputs = [p for p in action.formal_params if not p.name.startswith('prm:')]
    for p in params:
        declare_symbol(impl,p,classname=classname)
    impl.append('    ')
    emit_param_decls(impl,tc,params,extra = [ classname + ' *__ivy'],classname=classname)
    impl.append(': __ivy(__ivy)' + ''.join(',' + varname(p) + '(' + varname(p) + ')' for p in params) + '{}\n')
    impl.append('    ' + action_return_type(action) + ' ')
    emit_param_decls(impl,'operator()',inputs,classname=classname);
    impl.append(' const {{\n        {}__ivy->'.format('return ' if action_return_type != 'void' else '') + varname(actname)
                + '(' + ','.join(varname(p.name) for p in action.formal_params) + ');\n    }\n};\n')

def native_typeof(arg):
    if isinstance(arg,ivy_ast.Atom):
        if arg.rep in im.module.actions:
            return thunk_name(arg.rep)
        raise iu.IvyError(arg,'undefined action: ' + arg.rep)
    return int + len(arg.sort.dom) * '[]'

def native_z3name(arg):
    if il.is_variable(arg):
        return arg.sort.name
    rep = arg.rep
    if isinstance(rep,str):
        return rep
    return arg.rep.name

def native_to_str(native,reference=False,code=None):
    """
    Converts a native object to a string representation.

    Parameters:
        native (object): The native object to convert.
        reference (bool, optional): Flag indicating whether to use reference or declaration format. Defaults to False.
        code (str, optional): The code to split. If None, it will be extracted from the native object. Defaults to None.

    Returns:
        str: The string representation of the native object.

    Raises:
        IndexError: If the native object does not have the required attributes.

    Example:
        native = ...
        result = native_to_str(native, reference=True)
    """
    if code is None:
        tag,code = native_split(native.args[1].code)
    fields = code.split('`')
    f = native_reference if reference else native_declaration
    def nfun(idx):
        return native_typeof if fields[idx-1].endswith('%') else native_z3name if fields[idx-1].endswith('"') else f
    def dm(s):
        return s[:-1] if s.endswith('%') else s
    fields = [(nfun(idx)(native.args[int(s)+2]) if idx % 2 == 1 else dm(s)) for idx,s in enumerate(fields)]
    return ''.join(fields)

def emit_native(header,impl,native,classname):
    with ivy_ast.ASTContext(native):
        header.append(native_to_str(native))


# This determines the parameter passing type of each input and output
# of an action (value, const reference, or no-const reference, return
# by reference). The rules are as follows: 
#
# If an output parameter is the same as an input parameter, that
# parameter is returned by reference, and the input parameter is
# passed by reference. Other input parameters are passed by const
# reference, except if the parameter is assigned on the action body,
# in which case it is passed by value. Other output parameters are
# returned by value.
#
# Output parameters beyond the first are always return by reference.
# If they do not match any input parameter, they are added to the
# end of the input parameters.
#
# Notwithstanding the above, all exported actions use call and return
# by value so as not to confused external callers.

def annotate_action(name,action):
    """
    Annotates the given action with parameter and return types based on the provided name.

    Args:
        name (str): The name of the action.
        action (Action): The action to be annotated.

    Returns:
        None

    Raises:
        None

    Notes:
        - If the name is in the module's public actions, the action's parameter types and return types will be set to empty lists.
        - Otherwise, the action's parameter types and return types will be determined based on the formal parameters and returns of the action.
        - If a formal parameter is also a formal return, its parameter type will be set as a reference type.
        - If a formal parameter is assigned within the action or is not a struct, its parameter type will be set as a value type.
        - Otherwise, its parameter type will be set as a constant reference type.
        - The return types will be determined based on the formal returns of the action.
        - If a formal return matches a formal parameter, its return type will be set as a reference type with the index of the matching parameter.
        - If a formal return does not match any formal parameter and is not the first return, its return type will be set as a reference type with the next available argument position.
        - Otherwise, its return type will be set as a value type.
    """
    if name in im.module.public_actions:
        action.param_types = [ValueType() for p in action.formal_params]
        action.return_types = [ValueType() for p in action.formal_returns]
        return

    def action_assigns(p):
        return any(p in sub.modifies() for sub in action.iter_subactions())

    def is_struct(sort):
       return (il.is_uninterpreted_sort(sort) and
               (sort.name in im.module.native_types or sort.name in im.module.sort_destructors))

    action.param_types = [RefType() if any(p == q for q in action.formal_returns)
                          else ValueType() if action_assigns(p) or not is_struct(p.sort) else ConstRefType()
                          for p in action.formal_params]
    next_arg_pos = len(action.formal_params)
    action.return_types = []
    def matches_input(p,action):
        for idx,q in enumerate(action.formal_params):
            if p == q:
                return idx
        return None
    for pos,p in enumerate(action.formal_returns):
        idx = matches_input(p,action)
        if idx is not None:
            thing = ReturnRefType(idx)
        elif pos > 0:
            thing = ReturnRefType(next_arg_pos)
            next_arg_pos = next_arg_pos + 1
        else:
            thing = ValueType()
        action.return_types.append(thing)

def get_param_types(name,action):
    if not hasattr(action,"param_types"):
        annotate_action(name,action)
    return (action.param_types, action.return_types)

# Estimate if two expressions may alias. We say conservatively that expressions may alias
# if they have the same root variable.

def is_destructor(symbol):
    return symbol.name in im.module.destructor_sorts

def may_alias(x,y):
    def root_var(x):
        while il.is_app(x) and is_destructor(x.rep):
            x = x.args[0]
        return x
    return root_var(x) == root_var(y)

# emit parameter declarations of the approriate parameter types

def emit_param_decls(header,name,params,extra=[],classname=None,ptypes=None):
    """
    Emit parameter declarations for a function in a header file.

    Args:
        header (list): The list to append the parameter declarations to.
        name (str): The name of the function.
        params (list): The list of parameters.
        extra (list, optional): Extra elements to include in the parameter declarations. Defaults to [].
        classname (str, optional): The name of the class. Defaults to None.
        ptypes (list, optional): The list of parameter types. Defaults to None.

    Raises:
        IvyError: If a parameter has a function sort.

    Returns:
        None
    """
    header.append(funname(name) + '(')
    # CHRIS
    for p in params:
       if il.is_function_sort(p.sort):
           raise(iu.IvyError(None,'Cannot compile parameter {} with function sort'.format(p)))
    header.append(', '.join(extra + [sym_decl(p) if il.is_function_sort(p.sort) else (ctype(p.sort,classname=classname,ptype = ptypes[idx] if ptypes else None) + ' ' + varname(p.name)) for idx,p in enumerate(params)]))
    header.append(')')

def emit_param_decls_with_inouts(header,name,params,classname,ptypes,returns,return_ptypes):
    """
    Emit parameter declarations with inouts.

    Args:
        header (str): The header string.
        name (str): The name of the function.
        params (list): The list of parameters.
        classname (str): The name of the class.
        ptypes (list): The list of parameter types.
        returns (list): The list of return values.
        return_ptypes (list): The list of return value types.

    Returns:
        None

    Raises:
        None
    """
    extra_params = []
    extra_ptypes = []
    for (r,rp) in zip(returns,return_ptypes):
        if isinstance(rp,ReturnRefType) and rp.pos >= len(params):
            extra_params.append(r)
            extra_ptypes.append(RefType())
    emit_param_decls(header,name,params+extra_params,classname=classname,ptypes=ptypes+extra_ptypes)

def emit_method_decl(header,name,action,body=False,classname=None,inline=False):
    """
    Generates a method declaration for a given action.

    Args:
        header (list): The list to append the generated method declaration to.
        name (str): The name of the action.
        action (Action): The action object.
        body (bool, optional): Indicates whether the method declaration is for a method body. Defaults to False.
        classname (str, optional): The name of the class. Defaults to None.
        inline (bool, optional): Indicates whether the method declaration should be inline. Defaults to False.

    Raises:
        IvyError: If there are multiple output parameters in exported actions.

    Returns:
        None
    """
    if not hasattr(action,"formal_returns"):
        print("bad name: {}".format(name))
        print("bad action: {}".format(action))
    rs = action.formal_returns
    ptypes,rtypes = get_param_types(name,action)
    if not body:
        header.append('    ')
    if not body and target.get() != "gen" and not inline:
        header.append('virtual ')
    if len(rs) == 0:
        header.append('void ')
    else:
        header.append(ctype(rs[0].sort,classname=classname,ptype=rtypes[0]) + ' ')
    if len(rs) > 1:
        if any(not isinstance(p,ReturnRefType) for p in rtypes[1:]):
            raise iu.IvyError(action,'cannot handle multiple output in exported actions: {}'.format(name))
    if body and not inline:
        header.append(classname + '::')
    emit_param_decls_with_inouts(header,name,action.formal_params,classname if inline else None,ptypes,rs,rtypes)
    
def emit_action(header,impl,name,classname):
    action = im.module.actions[name]
    emit_some_action(header,impl,name,action,classname)

def trace_action(impl,name,action):
    """
    Trace an action in the implementation code.

    Args:
        impl (list): The list representing the implementation code.
        name (str): The name of the action.
        action (Action): The Action object representing the action.

    Returns:
        None

    Raises:
        None

    Example:
        >>> impl = []
        >>> name = "my_action"
        >>> action = Action(...)
        >>> trace_action(impl, name, action)
    """
    indent(impl)
    if name.startswith('ext:'):
        name = name[4:]
    impl.append('__ivy_out ' + number_format + ' << "< ' + name + '"')
    if action.formal_params:
        impl.append(' << "("')
        first = True
        for arg in action.formal_params:
            if not first:
                impl.append(' << ","')
            first = False
            impl.append(' << {}'.format(varname(arg.rep.name)))
        impl.append(' << ")"')
    impl.append(' << std::endl;\n')

def emit_some_action(header,impl,name,action,classname,inline=False):
    """
    Emits the code for a specific action in the given header and implementation files.

    Args:
        header (list): The list representing the header file.
        impl (list): The list representing the implementation file.
        name (str): The name of the action.
        action (ivy_ast.Action): The action object.
        classname (str): The name of the class.
        inline (bool, optional): Specifies whether the action should be emitted inline. Defaults to False.
    """
    global indent_level
    global import_callers
    if not inline:
        emit_method_decl(header,name,action)
        header.append(';\n')
    global thunks
    thunks = impl
    code = []
    emit_method_decl(code,name,action,body=True,classname=classname,inline=inline)
    code.append('{\n')
    indent_level += 1
    if name in import_callers:
        trace_action(code,name,action)
        if opt_trace.get():
            code_line(code,'__ivy_out ' + number_format + ' << "{" << std::endl')
    pt,rt = get_param_types(name,action)
    if len(action.formal_returns) >= 1 and not isinstance(rt[0],ReturnRefType):
        indent(code)
        p = action.formal_returns[0]
        if p not in action.formal_params:
            code.append(ctypefull(p.sort,classname=classname) + ' ' + varname(p.name) + ';\n')
            mk_nondet_sym(code,p,p.name,0)
    with ivy_ast.ASTContext(action):
        action.emit(code)
    if name in import_callers:
        if opt_trace.get():
            code_line(code,'__ivy_out ' + number_format + ' << "}" << std::endl')
    if len(action.formal_returns) >= 1 and not isinstance(rt[0],ReturnRefType):
        indent(code)
        code.append('return ' + varname(action.formal_returns[0].name) + ';\n')
    indent_level -= 1
    code.append('}\n')
    impl.extend(code)

def init_method():
    asserts = []
    # for ini in im.module.labeled_inits + im.module.labeled_axioms:
    #     act = ia.AssertAction(ini.formula)
    #     act.lineno = ini.lineno
    #     asserts.append(act)
    
    for name,ini in im.module.initializers:
        asserts.append(ini)

    res = ia.Sequence(*asserts)
    res.formal_params = []
    res.formal_returns = []
    return res

def emit_initial_action(header,impl,classname):
    """
    Emit the initial action for the given header, implementation, and classname.

    Args:
        header (str): The header file path.
        impl (str): The implementation file path.
        classname (str): The name of the class.

    Returns:
        None
    """
    global thunks
    thunks = impl
    code_line(header,'void __init()')
    open_scope(impl,line = 'void ' + classname + '::__init()')
    for action in im.module.initial_actions:
        open_loop(impl,action.formal_params)
        action.emit(impl)
        close_loop(impl,action.formal_params)
    close_scope(impl)
    
int_ctypes = ["bool","int","long long","unsigned","unsigned long long","int128_t","uint128_t"]

def is_iterable_sort(sort):
    return ctype(sort) in int_ctypes

def is_finite_iterable_sort(sort):
    return is_iterable_sort(sort) and sort_card(sort) is not None

def is_any_integer_type(sort):
    """
    Check if the given sort is any integer type.

    Parameters:
    sort (object): The sort to be checked.

    Returns:
    bool: True if the sort is an integer type, False otherwise.
    """
    if ctype(sort) not in int_ctypes:
        if il.is_uninterpreted_sort(sort) and sort.name in im.module.native_types:
            nt = native_type_full(im.module.native_types[sort.name]).strip()
            if nt in int_ctypes:
                return True
        if isinstance(sort,il.EnumeratedSort):
            return True
        return False
    return True

def check_iterable_sort(sort):
    if not is_any_integer_type(sort):
        raise iu.IvyError(None,"cannot iterate over non-integer sort {}".format(sort))

def fix_bound(sym,obj):
    res = varname(sym.name)
    if not sym.is_numeral() and obj is not None:
        res = obj + '.' + res
    return res

def sort_bounds(sort,obj=None):
    """
    Returns the bounds for a given sort.

    Parameters:
        sort (Sort): The sort for which the bounds are to be determined.
        obj (object, optional): The object for which the bounds are to be fixed. Defaults to None.

    Returns:
        list or None: A list containing the lower and upper bounds of the sort, or None if the sort has no bounds.

    Raises:
        None

    Examples:
        >>> sort_bounds(sort)
        ['0', '10']

        >>> sort_bounds(sort, obj)
        ['(lb+1)', 'ub']

    """
    itp = il.sig.interp.get(sort.name,None)
    if isinstance(itp,il.RangeSort):
        lb = fix_bound(itp.lb,obj)
        ub = fix_bound(itp.ub,obj)
        return [lb,'(' + ub + '+1)']
    card = sort_card(sort)
    return ["0",str(card)] if card else None

def sort_size(sort):
    itp = il.sig.interp.get(sort.name,None)
    if isinstance(itp,il.RangeSort):
        return 1 # just a guess!
    return sort_card(sort)

###
# Control flow management
###

def open_loop(impl,vs,declare=True,bounds=None):
    global indent_level
    for num,idx in enumerate(vs):
        check_iterable_sort(idx.sort)
        indent(impl)
        bds = bounds[num] if bounds else sort_bounds(idx.sort)
        vn = varname(idx.name)
        ct = ctype(idx.sort)
        ct = 'int' if ct == 'bool' else ct if ct in int_ctypes else 'int'
        if isinstance(idx.sort,il.EnumeratedSort):
            ct = ctype(idx.sort)
            impl.append('for ('+ ((ct + ' ') if declare else '') + vn + ' = (' + ct + ')' +  bds[0] + '; (int) ' + vn + ' < ' + bds[1] + '; ' + vn + ' = (' + ct + ')(((int)' + vn + ') + 1)) {\n')
        else:
            impl.append('for ('+ ((ct + ' ') if declare else '') + vn + ' = ' + bds[0] + '; ' + vn + ' < ' + bds[1] + '; ' + vn + '++) {\n')
        indent_level += 1

def close_loop(impl,vs):
    global indent_level
    for idx in vs:
        indent_level -= 1    
        indent(impl)
        impl.append('}\n')
        
def open_scope(impl,newline=False,line=None):
    global indent_level
    if line != None:
        indent(impl)
        impl.append(line)
    if newline:
        impl.append('\n')
        indent(impl)
    impl.append('{\n')
    indent_level += 1

def open_if(impl,cond):
    open_scope(impl,line='if('+(''.join(cond) if isinstance(cond,list) else cond)+')')
    
def close_scope(impl,semi=False):
    global indent_level
    indent_level -= 1
    indent(impl)
    impl.append('}'+(';' if semi else '')+'\n')


def emit_tick(header,impl,classname):
    """
   This generates the "tick" method, called by the test environment to
    represent passage of time. For each progress property, if it is not
    satisfied the counter is incremented else it is set to zero. For each
    property the maximum of the counter values for all its relies is
    computed and the test environment's ivy_check_progress function is called.

    This is currently a bit bogus, since we could miss satisfaction of
    the progress property occurring between ticks.

    Args:
        header (list): The list representing the header file.
        impl (list): The list representing the implementation file.
        classname (str): The name of the class.

    Returns:
        None
        
    """
    global indent_level
    indent_level += 1
    indent(header)
    header.append('void __tick(int timeout);\n')
    indent_level -= 1
    indent(impl)
    impl.append('void ' + classname + '::__tick(int __timeout){\n')
    indent_level += 1

    rely_map = defaultdict(list)
    for df in im.module.rely:
        key = df.args[0] if isinstance(df,il.Implies) else df
        rely_map[key.rep].append(df)

    for df in im.module.progress:
        vs = list(lu.free_variables(df.args[0]))
        open_loop(impl,vs)
        code = []
        indent(code)
        df.args[0].emit(impl,code)
        code.append(' = ')
        df.args[1].emit(impl,code)
        code.append(' ? 0 : ')
        df.args[0].emit(impl,code)
        code.append(' + 1;\n')
        impl.extend(code)
        close_loop(impl,vs)


    for df in im.module.progress:
        if any(not isinstance(r,il.Implies) for r in rely_map[df.defines()]):
            continue
        vs = list(lu.free_variables(df.args[0]))
        open_loop(impl,vs)
        maxt = new_temp(impl)
        indent(impl)
        impl.append(maxt + ' = 0;\n') 
        for r in rely_map[df.defines()]:
            if not isinstance(r,il.Implies):
                continue
            rvs = list(lu.free_variables(r.args[0]))
            assert len(rvs) == len(vs)
            subs = dict(list(zip(rvs,vs)))

            ## TRICKY: If there are any free variables on rhs of
            ## rely not occuring on left, we must prevent their capture
            ## by substitution

            xvs = set(lu.free_variables(r.args[1]))
            xvs = xvs - set(rvs)
            for xv in xvs:
                subs[xv.name] = xv.rename(xv.name + '__')
            xvs = [subs[xv.name] for xv in xvs]
    
            e = ilu.substitute_ast(r.args[1],subs)
            open_loop(impl,xvs)
            indent(impl)
            impl.append('{} = std::max({},'.format(maxt,maxt))
            e.emit(impl,impl)
            impl.append(');\n')
            close_loop(impl,xvs)
        indent(impl)
        impl.append('if (' + maxt + ' > __timeout)\n    ')
        indent(impl)
        df.args[0].emit(impl,impl)
        impl.append(' = 0;\n')
        indent(impl)
        impl.append('ivy_check_progress(')
        df.args[0].emit(impl,impl)
        impl.append(',{});\n'.format(maxt))
        close_loop(impl,vs)

    indent_level -= 1
    indent(impl)
    impl.append('}\n')

def csortcard(s):
    card = sort_card(s)
    return str(card) if card and card < 2 ** 64 else "0"

def check_member_names(classname):
    names = list(map(varname,(list(il.sig.symbols) + list(il.sig.sorts) + list(im.module.actions))))
    if classname in names:
        raise iu.IvyError(None,'Cannot create C++ class {} with member {}.\nUse command line option classname=... to change the class name.'
                          .format(classname,classname))

def emit_ctuple_to_solver(header,dom,classname):
    ct_name = classname + '::' + ctuple(dom)
    ch_name = classname + '::' + ctuple_hash(dom)
    emit_hash_thunk_to_solver(header,dom,classname,ct_name,ch_name)
    
def emit_hash_thunk_to_solver(header,dom,classname,ct_name,ch_name):
    """
    Emit the hash thunk to solver class for a given header, domain, classname, ct_name, and ch_name.

    Parameters:
    - header: The header file to emit the code into.
    - dom: The domain.
    - classname: The name of the class.
    - ct_name: The ct_name.
    - ch_name: The ch_name.
    """
    open_scope(header,line='template<typename R> class to_solver_class<hash_thunk<D,R> >'.replace('D',ct_name).replace('H',ch_name))
    code_line(header,'public:')
    open_scope(header,line='z3::expr operator()( gen &g, const  z3::expr &v, hash_thunk<D,R> &val)'.replace('D',ct_name).replace('H',ch_name))
    code_line(header,'z3::expr res = g.ctx.bool_val(true)')
    code_line(header,'z3::expr disj = g.ctx.bool_val(false)')
    code_line(header,'z3::expr bg = val.fun ? dynamic_cast<z3_thunk<D,R> *>(val.fun)->to_z3(g,v) : g.ctx.bool_val(true)'.replace('D',ct_name))
    open_scope(header,line='for(typename hash_map<D,R>::iterator it=val.memo.begin(), en = val.memo.end(); it != en; it++)'.replace('D',ct_name).replace('H',ch_name))
#    code_line(header,'if ((*val.fun)(it->first) == it->second) continue;')
    code_line(header,'z3::expr asgn = __to_solver(g,v,it->second)')
#    code_line(header,'if (eq(bg,asgn)) continue')
    if dom is not None:
        code_line(header,'z3::expr cond = '+' && '.join('__to_solver(g,v.arg('+str(n)+'),it->first.arg'+str(n)+')' for n in range(len(dom))))
    else:
        code_line(header,'z3::expr cond = __to_solver(g,v.arg(0),it->first)')
    code_line(header,'res = res && implies(cond,asgn)')
    code_line(header,'disj = disj || cond')
    close_scope(header)
    code_line(header,'res = res && (disj || bg)')
    code_line(header,'return res')
    close_scope(header)
    close_scope(header,semi=True)

def emit_all_ctuples_to_solver(header, classname):
    """
    Emits all ctuples to the solver.

    Args:
        header (str): The header file path.
        classname (str): The name of the class.

    Returns:
        None
    """
#    emit_hash_thunk_to_solver(header,None,classname,'__strlit','hash<__strlit>')
#    for cpptype in cpptypes:
#        emit_hash_thunk_to_solver(header,None,classname,cpptype.short_name(),'hash<'+cpptype.short_name()+'>')
    for cname in all_hash_thunk_domains(classname):
        emit_hash_thunk_to_solver(header,None,classname,cname,'hash<'+cname+'>')
    for dom in all_ctuples():
        emit_ctuple_to_solver(header,dom,classname)

def emit_ctuple_equality(header,dom,classname):
    """
    Generates the equality operator function for a given class and its corresponding ctuple.

    Args:
        header (str): The header file to write the function to.
        dom (list): The list of arguments for the ctuple.
        classname (str): The name of the class.

    Returns:
        None
    """
    t = ctuple(dom)
    open_scope(header,line = 'bool operator==(const {}::{} &x, const {}::{} &y)'.format(classname,t,classname,t))
    code_line(header,'return '+' && '.join('x.arg{} == y.arg{}'.format(n,n) for n in range(len(dom))))
    close_scope(header)

def is_really_uninterpreted_sort(sort):
    return il.is_uninterpreted_sort(sort) and not (
        sort.name in im.module.sort_destructors or sort.name in im.module.native_types)

# find the actions that wrap imports and flaf them so the we output a
# trace. This is so that the trace of the action will appear before 
# any assert failure in the precondition. To get the name of the caller
# from the import, we remove the prefic 'imp__'.

def find_import_callers():
    global import_callers
    import_callers = set()
    if target.get() != "test":
        return
    for imp in im.module.imports:
        name = imp.imported()
        if not imp.scope() and name in im.module.actions:
            import_callers.add('ext:' + name[5:])
            import_callers.add(name[5:])
            
def module_to_cpp_class(classname,basename):
    """
    Converts a module to a C++ class.

    Args:
        classname (str): The name of the C++ class.
        basename (str): The base name of the C++ file.

    Returns:
        None
    """
    global the_classname
    the_classname = classname
    global encoded_sorts
    encoded_sorts = set()
    check_member_names(classname)
    global is_derived
    is_derived = dict()
    for ldf in im.module.definitions + im.module.native_definitions:
        is_derived[ldf.formula.defines()] = ldf
    for sortname, conss in im.module.sort_constructors.items():
        for cons in conss:
            is_derived[cons] = True
    global the_extensional_relations
    the_extensional_relations = set(extensional_relations())
    
    global cpptypes
    cpptypes = []
    global sort_to_cpptype
    sort_to_cpptype = {}
    global field_names
    field_names = dict()
    for destrs in list(im.module.sort_destructors.values()):
        if destrs: # paranoia
            dest_base,_ = iu.parent_child_name(destrs[0].name)
            if not all(iu.parent_child_name(d.name)[0] == dest_base for d in destrs):
                for d in destrs:
                    field_names[d.name] = varname(d.name)

    if target.get() in ["gen","test"]:
        for t in list(il.sig.interp):
            attr = iu.compose_names(t,'override')
            if attr in im.module.attributes:
                print('override: interpreting {} as {}'.format(t,im.module.attributes[attr].rep))
                il.sig.interp[t] = im.module.attributes[attr].rep

    global number_format
    number_format = ''
    if 'radix' in im.module.attributes and im.module.attributes['radix'].rep == '16':
        number_format = ' << std::hex << std::showbase '
        
    # remove the actions not reachable from exported
        
    # TODO: may want to call internal actions from testbench

   # ra = iu.reachable(im.module.public_actions,lambda name: im.module.actions[name].iter_calls())
   # im.module.actions = dict((name,act) for name,act in im.module.actions.iteritems() if name in ra)

    header = ivy_cpp.context.globals.code
    import platform
    if platform.system() == 'Windows':
        header.append('#define WIN32_LEAN_AND_MEAN\n')
        header.append("#include <windows.h>\n")
    header.append("#define _HAS_ITERATOR_DEBUGGING 0\n")
    if target.get() == "gen":
        header.append('extern void ivy_assert(bool,const char *);\n')
        header.append('extern void ivy_assume(bool,const char *);\n')
        header.append('extern void ivy_check_progress(int,int);\n')
        header.append('extern int choose(int,int);\n')
    if target.get() in ["gen","test"]:
        header.append('struct ivy_gen {virtual int choose(int rng,const char *name) = 0;};\n')
#    header.append('#include <vector>\n')

    if target.get() in ["gen","test"]:
        header.append('#include "z3++.h"\n')


    header.append(hash_h)

    header.append("typedef std::string __strlit;\n")
    header.append("extern std::ofstream __ivy_out;\n")
    header.append("void __ivy_exit(int);\n")
    
    #chris
    header.append("#include <inttypes.h>\n")
    header.append("#include <math.h>\n")
    header.append("typedef __int128_t int128_t;\n")
    header.append("typedef __uint128_t uint128_t;\n")
    header.append("#include <signal.h>\n")
    header.append("#include <chrono> \n")
    # header.append("#include <execinfo.h>\n") # For backtrace
    header.append("int call_generating = 1;\n")

    declare_hash_thunk(header)

    once_memo = set()
    for native in im.module.natives:
        tag = native_type(native)
        if tag == "header":
            code = native_to_str(native)
            if code not in once_memo:
                once_memo.add(code)
                header.append(code)

    header.append("""

    class reader;
    class timer;

""")

    ivy_cpp.context.members = ivy_cpp.CppText()
    header = ivy_cpp.context.members.code
    header.append('class ' + classname + ' {\n  public:\n')
    header.append("    typedef {} ivy_class;\n".format(classname))
    header.append("""
    std::vector<std::string> __argv;
#ifdef _WIN32
    void *mutex;  // forward reference to HANDLE
#else
    pthread_mutex_t mutex;
#endif
    void __lock();
    void __unlock();
""")
    header.append("""
#ifdef _WIN32
    std::vector<HANDLE> thread_ids;\n
#else
    std::vector<pthread_t> thread_ids;\n
#endif
""")
    header.append('    void install_reader(reader *);\n')
    header.append('    void install_thread(reader *);\n')
    header.append('    void install_timer(timer *);\n')
    header.append('    virtual ~{}();\n'.format(classname))

    header.append('    std::vector<int> ___ivy_stack;\n')
    if target.get() in ["gen","test"]:
        header.append('    ivy_gen *___ivy_gen;\n')
    header.append('    int ___ivy_choose(int rng,const char *name,int id);\n')
    if target.get() != "gen":
        header.append('    virtual void ivy_assert(bool,const char *){}\n')
        header.append('    virtual void ivy_assume(bool,const char *){}\n')
        header.append('    virtual void ivy_check_progress(int,int){}\n')
    
    with ivy_cpp.CppClassName(classname):
        emit_cpp_sorts(header)

        
    impl = ivy_cpp.context.impls.code
    if opt_stdafx.get():
        impl.append('#include "stdafx.h"\n')
    impl.append('#include "' + basename + '.h"\n\n')
    impl.append("#include <sstream>\n")
    impl.append("#include <algorithm>\n")
    impl.append("""
#include <iostream>
#include <stdlib.h>
#include <sys/types.h>          /* See NOTES */
#include <sys/stat.h>
#include <fcntl.h>
#ifdef _WIN32
#include <winsock2.h>
#include <WS2tcpip.h>
#include <io.h>
#define isatty _isatty
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h> 
#include <sys/select.h>
#include <unistd.h>
#define _open open
#define _dup2 dup2
#define SIGUSR3 SIGWINCH
union sigval sigdata;
#endif
#include <string.h>
#include <stdio.h>
#include <string>
#if __cplusplus < 201103L
#else
#include <cstdint>
#endif
""")
    impl.append("typedef {} ivy_class;\n".format(classname))
    # impl.append("""
    # struct SignalData {
    #     {}_repl* ivy_ptr;
    #     double value2;
    # };
    # """.format(classname))
    impl.append("std::ofstream __ivy_out;\n")
    impl.append("std::ofstream __ivy_modelfile;\n")
    impl.append("void __ivy_exit(int code){exit(code);}\n")

    impl.append("""
class reader {
public:
    virtual int fdes() = 0;
    virtual void read() = 0;
    virtual void bind() {}
    virtual bool running() {return fdes() >= 0;}
    virtual bool background() {return false;}
    virtual ~reader() {}
};

class timer {
public:
    virtual int ms_delay() = 0;
    virtual void timeout(int) = 0;
    virtual ~timer() {}
};

#ifdef _WIN32
DWORD WINAPI ReaderThreadFunction( LPVOID lpParam ) 
{
    reader *cr = (reader *) lpParam;
    cr->bind();
    while (true)
        cr->read();
    return 0;
} 

DWORD WINAPI TimerThreadFunction( LPVOID lpParam ) 
{
    timer *cr = (timer *) lpParam;
    while (true) {
        int ms = cr->ms_delay();
        Sleep(ms);
        cr->timeout(ms);
    }
    return 0;
} 
#else
void * _thread_reader(void *rdr_void) {
    reader *rdr = (reader *) rdr_void;
    rdr->bind();
    std::cerr << "starting reader thread" << std::endl;
    while(rdr->running()) {
        std::cerr << "reading" << std::endl;
        rdr->read();
    }
    delete rdr;
    return 0; // just to stop warning
}

void * _thread_timer( void *tmr_void ) 
{
    timer *tmr = (timer *) tmr_void;
    while (true) {
        int ms = tmr->ms_delay();
        struct timespec ts;
        ts.tv_sec = ms/1000;
        ts.tv_nsec = (ms % 1000) * 1000000;
        nanosleep(&ts,NULL);
        tmr->timeout(ms);
    }
    return 0;
} 
#endif 
""")

    if target.get() == "repl":
        impl.append("""
void CLASSNAME::install_reader(reader *r) {
    #ifdef _WIN32

        DWORD dummy;
        HANDLE h = CreateThread( 
            NULL,                   // default security attributes
            0,                      // use default stack size  
            ReaderThreadFunction,   // thread function name
            r,                      // argument to thread function 
            0,                      // use default creation flags 
            &dummy);                // returns the thread identifier 
        if (h == NULL) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(h);
    #else
        pthread_t thread;
        std::cerr << "creating reader thread" << std::endl;
        int res = pthread_create(&thread, NULL, _thread_reader, r);
        if (res) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(thread);
    #endif
}      

void CLASSNAME::install_thread(reader *r) {
    install_reader(r);
}

void CLASSNAME::install_timer(timer *r) {
    #ifdef _WIN32

        DWORD dummy;
        HANDLE h = CreateThread( 
            NULL,                   // default security attributes
            0,                      // use default stack size  
            TimersThreadFunction,   // thread function name
            r,                      // argument to thread function 
            0,                      // use default creation flags 
            &dummy);                // returns the thread identifier 
        if (h == NULL) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(h);
    #else
        pthread_t thread;
        int res = pthread_create(&thread, NULL, _thread_timer, r);
        if (res) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(thread);
    #endif
}      

""".replace('CLASSNAME',classname))

    if target.get() == "test":
        impl.append("""
std::vector<reader *> threads;
std::vector<reader *> readers;
std::vector<timer *> timers;
bool initializing = false;

void CLASSNAME::install_reader(reader *r) {
    std::cerr << "installing reader 2" << std::endl;
    readers.push_back(r);
    if (!::initializing)
        r->bind();
}

void CLASSNAME::install_thread(reader *r) {
    #ifdef _WIN32

        DWORD dummy;
        HANDLE h = CreateThread( 
            NULL,                   // default security attributes
            0,                      // use default stack size  
            ReaderThreadFunction,   // thread function name
            r,                      // argument to thread function 
            0,                      // use default creation flags 
            &dummy);                // returns the thread identifier 
        if (h == NULL) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(h);
    #else
        pthread_t thread;
        std::cerr << "creating reader thread" << std::endl;
        int res = pthread_create(&thread, NULL, _thread_reader, r);
        if (res) {
            std::cerr << "failed to create thread" << std::endl;
            exit(1);
        }
        thread_ids.push_back(thread);
    #endif
}      

void CLASSNAME::install_timer(timer *r) {
    timers.push_back(r);
}
""".replace('CLASSNAME',classname))

    impl.append("""
#ifdef _WIN32
    void CLASSNAME::__lock() { WaitForSingleObject(mutex,INFINITE); }
    void CLASSNAME::__unlock() { ReleaseMutex(mutex); }
#else
    void CLASSNAME::__lock() { pthread_mutex_lock(&mutex); }
    void CLASSNAME::__unlock() { pthread_mutex_unlock(&mutex); }
#endif
""".replace('CLASSNAME',classname))
    native_exprs = []
    for n in im.module.natives:
        native_exprs.extend(n.args[2:])
    for actn,actb in im.module.actions.items():
        for n in actb.iter_subactions():
            if isinstance(n,ia.NativeAction):
                native_exprs.extend(n.args[1:])
    callbacks = set()
    for e in native_exprs:
        if isinstance(e,ivy_ast.Atom) and e.rep in im.module.actions:
            callbacks.add(e.rep)
    for actname in sorted(callbacks):
        action = im.module.actions[actname]
        create_thunk(impl,actname,action,classname)

    if target.get() in ["test"]:
        sf = header if target.get() == "gen" else impl
        emit_boilerplate1(sf,impl,classname)

    impl.append(hash_cpp)

    impl.append("""


struct ivy_value {
    int pos;
    std::string atom;
    std::vector<ivy_value> fields;
    bool is_member() const {
        return atom.size() && fields.size();
    }
};
struct deser_err {
};

struct ivy_ser {
    virtual void  set(long long) = 0;
    virtual void  set(bool) = 0;
    virtual void  setn(long long inp, int len) = 0;
    virtual void  set(const std::string &) = 0;
    virtual void  open_list(int len) = 0;
    virtual void  close_list() = 0;
    virtual void  open_list_elem() = 0;
    virtual void  close_list_elem() = 0;
    virtual void  open_struct() = 0;
    virtual void  close_struct() = 0;
    virtual void  open_field(const std::string &) = 0;
    virtual void  close_field() = 0;
    virtual void  open_tag(int, const std::string &) {throw deser_err();}
    virtual void  close_tag() {}
    virtual ~ivy_ser(){}
};
struct ivy_binary_ser : public ivy_ser {
    std::vector<char> res;
    void setn(long long inp, int len) {
        for (int i = len-1; i >= 0 ; i--)
            res.push_back((inp>>(8*i))&0xff);
    }
    void set(long long inp) {
        setn(inp,sizeof(long long));
    }
    void set(bool inp) {
        set((long long)inp);
    }
    void set(const std::string &inp) {
        for (unsigned i = 0; i < inp.size(); i++)
            res.push_back(inp[i]);
        res.push_back(0);
    }
    void open_list(int len) {
        set((long long)len);
    }
    void close_list() {}
    void open_list_elem() {}
    void close_list_elem() {}
    void open_struct() {}
    void close_struct() {}
    virtual void  open_field(const std::string &) {}
    void close_field() {}
    virtual void  open_tag(int tag, const std::string &) {
        set((long long)tag);
    }
    virtual void  close_tag() {}
};

struct ivy_deser {
    virtual void  get(long long&) = 0;
    virtual void  get(std::string &) = 0;
    virtual void  getn(long long &res, int bytes) = 0;
    virtual void  open_list() = 0;
    virtual void  close_list() = 0;
    virtual bool  open_list_elem() = 0;
    virtual void  close_list_elem() = 0;
    virtual void  open_struct() = 0;
    virtual void  close_struct() = 0;
    virtual void  open_field(const std::string &) = 0;
    virtual void  close_field() = 0;
    virtual int   open_tag(const std::vector<std::string> &) {throw deser_err();}
    virtual void  close_tag() {}
    virtual void  end() = 0;
    virtual ~ivy_deser(){}
};

struct ivy_binary_deser : public ivy_deser {
    std::vector<char> inp;
    int pos;
    std::vector<int> lenstack;
    ivy_binary_deser(const std::vector<char> &inp) : inp(inp),pos(0) {}
    virtual bool more(unsigned bytes) {return inp.size() >= pos + bytes;}
    virtual bool can_end() {return pos == inp.size();}
    void get(long long &res) {
       getn(res,8);
    }
    void getn(long long &res, int bytes) {
        if (!more(bytes))
            throw deser_err();
        res = 0;
        for (int i = 0; i < bytes; i++)
            res = (res << 8) | (((long long)inp[pos++]) & 0xff);
    }
    void get(std::string &res) {
        while (more(1) && inp[pos]) {
//            if (inp[pos] == '\"')
//                throw deser_err();
            res.push_back(inp[pos++]);
        }
        if(!(more(1) && inp[pos] == 0))
            throw deser_err();
        pos++;
    }
    void open_list() {
        long long len;
        get(len);
        lenstack.push_back(len);
    }
    void close_list() {
        lenstack.pop_back();
    }
    bool open_list_elem() {
        return lenstack.back();
    }
    void close_list_elem() {
        lenstack.back()--;
    }
    void open_struct() {}
    void close_struct() {}
    virtual void  open_field(const std::string &) {}
    void close_field() {}
    int open_tag(const std::vector<std::string> &tags) {
        long long res;
        get(res);
        if (res >= tags.size())
            throw deser_err();
        return res;
    }
    void end() {
        if (!can_end())
            throw deser_err();
    }
};
struct ivy_socket_deser : public ivy_binary_deser {
      int sock;
    public:
      ivy_socket_deser(int sock, const std::vector<char> &inp)
          : ivy_binary_deser(inp), sock(sock) {}
    virtual bool more(unsigned bytes) {
        while (inp.size() < pos + bytes) {
            int oldsize = inp.size();
            int get = pos + bytes - oldsize;
            get = (get < 1024) ? 1024 : get;
"""
+ #+ ("            get = (get < 1024) ? 1024 : get;" if target.get() not in ["gen","test"] else "") +
"""
            inp.resize(oldsize + get);
            int newbytes;
	    if ((newbytes = read(sock,&inp[oldsize],get)) < 0)
		 { std::cerr << "recvfrom failed\\n"; exit(1); }
            inp.resize(oldsize + newbytes);
            if (newbytes == 0)
                 return false;
        }
        return true;
    }
    virtual bool can_end() {return true;}
};

struct ivy_ser_128 {
    virtual void  set(int128_t) = 0;
    virtual void  set(bool) = 0;
    virtual void  setn(int128_t inp, int len) = 0;
    virtual void  set(const std::string &) = 0;
    virtual void  open_list(int len) = 0;
    virtual void  close_list() = 0;
    virtual void  open_list_elem() = 0;
    virtual void  close_list_elem() = 0;
    virtual void  open_struct() = 0;
    virtual void  close_struct() = 0;
    virtual void  open_field(const std::string &) = 0;
    virtual void  close_field() = 0;
    virtual void  open_tag(int, const std::string &) {
	std::cout << "ivy_ser_128 open_tag deser_err\\n"; 
	throw deser_err();
    }
    virtual void  close_tag() {}
    virtual ~ivy_ser_128(){}
};

struct ivy_binary_ser_128 : public ivy_ser_128 {
    std::vector<char> res;
    void setn(int128_t inp, int len) {
        for (int i = len-1; i >= 0 ; i--)
            res.push_back((inp>>(8*i))&0xff); //16 ? no
    }
    void set(int128_t inp) {
        setn(inp,sizeof(int128_t));
    }
    void set(bool inp) {
        set((int128_t)inp);
    }
    void set(const std::string &inp) {
        for (unsigned i = 0; i < inp.size(); i++)
            res.push_back(inp[i]);
        res.push_back(0);
    }
    void open_list(int len) {
        set((int128_t)len);
    }
    void close_list() {}
    void open_list_elem() {}
    void close_list_elem() {}
    void open_struct() {}
    void close_struct() {}
    virtual void  open_field(const std::string &) {}
    void close_field() {}
    virtual void  open_tag(int tag, const std::string &) {
        set((int128_t)tag);
    }
    virtual void  close_tag() {}
};

struct ivy_deser_128 {
    virtual void  get(int128_t&) = 0;
    virtual void  get(std::string &) = 0;
    virtual void  getn(int128_t &res, int bytes) = 0;
    virtual void  open_list() = 0;
    virtual void  close_list() = 0;
    virtual bool  open_list_elem() = 0;
    virtual void  close_list_elem() = 0;
    virtual void  open_struct() = 0;
    virtual void  close_struct() = 0;
    virtual void  open_field(const std::string &) = 0;
    virtual void  close_field() = 0;
    virtual int   open_tag(const std::vector<std::string> &) {
	    std::cout << "ivy_deser_128 open_tag deser_err\\n"; 
	    throw deser_err();
    }
    virtual void  close_tag() {}
    virtual void  end() = 0;
    virtual ~ivy_deser_128(){}
};

struct ivy_binary_deser_128 : public ivy_deser_128 {
    std::vector<char> inp;
    int pos;
    std::vector<int> lenstack;
    ivy_binary_deser_128(const std::vector<char> &inp) : inp(inp),pos(0) {}
    virtual bool more(unsigned bytes) {return inp.size() >= pos + bytes;}
    virtual bool can_end() {return pos == inp.size();}
    void get(int128_t &res) {
       getn(res,16);
    }
    void getn(int128_t &res, int bytes) {
        if (!more(bytes)) {
	    std::cerr << "ivy_binary_deser_128 getn deser_err\\n"; 
            throw deser_err();
        } res = 0;
        for (int i = 0; i < bytes; i++)
            res = (res << 8) | (((int128_t)inp[pos++]) & 0xff);
    }
    void get(std::string &res) {
        while (more(1) && inp[pos]) {
//            if (inp[pos] == '\"')
//                throw deser_err();
            res.push_back(inp[pos++]);
        }
        if(!(more(1) && inp[pos] == 0)) {
	    std::cerr << "ivy_binary_deser_128 get deser_err\\n"; 
            throw deser_err();
        } pos++;
    }
    void open_list() {
        int128_t len;
        get(len);
        lenstack.push_back(len);
    }
    void close_list() {
        lenstack.pop_back();
    }
    bool open_list_elem() {
        return lenstack.back();
    }
    void close_list_elem() {
        lenstack.back()--;
    }
    void open_struct() {}
    void close_struct() {}
    virtual void  open_field(const std::string &) {}
    void close_field() {}
    int open_tag(const std::vector<std::string> &tags) {
        int128_t res;
        get(res);
        if (res >= tags.size()) {
	    std::cerr << "ivy_binary_deser_128 open_tag deser_err\\n"; 
            throw deser_err();
        } return res;
    }
    void end() {
        if (!can_end()) {
	    std::cerr << "ivy_binary_deser_128 end deser_err\\n"; 
            throw deser_err();
	}
    }
};

struct ivy_socket_deser_128 : public ivy_binary_deser_128 {
    int sock;
    public:
      ivy_socket_deser_128(int sock, const std::vector<char> &inp)
          : ivy_binary_deser_128(inp), sock(sock) {}
    virtual bool more(unsigned bytes) {
        while (inp.size() < pos + bytes) {
            int oldsize = inp.size();
            int get = pos + bytes - oldsize;
            get = (get < 1024) ? 1024 : get;
            inp.resize(oldsize + get);
            int newbytes;
	    if ((newbytes = read(sock,&inp[oldsize],get)) < 0)
		 { std::cerr << "recvfrom failed\\n"; exit(1); }
            inp.resize(oldsize + newbytes);
            if (newbytes == 0)
                 return false;
        }
        return true;
    }
    virtual bool can_end() {return true;}
};

struct out_of_bounds {
    std::string txt;
    int pos;
    out_of_bounds(int _idx, int pos = 0) : pos(pos){
        std::ostringstream os;
        os << "argument " << _idx+1;
        txt = os.str();
    }
    out_of_bounds(const std::string &s, int pos = 0) : txt(s), pos(pos) {}
};

template <class T> T _arg(std::vector<ivy_value> &args, unsigned idx, long long bound);
template <class T> T __lit(const char *);

template <>
bool _arg<bool>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    if (!(args[idx].atom == "true" || args[idx].atom == "false") || args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return args[idx].atom == "true";
}

template <>
int _arg<int>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    std::istringstream s(args[idx].atom.c_str());
    s.unsetf(std::ios::dec);
    s.unsetf(std::ios::hex);
    s.unsetf(std::ios::oct);
    long long res;
    s  >> res;
    // int res = atoi(args[idx].atom.c_str());
    if (bound && (res < 0 || res >= bound) || args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return res;
}

template <>
long long _arg<long long>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    std::istringstream s(args[idx].atom.c_str());
    s.unsetf(std::ios::dec);
    s.unsetf(std::ios::hex);
    s.unsetf(std::ios::oct);
    long long res;
    s  >> res;
//    long long res = atoll(args[idx].atom.c_str());
    if (bound && (res < 0 || res >= bound) || args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return res;
}

template <>
unsigned long long _arg<unsigned long long>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    std::istringstream s(args[idx].atom.c_str());
    s.unsetf(std::ios::dec);
    s.unsetf(std::ios::hex);
    s.unsetf(std::ios::oct);
    unsigned long long res;
    s  >> res;
//    unsigned long long res = atoll(args[idx].atom.c_str());
    if (bound && (res < 0 || res >= bound) || args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return res;
}

template <>
unsigned _arg<unsigned>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    std::istringstream s(args[idx].atom.c_str());
    s.unsetf(std::ios::dec);
    s.unsetf(std::ios::hex);
    s.unsetf(std::ios::oct);
    unsigned res;
    s  >> res;
//    unsigned res = atoll(args[idx].atom.c_str());
    if (bound && (res < 0 || res >= bound) || args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return res;
}


std::ostream &operator <<(std::ostream &s, const __strlit &t){
    s << "\\"" << t.c_str() << "\\"";
    return s;
}

template <>
__strlit _arg<__strlit>(std::vector<ivy_value> &args, unsigned idx, long long bound) {
    if (args[idx].fields.size())
        throw out_of_bounds(idx,args[idx].pos);
    return args[idx].atom;
}

template <class T> void __ser(ivy_ser &res, const T &inp);

template <>
void __ser<int>(ivy_ser &res, const int &inp) {
    res.set((long long)inp);
}

template <>
void __ser<long long>(ivy_ser &res, const long long &inp) {
    res.set(inp);
}

template <>
void __ser<unsigned long long>(ivy_ser &res, const unsigned long long &inp) {
    res.set((long long)inp);
}

template <>
void __ser<int128_t>(ivy_ser &res, const int128_t &inp) {
    res.set((long long)inp);
}


template <>
void __ser<unsigned>(ivy_ser &res, const unsigned &inp) {
    res.set((long long)inp);
}

template <>
void __ser<bool>(ivy_ser &res, const bool &inp) {
    res.set(inp);
}
""" + ("""
template <>
void __ser<std::vector<bool>::const_reference>(ivy_ser &res, const std::vector<bool>::const_reference &inp) {
    bool thing = inp;
    res.set(thing);
} """ if platform.system() == 'Darwin' else "") + """

template <>
void __ser<__strlit>(ivy_ser &res, const __strlit &inp) {
    res.set(inp);
}

template <class T> void __deser(ivy_deser &inp, T &res);

template <>
void __deser<int>(ivy_deser &inp, int &res) {
    long long temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<long long>(ivy_deser &inp, long long &res) {
    inp.get(res);
}

template <>
void __deser<unsigned long long>(ivy_deser &inp, unsigned long long &res) {
    long long temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<int128_t>(ivy_deser &inp, int128_t &res) {
    long long temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<unsigned>(ivy_deser &inp, unsigned &res) {
    long long temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<__strlit>(ivy_deser &inp, __strlit &res) {
    inp.get(res);
}

template <>
void __deser<bool>(ivy_deser &inp, bool &res) {
    long long thing;
    inp.get(thing);
    res = thing;
}

void __deser(ivy_deser &inp, std::vector<bool>::reference res) {
    long long thing;
    inp.get(thing);
    res = thing;
}


//we could probably merge that but we prefered to not modify too much initial
//code

template <class T> void __ser(ivy_ser_128 &res, const T &inp);

template <>
void __ser<int>(ivy_ser_128 &res, const int &inp) {
    res.set((int128_t)inp);
}

template <>
void __ser<long long>(ivy_ser_128 &res, const long long &inp) {
    res.set((int128_t)inp);
}

template <>
void __ser<int128_t>(ivy_ser_128 &res, const int128_t &inp) {
    res.set(inp);
}

template <>
void __ser<unsigned long long>(ivy_ser_128 &res, const unsigned long long &inp) {
    res.set((int128_t)inp);
}

template <>
void __ser<uint128_t>(ivy_ser_128 &res, const uint128_t &inp) {
    res.set((int128_t)inp);
}

template <>
void __ser<unsigned>(ivy_ser_128 &res, const unsigned &inp) {
    res.set((int128_t)inp);
}

template <>
void __ser<bool>(ivy_ser_128 &res, const bool &inp) {
    res.set(inp);
}

template <>
void __ser<__strlit>(ivy_ser_128 &res, const __strlit &inp) {
    res.set(inp);
}

template <class T> void __deser(ivy_deser_128 &inp, T &res);

template <>
void __deser<int>(ivy_deser_128 &inp, int &res) {
    int128_t temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<long long>(ivy_deser_128 &inp, long long &res) {
    int128_t temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<int128_t>(ivy_deser_128 &inp, int128_t &res) {
    inp.get(res);
}


template <>
void __deser<unsigned long long>(ivy_deser_128 &inp, unsigned long long &res) {
    int128_t temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<unsigned>(ivy_deser_128 &inp, unsigned &res) {
    int128_t temp;
    inp.get(temp);
    res = temp;
}

template <>
void __deser<__strlit>(ivy_deser_128 &inp, __strlit &res) {
    inp.get(res);
}

template <>
void __deser<bool>(ivy_deser_128 &inp, bool &res) {
    int128_t thing;
    inp.get(thing);
    res = thing;
}

class gen;

""")
    if target.get() in ["gen","test"]:
        impl.append("""
template <class T> void __from_solver( gen &g, const  z3::expr &v, T &res);

template <>
void __from_solver<int>( gen &g, const  z3::expr &v, int &res) {
    res = g.eval(v);
}

template <>
void __from_solver<long long>( gen &g, const  z3::expr &v, long long &res) {
    res = g.eval(v);
}


template <>
void __from_solver<int128_t>( gen &g, const  z3::expr &v, int128_t &res) {
    res = g.eval(v);
}

template <>
void __from_solver<uint128_t>( gen &g, const  z3::expr &v, uint128_t &res) {
    res = g.eval(v);
}


template <>
void __from_solver<unsigned long long>( gen &g, const  z3::expr &v, unsigned long long &res) {
    res = g.eval(v);
}

template <>
void __from_solver<unsigned>( gen &g, const  z3::expr &v, unsigned &res) {
    res = g.eval(v);
}

template <>
void __from_solver<bool>( gen &g, const  z3::expr &v, bool &res) {
    res = g.eval(v);
}

template <>
void __from_solver<__strlit>( gen &g, const  z3::expr &v, __strlit &res) {
    res = g.eval_string(v);
}

template <class T>
class to_solver_class {
};

template <class T> z3::expr __to_solver( gen &g, const  z3::expr &v, T &val) {
    return to_solver_class<T>()(g,v,val);
}


template <>
z3::expr __to_solver<int>( gen &g, const  z3::expr &v, int &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<long long>( gen &g, const  z3::expr &v, long long &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<int128_t>( gen &g, const  z3::expr &v, int128_t &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<uint128_t>( gen &g, const  z3::expr &v, uint128_t &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<unsigned long long>( gen &g, const  z3::expr &v, unsigned long long &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<unsigned>( gen &g, const  z3::expr &v, unsigned &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<bool>( gen &g, const  z3::expr &v, bool &val) {
    return v == g.int_to_z3(v.get_sort(),val);
}

template <>
z3::expr __to_solver<__strlit>( gen &g, const  z3::expr &v, __strlit &val) {
//    std::cerr << v << ":" << v.get_sort() << std::endl;
    return v == g.int_to_z3(v.get_sort(),val);
}

template <class T>
class __random_string_class {
public:
    std::string operator()() {
        std::string res;
        res.push_back('a' + (rand() % 26)); // no empty strings for now
        while (rand() %2)
            res.push_back('a' + (rand() % 26));
        return res;
    }
};

template <class T> std::string __random_string(){
    return __random_string_class<T>()();
}

template <class T> void __randomize( gen &g, const  z3::expr &v, const std::string &sort_name);

template <>
void __randomize<int>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<long long>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<int128_t>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<uint128_t>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<unsigned long long>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<unsigned>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
void __randomize<bool>( gen &g, const  z3::expr &v, const std::string &sort_name) {
    g.randomize(v,sort_name);
}

template <>
        void __randomize<__strlit>( gen &g, const  z3::expr &apply_expr, const std::string &sort_name) {
    z3::sort range = apply_expr.get_sort();
    __strlit value = (rand() % 2) ? "a" : "b";
    z3::expr val_expr = g.int_to_z3(range,value);
    z3::expr pred = apply_expr == val_expr;
    g.add_alit(pred);
}

static int z3_thunk_counter = 0;

template<typename D, typename R>
class z3_thunk : public thunk<D,R> {
    public:
       virtual z3::expr to_z3(gen &g, const  z3::expr &v) = 0;
};

z3::expr __z3_rename(const z3::expr &e, hash_map<std::string,std::string> &rn) {
    if (e.is_app()) {
        z3::func_decl decl = e.decl();
        z3::expr_vector args(e.ctx());
        unsigned arity = e.num_args();
        for (unsigned i = 0; i < arity; i++) {
            args.push_back(__z3_rename(e.arg(i),rn));
        }
        if (decl.name().kind() == Z3_STRING_SYMBOL) {
            std::string fun = decl.name().str();
            if (rn.find(fun) != rn.end()) {
                std::string newfun = rn[fun];
                std::vector<z3::sort> domain;
                for (unsigned i = 0; i < arity; i++) {
                    domain.push_back(decl.domain(i));
                }
                z3::sort range = e.decl().range();
                decl = e.ctx().function(newfun.c_str(),arity,&domain[0],range);
            }
        }
        return decl(args);
    } else if (e.is_quantifier()) {
        z3::expr body = __z3_rename(e.body(),rn);
        unsigned nb = Z3_get_quantifier_num_bound(e.ctx(),e);
        std::vector<Z3_symbol> bnames;
        std::vector<Z3_sort> bsorts;
        for (unsigned i = 0; i < nb; i++) {
            bnames.push_back(Z3_get_quantifier_bound_name(e.ctx(),e,i));
            bsorts.push_back(Z3_get_quantifier_bound_sort(e.ctx(),e,i));
        }
        Z3_ast q = Z3_mk_quantifier(e.ctx(),
                                    Z3_is_quantifier_forall(e.ctx(),e),
                                    Z3_get_quantifier_weight(e.ctx(),e),
                                    0,
                                    0,
                                    nb,
                                    &bsorts[0],
                                    &bnames[0],
                                    body);
        return z3::expr(e.ctx(),q);
    }
    return(e);
}""")

    for sort_name in [s for s in sorted(il.sig.sorts) if isinstance(il.sig.sorts[s],il.EnumeratedSort)]:
        csname = varname(sort_name)
        cfsname = classname + '::' + csname
        if sort_name not in encoded_sorts:
            impl.append('std::ostream &operator <<(std::ostream &s, const {} &t);\n'.format(cfsname))
            impl.append('template <>\n')
            impl.append(cfsname + ' _arg<' + cfsname + '>(std::vector<ivy_value> &args, unsigned idx, long long bound);\n')
            impl.append('template <>\n')
            impl.append('void  __ser<' + cfsname + '>(ivy_ser &res, const ' + cfsname + '&);\n')
            impl.append('template <>\n')
            impl.append('void  __deser<' + cfsname + '>(ivy_deser &inp, ' + cfsname + ' &res);\n')                
            impl.append('template <>\n')
            impl.append('void  __ser<' + cfsname + '>(ivy_ser_128 &res, const ' + cfsname + '&);\n')
            impl.append('template <>\n')
            impl.append('void  __deser<' + cfsname + '>(ivy_deser_128 &inp, ' + cfsname + ' &res);\n')                          
        if target.get() in ["test","gen"]:
            impl.append('template <>\n')
            impl.append('void __from_solver<' + cfsname + '>( gen &g, const  z3::expr &v, ' + cfsname + ' &res);\n')
            impl.append('template <>\n')
            impl.append('z3::expr __to_solver<' + cfsname + '>( gen &g, const  z3::expr &v, ' + cfsname + ' &val);\n')
            impl.append('template <>\n')
            impl.append('void __randomize<' + cfsname + '>( gen &g, const  z3::expr &v, const std::string &sort_name);\n')
        
    for sort_name in sorted(im.module.sort_destructors):
        csname = varname(sort_name)
        cfsname = classname + '::' + csname
        if sort_name not in encoded_sorts:
            impl.append('std::ostream &operator <<(std::ostream &s, const {} &t);\n'.format(cfsname))
            impl.append('template <>\n')
            impl.append(cfsname + ' _arg<' + cfsname + '>(std::vector<ivy_value> &args, unsigned idx, long long bound);\n')
            impl.append('template <>\n')
            impl.append('void  __ser<' + cfsname + '>(ivy_ser &res, const ' + cfsname + '&);\n')
            impl.append('template <>\n')
            impl.append('void  __deser<' + cfsname + '>(ivy_deser &inp, ' + cfsname + ' &res);\n')                
            impl.append('template <>\n')
            impl.append('void  __ser<' + cfsname + '>(ivy_ser_128 &res, const ' + cfsname + '&);\n')
            impl.append('template <>\n')
            impl.append('void  __deser<' + cfsname + '>(ivy_deser_128 &inp, ' + cfsname + ' &res);\n')              
    

    if target.get() in ["test","gen"]:
        for sort_name in sorted(im.module.sort_destructors):
            csname = varname(sort_name)
            cfsname = classname + '::' + csname
            impl.append('template <>\n')
            impl.append('void __from_solver<' + cfsname + '>( gen &g, const  z3::expr &v, ' + cfsname + ' &res);\n')
            impl.append('template <>\n')
            impl.append('z3::expr __to_solver<' + cfsname + '>( gen &g, const  z3::expr &v, ' + cfsname + ' &val);\n')
            impl.append('template <>\n')
            impl.append('void __randomize<' + cfsname + '>( gen &g, const  z3::expr &v, const std::string &sort_name);\n')

    for dom in all_ctuples():
        emit_ctuple_equality(impl,dom,classname)

    for cpptype in cpptypes:
        cpptype.emit_templates()

    global native_classname
    global global_classname
    once_memo = set()
    for native in im.module.natives:
        tag = native_type(native)
        if tag == "impl" or tag.startswith('encode'):
            native_classname = classname
#            print 'native_classname:{}'.format(native_classname)
            code = native_to_str(native)
            native_classname = None
            if code not in once_memo:
                once_memo.add(code)
                impl.append(code)


    impl.append("int " + classname)
    if target.get() in ["gen","test"]:
        impl.append(
"""::___ivy_choose(int rng,const char *name,int id) {
        std::ostringstream ss;
        ss << name << ':' << id;;
        for (unsigned i = 0; i < ___ivy_stack.size(); i++)
            ss << ':' << ___ivy_stack[i];
        return ___ivy_gen->choose(rng,ss.str().c_str());
    }
""")
    else:
        impl.append(
"""::___ivy_choose(int rng,const char *name,int id) {
        return 0;
    }
""")

    global declared_ctuples
    declared_ctuples = set()
    with ivy_cpp.CppClassName(classname):
        declare_all_ctuples(header)
        declare_all_ctuples_hash(header,classname)
        for sym in all_state_symbols():
            if sym_is_member(sym):
                declare_symbol(header,sym)
#    for sym in il.sig.constructors:
#        declare_symbol(header,sym)
    for sname in il.sig.interp:
        header.append('    long long __CARD__' + varname(sname) + ';\n')
    find_import_callers()
    for ldf in im.module.definitions + im.module.native_definitions:
        with ivy_ast.ASTContext(ldf):
            emit_derived(header,impl,ldf.formula,classname)
    for sortname, conss in im.module.sort_constructors.items():
        for cons in conss:
            emit_constructor(header,impl,cons,classname)
    for native in im.module.natives:
        tag = native_type(native)
        if tag.startswith('encode'):
            tag = native_to_str(native,code=tag) # do the anti-quoting
            tag = tag[6:].strip().replace('__','.')
            if tag not in il.sig.sorts:
                raise iu.IvyError(native,"{} is not a declared sort".format(tag))
            if tag in encoded_sorts:
                raise iu.IvyError(native,"duplicate encoding for sort {}".format(tag))
            encoded_sorts.add(tag)
            continue
        if tag not in ["member","init","header","impl","inline"]:
            raise iu.IvyError(native,"syntax error at token {}".format(tag))
        if tag == "member":
            emit_native(header,impl,native,classname)

    # declare one counter for each progress obligation
    # TRICKY: these symbols are boolean but we create a C++ int
    for df in im.module.progress:
        declare_symbol(header,df.args[0].rep,c_type = 'int')

    header.append('    ');
    emit_param_decls(header,classname,im.module.params)
    header.append(';\n');
#    im.module.actions['.init'] = init_method()
    emit_initial_action(header,impl,classname)
    for a in im.module.actions:
        emit_action(header,impl,a,classname)
    emit_tick(header,impl,classname)
    header.append('};\n')

    impl.append(classname + '::')
    emit_param_decls(impl,classname,im.module.params)
    impl.append('{\n')
    impl.append('#ifdef _WIN32\n');
    impl.append('mutex = CreateMutex(NULL,FALSE,NULL);\n')
    impl.append('#else\n');
    impl.append('pthread_mutex_init(&mutex,NULL);\n')
    impl.append('#endif\n');
    impl.append('__lock();\n');
    enums = set(sym.sort.name for sym in il.sig.constructors)  
#    for sortname in enums:
#        for i,n in enumerate(il.sig.sorts[sortname].extension):
#            impl.append('    {} = {};\n'.format(varname(n),i))
    for sortname in il.sig.interp:
        if sortname in il.sig.sorts:
            impl.append('    __CARD__{} = {};\n'.format(varname(sortname),csortcard(il.sig.sorts[sortname])))
    for native in im.module.natives:
        tag = native_type(native)
        if tag == "init":
            vs = [il.Symbol(v.rep,im.module.sig.sorts[v.sort]) for v in native.args[0].args] if native.args[0] is not None else []
            global indent_level
            indent_level += 1
            open_loop(impl,vs)
            code = native_to_str(native,reference=True)
            indent_code(impl,code)
            close_loop(impl,vs)
            indent_level -= 1
    if target.get() not in ["gen","test"]:
        emit_one_initial_state(impl)
    else:
        emit_parameter_assignments(impl)

    impl.append('}\n')

    impl.append("""CLASSNAME::~CLASSNAME(){
    __lock(); // otherwise, thread may die holding lock!
    for (unsigned i = 0; i < thread_ids.size(); i++){
#ifdef _WIN32
       // No idea how to cancel a thread on Windows. We just suspend it
       // so it can't cause any harm as we destruct this object.
       SuspendThread(thread_ids[i]);
#else
        pthread_cancel(thread_ids[i]);
        pthread_join(thread_ids[i],NULL);
#endif
    }
    __unlock();
}
""".replace('CLASSNAME',classname))

    for native in im.module.natives:
        tag = native_type(native)
        if tag == "inline":
            native_classname = classname
            code = native_to_str(native)
            native_classname = None
            if code not in once_memo:
                once_memo.add(code)
                header.append(code)

 
    ivy_cpp.context.globals.code.extend(header)
    ivy_cpp.context.members.code = []
    header = ivy_cpp.context.globals.code

    if target.get() in ["gen","test"]:
        sf = header if target.get() == "gen" else impl
        if target.get() == "gen":
            emit_boilerplate1(sf,impl,classname)
        emit_init_gen(sf,impl,classname)
        for name,action in im.module.actions.items():
            if name in im.module.public_actions:
                emit_action_gen(sf,impl,name,action,classname)

    enum_sort_names = [s for s in sorted(il.sig.sorts) if isinstance(il.sig.sorts[s],il.EnumeratedSort)]
    if True or target.get() == "repl":
        # forward declare all the equality operations for variant types
        for sort_name in im.module.sort_order:
            if sort_name in im.module.variants:
                csname = varname(sort_name)
                cfsname = classname + '::' + csname
                code_line(header,'inline bool operator ==(const {} &s, const {} &t);'.format(cfsname,cfsname))

        # Tricky: inlines for for supertypes have to come *after* the inlines
        # for the subtypes. So we re-sort the types accordingly.
        arcs = [(x,s) for s in im.module.sort_order for x in im.sort_dependencies(im.module,s,with_variants=True)]
        variant_of = set((x.name,y) for y,l in im.module.variants.items() for x in l)
        arcs = [a for a in arcs if a in variant_of]
        inline_sort_order = iu.topological_sort(im.module.sort_order,arcs)
        global_classname = classname
        for sort_name in inline_sort_order:
            if sort_name in im.module.variants:
                sort = im.module.sig.sorts[sort_name] 
                assert sort in sort_to_cpptype
                if sort in sort_to_cpptype:
                    sort_to_cpptype[sort].emit_inlines()
                continue
            if sort_name not in sorted(im.module.sort_destructors):
                continue
            destrs = im.module.sort_destructors[sort_name]
            sort = im.module.sig.sorts[sort_name]
            csname = varname(sort_name)
            cfsname = classname + '::' + csname
            if sort_name not in encoded_sorts:
                open_scope(impl,line='std::ostream &operator <<(std::ostream &s, const {} &t)'.format(cfsname))
                code_line(impl,'s<<"{"')
                for idx,sym in enumerate(destrs):
                    if idx > 0:
                        code_line(impl,'s<<","')
                    code_line(impl,'s<< "' + memname(sym) + ':"')
                    dom = sym.sort.dom[1:]
                    vs = variables(dom)
                    for d,v in zip(dom,vs):
                        code_line(impl,'s << "["')
                        open_loop(impl,[v])
                        code_line(impl,'if ({}) s << ","'.format(varname(v)))
                    code_line(impl,'s << t.' + memname(sym) + subscripts(vs))
                    for d,v in zip(dom,vs):
                        close_loop(impl,[v])
                        code_line(impl,'s << "]"')
                code_line(impl,'s<<"}"')
                code_line(impl,'return s')
                close_scope(impl)

            open_scope(header,line='inline bool operator ==(const {} &s, const {} &t)'.format(cfsname,cfsname))
            s = il.Symbol('s',sort)
            t = il.Symbol('t',sort)
            code_line(header,'return ' + code_eval(header,il.And(*[field_eq(s,t,sym) for sym in destrs])))
            close_scope(header)

            if sort_name not in encoded_sorts:
                impl.append('template <>\n')
                open_scope(impl,line='void  __ser<' + cfsname + '>(ivy_ser &res, const ' + cfsname + '&t)')
                code_line(impl,"res.open_struct()")
                for idx,sym in enumerate(destrs):
                    dom = sym.sort.dom[1:]
                    vs = variables(dom)
                    for d,v in zip(dom,vs):
                        open_loop(impl,[v])
                    code_line(impl,'res.open_field("'+memname(sym)+'")')
                    code_line(impl,'__ser<' + ctype(sym.sort.rng,classname=classname) + '>(res,t.' + memname(sym) + subscripts(vs) + ')')
                    code_line(impl,'res.close_field()')
                    for d,v in zip(dom,vs):
                        close_loop(impl,[v])
                code_line(impl,"res.close_struct()")
                close_scope(impl)
                #chris
                impl.append('template <>\n')
                open_scope(impl,line='void  __ser<' + cfsname + '>(ivy_ser_128 &res, const ' + cfsname + '&t)')
                code_line(impl,"res.open_struct()")
                for idx,sym in enumerate(destrs):
                    dom = sym.sort.dom[1:]
                    vs = variables(dom)
                    for d,v in zip(dom,vs):
                        open_loop(impl,[v])
                    code_line(impl,'res.open_field("'+memname(sym)+'")')
                    code_line(impl,'__ser<' + ctype(sym.sort.rng,classname=classname) + '>(res,t.' + memname(sym) + subscripts(vs) + ')')
                    code_line(impl,'res.close_field()')
                    for d,v in zip(dom,vs):
                        close_loop(impl,[v])
                code_line(impl,"res.close_struct()")
                close_scope(impl)

        global_classname = None


        for sort_name in enum_sort_names:
            sort = im.module.sig.sorts[sort_name]
            csname = varname(sort_name)
            cfsname = classname + '::' + csname
            if sort_name not in encoded_sorts:
                open_scope(impl,line='std::ostream &operator <<(std::ostream &s, const {} &t)'.format(cfsname))
                for idx,sym in enumerate(sort.extension):
                    code_line(impl,'if (t == {}) s<<"{}"'.format(classname + '::' + varname(sym),memname(sym)))
                code_line(impl,'return s')
                close_scope(impl)
                impl.append('template <>\n')
                open_scope(impl,line='void  __ser<' + cfsname + '>(ivy_ser &res, const ' + cfsname + '&t)')
                code_line(impl,'__ser(res,(int)t)')
                close_scope(impl)
                #chris
                impl.append('template <>\n')
                open_scope(impl,line='void  __ser<' + cfsname + '>(ivy_ser_128 &res, const ' + cfsname + '&t)')
                code_line(impl,'__ser(res,(int)t)')
                close_scope(impl)


        if target.get() in ["repl","test"]:

            if  emit_main:
                emit_repl_imports(header,impl,classname)
                emit_repl_boilerplate1(header,impl,classname)

            global_classname = classname
            for sort_name in sorted(im.module.sort_destructors):
                destrs = im.module.sort_destructors[sort_name]
                sort = im.module.sig.sorts[sort_name]
                csname = varname(sort_name)
                cfsname = classname + '::' + csname
                if sort_name not in encoded_sorts:
                    impl.append('template <>\n')
                    open_scope(impl,line=cfsname + ' _arg<' + cfsname + '>(std::vector<ivy_value> &args, unsigned idx, long long bound)')
                    code_line(impl,cfsname + ' res')
                    assign_zero_symbol(impl,il.Symbol('res',sort))
                    code_line(impl,'ivy_value &arg = args[idx]')
                    # code_line(impl,'if (arg.atom.size() || arg.fields.size() != {}) throw out_of_bounds("wrong number of fields",args[idx].pos)'.format(len(destrs)))
                    code_line(impl,'std::vector<ivy_value> tmp_args(1)')
                    open_scope(impl,line = 'for (unsigned i = 0; i < arg.fields.size(); i++)')
                    open_scope(impl,line='if (arg.fields[{}].is_member())'.format('i'))
                    code_line(impl,'tmp_args[0] = arg.fields[{}].fields[0]'.format('i'))
                    for idx,sym in enumerate(destrs):
                        fname = memname(sym)
                        open_scope(impl,line = '{}if (arg.fields[{}].atom == "{}")'.format('else ' if idx > 0 else '','i',fname))
                        vs = variables(sym.sort.dom[1:])
                        for v in vs:
                            open_scope(impl)
                            code_line(impl,'ivy_value tmp = tmp_args[0]')
                            code_line(impl,'if(tmp.atom.size() || tmp.fields.size() != {}) throw out_of_bounds(idx,tmp.pos)'.format(csortcard(v.sort)))
                            open_loop(impl,[v])
                            code_line(impl,'std::vector<ivy_value> tmp_args(1)')
                            code_line(impl,'tmp_args[0] = tmp.fields[{}]'.format(varname(v)))
                        open_scope(impl,line='try')
                        code_line(impl,'res.'+fname+''.join('[{}]'.format(varname(v)) for v in vs) + ' = _arg<'+ctype(sym.sort.rng,classname=classname)
                                  +'>(tmp_args,0,{})'.format(csortcard(sym.sort.rng)))
                        close_scope(impl)
                        open_scope(impl,line='catch(const out_of_bounds &err)')
                        code_line(impl,'throw out_of_bounds("in field {}: " + err.txt,err.pos)'.format(fname))
                        close_scope(impl)
                        for v in vs:
                            close_loop(impl,[v])
                            close_scope(impl)
                        close_scope(impl)
                    code_line(impl,'{} throw out_of_bounds("unexpected field: " + arg.fields[{}].atom,arg.fields[{}].pos)'.format('else ' if len(destrs) > 0 else '','i','i'))
                    close_scope(impl)
                    code_line(impl,'else throw out_of_bounds("expected struct",args[idx].pos)')
                    close_scope(impl)
                    code_line(impl,'return res')
                    close_scope(impl)

                    impl.append('template <>\n')
                    open_scope(impl,line='void __deser<' + cfsname + '>(ivy_deser &inp, ' + cfsname + ' &res)')
                    code_line(impl,"inp.open_struct()")
                    for idx,sym in enumerate(destrs):
                        fname = memname(sym)
                        vs = variables(sym.sort.dom[1:])
                        code_line(impl,'inp.open_field("'+fname+'")')
                        for v in vs:
                            card = sort_card(v.sort)
                            code_line(impl,'inp.open_list()')
                            open_loop(impl,[v])
                        code_line(impl,'__deser(inp,res.'+fname+''.join('[{}]'.format(varname(v)) for v in vs) + ')')
                        for v in vs:
                            close_loop(impl,[v])
                            code_line(impl,'inp.close_list()')
                        code_line(impl,'inp.close_field()')
                    code_line(impl,"inp.close_struct()")
                    close_scope(impl)
                    #chris
                    impl.append('template <>\n')
                    open_scope(impl,line='void __deser<' + cfsname + '>(ivy_deser_128 &inp, ' + cfsname + ' &res)')
                    code_line(impl,"inp.open_struct()")
                    for idx,sym in enumerate(destrs):
                        fname = memname(sym)
                        vs = variables(sym.sort.dom[1:])
                        code_line(impl,'inp.open_field("'+fname+'")')
                        for v in vs:
                            card = sort_card(v.sort)
                            code_line(impl,'inp.open_list('+str(card)+')')
                            open_loop(impl,[v])
                        code_line(impl,'__deser(inp,res.'+fname+''.join('[{}]'.format(varname(v)) for v in vs) + ')')
                        for v in vs:
                            close_loop(impl,[v])
                            code_line(impl,'inp.close_list()')
                        code_line(impl,'inp.close_field()')
                    code_line(impl,"inp.close_struct()")
                    close_scope(impl)
                if target.get() in ["gen","test"]:
                    impl.append('template <>\n')
                    open_scope(impl,line='void  __from_solver<' + cfsname + '>( gen &g, const  z3::expr &v,' + cfsname + ' &res)')
                    for idx,sym in enumerate(destrs):
                        fname = memname(sym)
                        vs = variables(sym.sort.dom[1:])
                        for v in vs:
                            open_loop(impl,[v])
                        sname = slv.solver_name(sym)
                        code_line(impl,'__from_solver(g,g.apply("'+sname+'",v'+ ''.join(',g.int_to_z3(g.sort("'+v.sort.name+'"),'+varname(v)+')' for v in vs)+'),res.'+fname+''.join('[{}]'.format(varname(v)) for v in vs) + ')')
                        for v in vs:
                            close_loop(impl,[v])
                    close_scope(impl)
                    impl.append('template <>\n')
                    open_scope(impl,line='z3::expr  __to_solver<' + cfsname + '>( gen &g, const  z3::expr &v,' + cfsname + ' &val)')
                    code_line(impl,'std::string fname = g.fresh_name()')
                    code_line(impl,'z3::expr tmp = g.ctx.constant(fname.c_str(),g.sort("{}"))'.format(sort.name))
#                    code_line(impl,'z3::expr res = g.ctx.bool_val(1)')
                    for idx,sym in enumerate(destrs):
                        fname = memname(sym)
                        vs = variables(sym.sort.dom[1:])
                        for v in vs:
                            open_loop(impl,[v])
                        sname = slv.solver_name(sym)
                        code_line(impl,'g.slvr.add(__to_solver(g,g.apply("'+sname+'",tmp'+ ''.join(',g.int_to_z3(g.sort("'+v.sort.name+'"),'+varname(v)+')' for v in vs)+'),val.'+fname+''.join('[{}]'.format(varname(v)) for v in vs) + '))')
                        for v in vs:
                            close_loop(impl,[v])
                    code_line(impl,'return v==tmp')
                    close_scope(impl)
                    impl.append('template <>\n')
                    open_scope(impl,line='void  __randomize<' + cfsname + '>( gen &g, const  z3::expr &v, const std::string &sort_name)')
                    for idx,sym in enumerate(destrs):
                        # we can't randomize a type that z3 is representing with an uninterpreted sort,
                        # because z3 has no numerals for these sorts. Rather than throwing an error, however,
                        # we just don't randomize, in case randomization for this type is not actually needed.
                        # In principle, we should check whether randomiation is needed but this is pretty tricky.
                        if is_really_uninterpreted_sort(sym.sort.rng):
                            continue
#                            raise iu.IvyError(None,'cannot create test generator because type {} is uninterpreted'.format(sym.sort.rng))
                        fname = memname(sym)
                        vs = variables(sym.sort.dom[1:])
                        for v in vs:
                            open_loop(impl,[v])
                        sname = slv.solver_name(sym)
                        code_line(impl,'__randomize<'+ctypefull(sym.sort.rng,classname=classname)+'>(g,g.apply("'+sname+'",v'+ ''.join(',g.int_to_z3(g.sort("'+v.sort.name+'"),'+varname(v)+')' for v in vs)+'),"'+sym.sort.rng.name+'")')
                        for v in vs:
                            close_loop(impl,[v])
                    close_scope(impl)
            global_classname = None


            for sort_name in enum_sort_names:
                sort = im.module.sig.sorts[sort_name]
                csname = varname(sort_name)
                cfsname = classname + '::' + csname
                if sort_name not in encoded_sorts:
                    impl.append('template <>\n')
                    open_scope(impl,line=cfsname + ' _arg<' + cfsname + '>(std::vector<ivy_value> &args, unsigned idx, long long bound)')
                    code_line(impl,'ivy_value &arg = args[idx]')
                    code_line(impl,'if (arg.atom.size() == 0 || arg.fields.size() != 0) throw out_of_bounds(idx,arg.pos)')
                    for idx,sym in enumerate(sort.extension):
                        code_line(impl,'if(arg.atom == "{}") return {}'.format(memname(sym),classname + '::' + varname(sym)))
                    code_line(impl,'throw out_of_bounds("bad value: " + arg.atom,arg.pos)')
                    close_scope(impl)
                    impl.append('template <>\n')
                    open_scope(impl,line='void __deser<' + cfsname + '>(ivy_deser &inp, ' + cfsname + ' &res)')
                    code_line(impl,'int __res')
                    code_line(impl,'__deser(inp,__res)')
                    code_line(impl,'res = ({})__res'.format(cfsname))
                    close_scope(impl)
                    #chris
                    impl.append('template <>\n')
                    open_scope(impl,line='void __deser<' + cfsname + '>(ivy_deser_128 &inp, ' + cfsname + ' &res)')
                    code_line(impl,'int __res')
                    code_line(impl,'__deser(inp,__res)')
                    code_line(impl,'res = ({})__res'.format(cfsname))
                    close_scope(impl)
                if target.get() in ["test","gen"]:
                    impl.append('template <>\n')
                    open_scope(impl,line='z3::expr  __to_solver<' + cfsname + '>( gen &g, const  z3::expr &v,' + cfsname + ' &val)')
                    code_line(impl,'int thing = val')
                    code_line(impl,'return __to_solver<int>(g,v,thing)')
                    close_scope(impl)
                    impl.append('template <>\n')
                    open_scope(impl,line='void  __from_solver<' + cfsname + '>( gen &g, const  z3::expr &v,' + cfsname + ' &res)')
                    code_line(impl,'int temp')
                    code_line(impl,'__from_solver<int>(g,v,temp)')
                    code_line(impl,'res = ('+cfsname+')temp')
                    close_scope(impl)
                    impl.append('template <>\n')
                    open_scope(impl,line='void  __randomize<' + cfsname + '>( gen &g, const  z3::expr &v, const std::string &sort_name)')
                    code_line(impl,'__randomize<int>(g,v,sort_name)')
                    close_scope(impl)


            if emit_main:
                if target.get() in ["gen","test"]:
                    emit_all_ctuples_to_solver(impl,classname)


                emit_repl_boilerplate1a(header,impl,classname)
                for actname in sorted(im.module.public_actions):
                    username = actname[4:] if actname.startswith("ext:") else actname
                    action = im.module.actions[actname]
                    argstrings = ['_arg<{}>(args,{},{})'.format(ctype(x.sort,classname=classname),idx,csortcard(x.sort)) for idx,x in enumerate(action.formal_params)]
                    getargs = ','.join(argstrings)
                    thing = "ivy.methodname(getargs)"
                    if action.formal_returns:
                        thing = '__ivy_out ' + number_format + ' << "= " << ' + thing + " << std::endl"
                    if target.get() == "repl" and opt_trace.get():
                        if action.formal_params:
                            trace_code = '__ivy_out ' + number_format + ' << "{}("'.format(actname.split(':')[-1]) + ' << "," '.join(' << {}'.format(arg) for arg in argstrings) + ' << ") {" << std::endl'
                        else:
                            trace_code = '__ivy_out ' + number_format + ' << "{} {{"'.format(actname.split(':')[-1]) + ' << std::endl'
                        thing = trace_code + ';\n                    ' + thing + ';\n                    __ivy_out << "}" << std::endl' 
                    impl.append("""
                if (action == "actname") {
                    check_arity(args,numargs,action);
                    thing;
                }
                else
    """.replace('thing',thing).replace('actname',username).replace('methodname',varname(actname)).replace('numargs',str(len(action.formal_params))).replace('getargs',getargs))
                emit_repl_boilerplate2(header,impl,classname)

                print("test_iter =")
                print(opt_test_iters.get())
                impl.append("int "+ opt_main.get() + "(int argc, char **argv){\n")
                impl.append("        int test_iters = TEST_ITERS;\n".replace('TEST_ITERS',opt_test_iters.get()))
                impl.append("        int runs = TEST_RUNS;\n".replace('TEST_RUNS',opt_test_runs.get()))
                for p,d in zip(im.module.params,im.module.param_defaults):
#                    impl.append('    {} p__'.format(ctypefull(p.sort,classname=classname))+varname(p)+';\n')
                    impl.append('    {};\n'.format(sym_decl(p.prefix('p__'),classname=classname)))
                    if d is not None:
                        if il.is_function_sort(p.sort):
                            raise iu.IvyError(None,"can't handle default values for function-sorted parameter {}".format(p))
                        emit_value_parser(impl,p,'"{}"'.format(d.rep.replace('"','\\"')),classname,lineno=d.lineno)
                impl.append("""
    int seed = 1;
    int sleep_ms = 10;
    int final_ms = 0; 
    
    std::vector<char *> pargs; // positional args
    pargs.push_back(argv[0]);
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        size_t p = arg.find('=');
        if (p == std::string::npos)
            pargs.push_back(argv[i]);
        else {
            std::string param = arg.substr(0,p);
            std::string value = arg.substr(p+1);
""")
                pos_params = []
                for p,d in zip(im.module.params,im.module.param_defaults):
                    if d is None:
                        pos_params.append(p)
                    else:
                        impl.append('            if (param == "{}") {{\n'.format(str(p)))
                        emit_value_parser(impl,p,"value",classname)
                        impl.append('                continue;\n')
                        impl.append('            }\n')
                
                impl.append("""
            if (param == "out") {
                __ivy_out.open(value.c_str());
                if (!__ivy_out) {
                    std::cerr << "cannot open to write: " << value << std::endl;
                    return 1;
                }
            }
            else if (param == "iters") {
                test_iters = atoi(value.c_str());
            }
            else if (param == "runs") {
                runs = atoi(value.c_str());
            }
            else if (param == "seed") {
                seed = atoi(value.c_str());
            }
            else if (param == "delay") {
                sleep_ms = atoi(value.c_str());
            }
            else if (param == "wait") {
                final_ms = atoi(value.c_str());
            }
            else if (param == "modelfile") {
                __ivy_modelfile.open(value.c_str());
                if (!__ivy_modelfile) {
                    std::cerr << "cannot open to write: " << value << std::endl;
                    return 1;
                }
            }
            else {
                std::cerr << "unknown option: " << param << std::endl;
                //return 1;
            }
        }
    }
    srand(seed);
    if (!__ivy_out.is_open())
        __ivy_out.basic_ios<char>::rdbuf(std::cout.rdbuf());
    argc = pargs.size();
    argv = &pargs[0];
    //chris 
    struct sigaction sa;
	sa.sa_handler = signal1_handler_generating;
	sa.sa_flags = SA_RESTART;
	sigemptyset(&sa.sa_mask);

	if (sigaction(SIGUSR1, &sa, NULL) == -1) {
		perror("sigaction");
		return 1;
	}
    struct sigaction sa2;
	sa2.sa_handler = signal2_handler_generating;
	sa2.sa_flags = SA_RESTART;
	sigemptyset(&sa2.sa_mask);

	if (sigaction(SIGUSR2, &sa2, NULL) == -1) {
		perror("sigaction");
		return 1;
	}
 
    /*if (signal(SIGUSR1, signal1_handler_generating) == SIG_ERR) {
        perror("Signal1 registration failed");
        return 1;
    }
    if (signal(SIGUSR2, signal2_handler_generating) == SIG_ERR) {
        perror("Signal2 registration failed");
        return 1;
    }*/
""")
                impl.append("    if (argc == "+str(len(pos_params)+2)+"){\n")
                impl.append("        argc--;\n")
                impl.append("        int fd = _open(argv[argc],0);\n")
                impl.append("        if (fd < 0){\n")
                impl.append('            std::cerr << "cannot open to read: " << argv[argc] << "\\n";\n')
                impl.append('            __ivy_exit(1);\n')
                impl.append('        }\n')
                impl.append("        _dup2(fd, 0);\n")
                impl.append("    }\n")
                impl.append("    if (argc != "+str(len(pos_params)+1)+"){\n")
                impl.append('        std::cerr << "usage: {} {}\\n";\n'
                            .format(classname,' '.join(map(str,pos_params))))
                impl.append('        __ivy_exit(1);\n    }\n')
                impl.append('    std::vector<std::string> args;\n')
                impl.append('    std::vector<ivy_value> arg_values({});\n'.format(len(pos_params)))
                impl.append('    for(int i = 1; i < argc;i++){args.push_back(argv[i]);}\n')
                for idx,s in enumerate(pos_params):
                    impl.append('    try {\n')
                    impl.append('        int pos = 0;\n')
                    impl.append('        arg_values[{}] = parse_value(args[{}],pos);\n'.format(idx,idx))
                    if not il.is_function_sort(s.sort):
                        impl.append('        p__'+varname(s)+' =  _arg<{}>(arg_values,{},{});\n'
                                    .format(ctype(s.sort,classname=classname),idx,csortcard(s.sort)))
                    else:
                        def make_function_app(s,args):
                            res = varname(s)
                            if is_large_type(s.sort) and len(s.sort.dom) > 1:
                                res +=('[' + ctuple(s.sort.dom,classname=classname) + '(')
                                first = True
                                for a in args:
                                    if not first:
                                        res += ','
                                    res += a
                                    first = False
                                res += ')]'
                            else: 
                                for a in args:
                                    res += '[{}]'.format(a)
                            return res
                        impl.append('        ivy_value &arg = arg_values[{}];\n'.format(idx))
                        impl.append('        if (arg.atom.size())\n')
                        impl.append('            throw out_of_bounds({});\n'.format(idx))
                        impl.append('        for (unsigned i = 0; i < arg.fields.size(); i++) {\n')
                        impl.append('            if (arg.fields[i].fields.size() != {})\n'.format(1 + len(s.sort.dom))) 
                        impl.append('                throw out_of_bounds({});\n'.format(idx))
                        impl.append('            ' + make_function_app(s.prefix('p__'),['_arg<{}>(arg.fields[i].fields,{},0)'.format(ctype(domt,classname=classname),q) for q,domt in enumerate(s.sort.dom)]))
                        impl.append('= _arg<{}>(arg.fields[i].fields,{},0);\n'.format(ctype(s.sort.rng,classname=classname),len(s.sort.dom)))
                        impl.append('        }\n')
                    impl.append('    }\n    catch(out_of_bounds &) {\n')
                    impl.append('        std::cerr << "parameter {} out of bounds\\n";\n'.format(varname(s)))
                    impl.append('        __ivy_exit(1);\n    }\n')
                    impl.append('    catch(syntax_error &) {\n')
                    impl.append('        std::cerr << "syntax error in command argument\\n";\n')
                    impl.append('        __ivy_exit(1);\n    }\n')
                cp = '(' + ','.join('p__'+varname(s) for s in im.module.params) + ')' if im.module.params else ''
                emit_winsock_init(impl)
                if target.get() == "test":
                    impl.append('    for(int runidx = 0; runidx < runs; runidx++) {\n')
                    impl.append('    initializing = true;\n')
                impl.append('    {}_repl ivy{};\n'
                            .format(classname,cp))
                impl.append('    for(unsigned i = 0; i < argc; i++) {ivy.__argv.push_back(argv[i]);}\n')
                if target.get() == "test":
                    impl.append('    ivy._generating = false;\n')
                    emit_repl_boilerplate3test(header,impl,classname)
                else:
                    impl.append("    ivy.__init();\n");
                    if im.module.public_actions:
                        emit_repl_boilerplate3(header,impl,classname)
                    else:
                        emit_repl_boilerplate3server(header,impl,classname)
                if target.get() == "test":
                    impl.append('    }\n')
                impl.append("    return 0;\n}\n")


        
    return ivy_cpp.context.globals.get_file(), ivy_cpp.context.impls.get_file()

def emit_value_parser(impl,s,arg,classname,lineno=None):
    """
    Parses a value and assigns it to a variable.

    Args:
        impl (list): The list to append the implementation code to.
        s (str): The name of the variable.
        arg (str): The argument to parse.
        classname (str): The name of the class.
        lineno (int, optional): The line number. Defaults to None.
    """
    impl.append('    try {\n')
    impl.append('        int pos = 0;\n')
    impl.append('        std::vector<ivy_value> arg_values; arg_values.resize(1); arg_values[0] = parse_value({},pos);\n'.format(arg))
    impl.append('        p__'+varname(s)+' =  _arg<{}>(arg_values,{},{});\n'
                                .format(ctype(s.sort,classname=classname),0,csortcard(s.sort)))
    impl.append('    }\n    catch(out_of_bounds &) {\n')
    impl.append('        std::cerr << "{}parameter {} out of bounds\\n";\n'.format(str(lineno) if lineno else "",str(s)))
    impl.append('        __ivy_exit(1);\n    }\n')
    impl.append('    catch(syntax_error &) {\n')
    impl.append('        std::cerr << "{}syntax error in parameter value {}\\n";\n'.format(str(lineno) if lineno else "",str(s)))
    impl.append('        __ivy_exit(1);\n    }\n')


def check_representable(sym,ast=None,skip_args=0):
    return True

def really_check_representable(sym,ast=None,skip_args=0):
    """
    Check if a symbol is representable.

    Args:
        sym: The symbol to check.
        ast: The abstract syntax tree (AST) associated with the symbol. (default: None)
        skip_args: The number of arguments to skip in the domain of the symbol's sort. (default: 0)

    Raises:
        iu.IvyError: If the initial constraint cannot be compiled due to a large type.

    Returns:
        None
    """                
    sort = sym.sort
    if hasattr(sort,'dom'):
        for domsort in sort.dom[skip_args:]:
            card = sort_card(domsort)
            if card == None or card > large_thresh:
                raise iu.IvyError(ast,'cannot compile initial constraint on "{}" because type {} is large. suggest using "after init"'.format(sym,domsort))

def cstr(term):
    if isinstance(term,il.Symbol):
        return varname(term).split('!')[-1]
    return il.fmla_to_str_ambiguous(term)

def subscripts(vs):
    return ''.join('['+varname(v)+']' for v in vs)

def variables(sorts,start=0):
    return [il.Variable('X__'+str(idx+start),s) for idx,s in enumerate(sorts)]


def assign_symbol_value(header,lhs_text,m,v,same=False):
    """
    Assigns a symbol value to the header.

    Args:
        header (list): The header to which the assignment will be appended.
        lhs_text (list): The left-hand side text of the assignment.
        m (function): The function used to convert the symbol value to a string.
        v: The symbol value to be assigned.
        same (bool, optional): Indicates whether the symbol value is the same for all iterations. Defaults to False.
    """
    sort = v.sort
    if hasattr(sort,'name') and sort.name in im.module.sort_destructors:
        for sym in im.module.sort_destructors[sort.name]:
            check_representable(sym,skip_args=1) # TODO return always true
            dom = sym.sort.dom[1:]
            if dom:
                if same:
                    vs = variables(dom)
                    open_loop(header,vs)
                    term = sym(*([v] + vs))
                    ctext = memname(sym) + ''.join('['+varname(a)+']' for a in vs)
                    assign_symbol_value(header,lhs_text+[ctext],m,term,same)
                    close_loop(header,vs)
                else:
                    for args in itertools.product(*[list(range(sort_card(s))) for s in dom]):
                        term = sym(*([v] + [il.Symbol(str(a),s) for a,s in zip(args,dom)]))
                        ctext = memname(sym) + ''.join('['+str(a)+']' for a in args)
                        assign_symbol_value(header,lhs_text+[ctext],m,term,same)
            else:
                assign_symbol_value(header,lhs_text+[memname(sym)],m,sym(v),same)
    else:
        mv = m(v)
        if mv != None:           
            header.append('    ' + '.'.join(lhs_text) + ' = ' + m(v) + ';\n')
        

def assign_symbol_from_model(header,sym,m):
    """
    Assigns a symbol from the model to the header.

    This function evaluates a given symbol from the model and assigns its value
    to the header. It skips interpreted symbols and structs. For symbols with
    domains, it iterates over all possible arguments and assigns values accordingly.

    Args:
        header (str): The header to which the symbol's value will be assigned.
        sym (Symbol): The symbol to be evaluated and assigned.
        m (Model): The model from which the symbol's value is evaluated.

    Returns:
        None
    """
    if slv.solver_name(sym) == None:
        return # skip interpreted symbols
    if sym.name in im.module.destructor_sorts:
        return # skip structs
    name, sort = sym.name,sym.sort
    really_check_representable(sym)
    fun = lambda v: cstr(m.eval_to_constant(v))
    if hasattr(sort,'dom'):
        for args in itertools.product(*[list(range(sort_card(s))) for s in sym.sort.dom]):
            term = sym(*[il.Symbol(str(a),s) for a,s in zip(args,sym.sort.dom)])
            ctext = varname(sym.name) + ''.join('['+str(a)+']' for a in args)
            assign_symbol_value(header,[ctext],fun,term)
    else:
        assign_symbol_value(header,[varname(sym.name)],fun,sym)

def assign_array_from_model(impl,sym,prefix,fun):
    """
    Assigns values to an array from a model.

    This function assigns values to an array based on the provided model symbol.
    If the symbol's sort has a domain, it iterates over the variables in the domain,
    constructs the corresponding term, and assigns the value using the provided function.
    If the symbol's sort does not have a domain, it directly assigns the value.

    Args:
        impl: The implementation context or object.
        sym: The model symbol whose values are to be assigned.
        prefix: A string prefix to be used in the assignment.
        fun: A function used to assign values to the symbol.

    Returns:
        None
    """
    name, sort = sym.name,sym.sort
    if hasattr(sort,'dom'):
        vs = variables(sym.sort.dom)
        for v in vs:
            open_loop(impl,[v])
        term = sym(*vs)
        ctext = prefix + varname(sym.name) + ''.join('['+v.name+']' for v in vs)
        assign_symbol_value(impl,[ctext],fun,term)
        for v in vs:
            close_loop(impl,[v])
    else:
        assign_symbol_value(impl,[prefix+varname(sym.name)],fun,sym)
        
def check_init_cond(kind,lfmlas):
    """
    Checks the initial conditions for logical formulas.

    This function verifies that none of the logical formulas in `lfmlas` depend on any stripped parameters.
    If a dependency is found, an IvyError is raised.

    Args:
        kind (str): A string representing the kind of logical formula.
        lfmlas (list): A list of logical formula objects to be checked.

    Raises:
        IvyError: If any logical formula depends on a stripped parameter.
    """
    params = set(im.module.params)
    for lfmla in lfmlas:
        if any(c in params for c in ilu.used_symbols_ast(lfmla.formula)):
            raise iu.IvyError(lfmla,"{} depends on stripped parameter".format(kind))
        
    
def emit_one_initial_state(header):
    """
    Emit the initial state for the given header.

    This function checks the initial conditions and axioms, constructs the 
    necessary constraints, and generates the initial state based on these 
    constraints. If the initial conditions and/or axioms are inconsistent, 
    it raises an IvyError.

    Args:
        header: The header to which the initial state code will be emitted.

    Raises:
        IvyError: If the initial conditions and/or axioms are inconsistent.

    Notes:
        - The function uses the `im.module` to access initial conditions, 
          axioms, and relevant definitions.
        - It constructs constraints from initial conditions and axioms, 
          converts them to clauses, and attempts to get a model from these 
          clauses.
        - If a model is found, it assigns symbols from the model to the 
          header. If a symbol is not used, it creates a non-deterministic 
          symbol.
    """
    check_init_cond("initial condition",im.module.labeled_inits)
    check_init_cond("axiom",im.module.labeled_axioms)
        
    constraints = [ilu.clauses_to_formula(im.module.init_cond)]
    for a in im.module.axioms:
        constraints.append(a)
    for ldf in im.relevant_definitions(ilu.symbols_asts(constraints)):
        constraints.append(fix_definition(ldf.formula).to_constraint())
    clauses = ilu.formula_to_clauses(il.And(*constraints))
#    clauses = ilu.and_clauses(im.module.init_cond,im.module.background_theory())
    m = slv.get_model_clauses(clauses)
    if m == None:
        print(clauses)
        if iu.version_le(iu.get_string_version(),"1.6"):
            raise iu.IvyError(None,'Initial condition and/or axioms are inconsistent')
        else:
            raise iu.IvyError(None,'Axioms are inconsistent')
    used = ilu.used_symbols_clauses(clauses)
    for sym in all_state_symbols():
        if sym.name in im.module.destructor_sorts:
            continue
        if sym in im.module.params:
            vs = variables(sym.sort.dom)
            expr = sym(*vs) if vs else sym
            open_loop(header,vs)
            code_line(header,'this->' + code_eval(header,expr) + ' = ' + code_eval(header,expr))
            close_loop(header,vs)
        elif sym not in is_derived and not is_native_sym(sym):
            if sym in used:
                assign_symbol_from_model(header,sym,m)
            else:
                mk_nondet_sym(header,sym,'init',0)
#    action = ia.Sequence(*[a for n,a in im.module.initializers])
#    action.emit(header)

def emit_parameter_assignments(impl):
    """
    Generates and emits parameter assignment code for the given implementation.

    This function iterates over the parameters defined in the module and generates
    code to assign values to these parameters. For each parameter, it creates the
    necessary variable declarations, constructs the assignment expression, and 
    emits the corresponding code lines.

    Args:
        impl: The implementation object where the generated code will be emitted.

    Returns:
        None
    """
    for sym in im.module.params:
            vs = variables(sym.sort.dom)
            expr = sym(*vs) if vs else sym
            open_loop(impl,vs)
            code_line(impl,'this->' + code_eval(impl,expr) + ' = ' + code_eval(impl,expr))
            close_loop(impl,vs)
    

def emit_constant(self,header,code):
    """
    Emits the C++ code representation of a constant symbol.

    This function appends the appropriate C++ code for a given constant symbol
    to the provided `code` list. The behavior of the function depends on the 
    type and properties of the symbol.

    Parameters:
    - self: The symbol to be emitted.
    - header: A list to which any necessary header declarations can be appended.
    - code: A list to which the generated C++ code will be appended.

    Behavior:
    - If the symbol is derived, it appends the function name followed by '()'.
    - If the symbol is a numeral and has an interpretation as a range sort, it 
        generates a ternary expression to ensure the numeral is within bounds.
    - If the symbol is a native symbol, it generates a literal representation.
    - If the symbol has a string interpretation and is not a literal string, it 
        raises an error unless the symbol is '0', in which case it appends an empty string.
    - If the symbol's sort has destructors or is interpreted as a bit-vector, 
        it generates the appropriate C++ code.
    - If the symbol's sort has a corresponding C++ type, it uses the type's 
        literal method to generate the code.
    - If the symbol is a constructor and there is a delegate for enums, it 
        appends the delegate's namespace.

    Raises:
    - IvyError: If the symbol cannot be compiled due to unsupported numeral or sort.
    """
    if self in is_derived:
        code.append(funname(self.name)+'()')
        return
    if isinstance(self,il.Symbol) and self.is_numeral():
        itp = il.sig.interp.get(self.sort.name,None)
        if isinstance(itp,il.RangeSort):
            lb = varname(itp.lb.name)
            ub = varname(itp.ub.name)
            x = self.name
            code.append('( {} < {} ? {} : {} < {} ? {} : {})'.format(x,lb,lb,ub,x,ub,x))
            return
        if is_native_sym(self):
            vv = self.name if self.is_literal_string() else ('"' + self.name + '"') 
            code.append('__lit<'+varname(self.sort)+'>(' + vv + ')')
            return
        if has_string_interp(self.sort) and self.name[0] != '"' :
            if self.name == '0':
                code.append('""')
                return
            raise iu.IvyError(None,'Cannot compile numeral {} of string sort {}'.format(self,self.sort))
        if self.sort.name in im.module.sort_destructors:
            if self.name == '0':
                code.append(new_temp(header,sort=self.sort))
                return
            raise iu.IvyError(None,"cannot compile symbol {} of sort {}".format(self.name,self.sort))
        if self.sort.name in il.sig.interp and il.sig.interp[self.sort.name].startswith('bv['):
            sname,sparms = parse_int_params(il.sig.interp[self.sort.name])
            code.append('(' + varname(self.name) + ' & ' + str((1 << sparms[0]) -1) + ')')
            return
        if self.sort in sort_to_cpptype: 
            code.append(sort_to_cpptype[self.sort].literal(self.name))
            return
    if isinstance(self,il.Symbol) and self in il.sig.constructors:
        if delegate_enums_to:
            code.append(delegate_enums_to+'::')
    code.append(varname(self.name))
    if self in is_derived:
        code.append('()')

il.Symbol.emit   = emit_constant
il.Variable.emit = emit_constant

def emit_native_expr(self,header,code):
    code.append(native_expr_full(self))

ivy_ast.NativeExpr.emit = emit_native_expr

def parse_int_params(name):
    spl = name.split('[')
    name,things = spl[0],spl[1:]
#    print "things:".format(things)
    if not all(t.endswith(']') for t in things):
        raise SyntaxError()
    return name,[int(t[:-1]) for t in things]

def emit_special_op(self,op,header,code):
    """
    Emit C++ code for special operations.

    This method handles the emission of C++ code for specific operations such as 
    'concat' and bit-field extraction (bfe). It appends the generated C++ code 
    to the provided `code` list based on the operation type.

    Parameters:
    - op (str): The operation to be emitted. Supported operations are 'concat' 
        and operations starting with 'bfe['.
    - header (list): A list to which any necessary header includes or declarations 
        can be appended.
    - code (list): A list to which the generated C++ code will be appended.

    Raises:
    - IvyError: If the operation cannot be emitted as C++ code.
    """
    if op == 'concat':
        sort_name = il.sig.interp[self.args[1].sort.name]
        sname,sparms = parse_int_params(sort_name)
        if sname == 'bv' and len(sparms) == 1:
            code.append('(')
            self.args[0].emit(header,code)
            code.append(' << {} | '.format(sparms[0]))
            self.args[1].emit(header,code)
            code.append(')')
            return
    if op.startswith('bfe['):
        opname,opparms = parse_int_params(op)
        mask = (1 << (opparms[0]-opparms[1]+1)) - 1
        code.append('(')
        self.args[0].emit(header,code)
        code.append(' >> {} & {})'.format(opparms[1],mask))
        return
    raise iu.IvyError(self,"operator {} cannot be emitted as C++".format(op))

bv_ops = {
    'bvand' : '&',
    'bvor' : '|',
    'bvnot' : '~',
}

def emit_bv_op(self,header,code):
    """
    Emits the bit-vector operation code for the given operation.

    Args:
        header (list): A list to which header code can be appended.
        code (list): A list to which the generated code will be appended.

    Raises:
        IvyError: If the bit-field extraction operator is malformed.

    Notes:
        - The function handles different bit-vector operations based on the 
            function name.
        - For bit-field extraction (bfe), it parses the parameters and emits 
            the appropriate code.
        - For other operations, it uses a dictionary to map the function name 
            to the corresponding operator.
        - The result is masked to fit within the bit-width specified by the 
            sort parameters.
    """
    sname,sparms = parse_int_params(il.sig.interp[self.sort.name])
    code.append('(')
    code.append('(')
    if len(self.args) == 2:
        self.args[0].emit(header,code)
    if self.func.name.startswith('bfe['):
        fname,fparams = parse_int_params(self.func.name)
        if (len(fparams) != 2):
            iu.IvyError(None,'malformed operator: {}'.format(self.func.name))
        self.args[-1].emit(header,code)
        code.append(' >> {}) & {})'.format(fparams[0],2**(fparams[1]-fparams[0]+1)-1))
        return
    if self.func.name != 'cast':
        code.append(' {} '.format(bv_ops.get(self.func.name,self.func.name)))
    self.args[-1].emit(header,code)
    code.append(') & {})'.format((1 << sparms[0])-1))

def is_bv_term(self):
    if not il.is_first_order_sort(self.sort):
        return False
    itp = il.sig.interp.get(self.sort.name,None)
    return (isinstance(itp,str) and itp.startswith('bv[')
            or self.rep.name.startswith('bfe[') and ctype(self.args[0].sort) in int_ctypes)

def capture_emit(a,header,code,capture_args):
    """
    Emits code with a given header and optionally captures the emitted code.

    Parameters:
    a (object): An object that has an `emit` method.
    header (str): The header to be emitted.
    code (list): A list where the emitted code will be appended.
    capture_args (list or None): If not None, the emitted code will be captured 
                                    and appended to this list as a single string.

    Returns:
    None
    """
    if capture_args != None:
        tmp = []
        a.emit(header,tmp)
        code.extend(tmp)
        capture_args.append(''.join(tmp))
    else:
        a.emit(header,code)

delegate_methods_to = ''
delegate_enums_to   = ''

def emit_app(self,header,code,capture_args=None):
    """
    Emit the application of a function or operator in C++ code.

    This method handles various cases including macros, interpreted operations,
    bit-vector operations, casting, and uninterpreted operations. It generates
    the appropriate C++ code for the given function application.

    Args:
        header (list): A list to which header code lines are appended.
        code (list): A list to which the generated C++ code is appended.
        capture_args (optional): Additional arguments for capturing, if any.

    Raises:
        IvyError: If the symbol has no interpretation or if polymorphic operations
                    cannot be handled.
    """
    # handle macros
    if il.is_macro(self):
        return il.expand_macro(self).emit(header,code)
    # handle interpreted ops
    if slv.solver_name(self.func) == None or self.func.name == 'cast':
        if self.func.name in il.sig.interp and self.func.name != 'cast':
            op = il.sig.interp[self.func.name]
            emit_special_op(self,op,header,code)
            return
        if is_bv_term(self) and self.func.name != 'cast':
            emit_bv_op(self,header,code)
            return
        itp = il.sig.interp.get(self.func.sort.rng.name,None)
        if self.func.name == '-' and itp == 'nat':
            x = new_temp(header,self.func.sort.rng)
            code_line(header,x + ' = ' + code_eval(header,self.args[0]))
            y = new_temp(header,self.func.sort.rng)
            code_line(header,y + ' = ' + code_eval(header,self.args[1]))
            code.append('( {} < {} ? 0 : {} - {})'.format(x,y,x,y))
            return
        if self.func.name == 'cast':
            if len(self.args) == 1:
                atype = ctypefull(self.args[0].sort)
                if atype in ['int','long long','unsigned long long','unsigned',"unint128_t","int128_t"]:
                    if isinstance(itp,il.RangeSort):
                        x = new_temp(header)
                        code_line(header,x + ' = ' + code_eval(header,self.args[0]))
                        lb = code_eval(header,itp.lb)
                        ub = code_eval(header,itp.ub)
                        code.append('( {} < {} ? {} : {} < {} ? {} : {})'.format(x,lb,lb,ub,x,ub,x))
                        return
                    if itp == 'int':
                        code.append(code_eval(header,self.args[0]))
                        return
                    if itp == 'nat':
                        x = new_temp(header)
                        code_line(header,x + ' = ' + code_eval(header,self.args[0]))
                        code.append('( {} < 0 ? 0 : {})'.format(x,x))
                        return
                    if is_bv_term(self):
                        emit_bv_op(self,header,code)
                        return
            raise iu.IvyError(None,"symbol has no interpretation: {}".format(il.typed_symbol(self.func)))
        if isinstance(itp,il.RangeSort):
            x = new_temp(header)
            code_line(header,x + ' = ' + code_eval(header,self.args[0]) + ' {} '.format(self.func.name) + code_eval(header,self.args[1]))
            lb = code_eval(header,itp.lb)
            ub = code_eval(header,itp.ub)
            code.append('( {} < {} ? {} : {} < {} ? {} : {})'.format(x,lb,lb,ub,x,ub,x))
            return
        assert len(self.args) == 2 # handle only binary ops for now
        code.append('(')
        self.args[0].emit(header,code)
        code.append(' {} '.format(self.func.name))
        self.args[1].emit(header,code)
        code.append(')')
        return 
    global is_derived
    # no way to deal with polymorphic ops if not derived, give up here
    if il.symbol_is_polymorphic(self.func) and self.func not in is_derived:
        raise iu.IvyError(None,"symbol has no interpretation: {}".format(il.typed_symbol(self.func)))
    # handle destructors
    skip_params = 0
    if self.func.name in im.module.destructor_sorts:
        if capture_args != None and isinstance(self.args[0],lg.Apply):
            self.args[0].emit(header,code,capture_args)
        else:
            self.args[0].emit(header,code)
        code.append('.'+memname(self.func))
        skip_params = 1
    # handle uninterpreted ops
    else:
        if self.func in is_derived:
            code.append(delegate_methods_to)
        code.append(funname(self.func.name))
    if self.func in is_derived:
        code.append('(')
        first = True
        for a in self.args:
            if not first:
                code.append(',')
            a.emit(header,code)
            first = False
        code.append(')')
    elif (is_large_destr if skip_params > 0 else is_large_type)(self.rep.sort) and len(self.args[skip_params:]) > 1:
        code.append('[' + ctuple(self.rep.sort.dom[skip_params:],classname=the_classname) + '(')
        first = True
        for a in self.args[skip_params:]:
            if not first:
                code.append(',')
            capture_emit(a,header,code,capture_args)
            first = False
        code.append(')]')
    else: 
        for a in self.args[skip_params:]:
            code.append('[')
            capture_emit(a,header,code,capture_args)
            code.append(']')

lg.Apply.emit = emit_app

class HavocSymbol(object):
    """
    A class representing a Havoc symbol.

    Attributes:
        sort (str): The sort/type of the symbol.
        name (str): The name of the symbol.
        unique_id (int): A unique identifier for the symbol.
        args (list): A list of arguments associated with the symbol.

    Methods:
        __init__(sort, name, unique_id):
            Initializes a new instance of the HavocSymbol class.
        
        clone(args):
            Creates a clone of the current HavocSymbol instance with the given arguments.
    """
    def __init__(self,sort,name,unique_id):
        self.sort,self.name,self.unique_id = sort,name,unique_id
        self.args = []
    def clone(self,args):
        return HavocSymbol(self.sort,self.name,self.unique_id)

def emit_havoc_symbol(self,header,code):
    sym = il.Symbol(new_temp(header,sort=self.sort),self.sort)
    mk_nondet_sym(header,sym,self.name,self.unique_id)
    code.append(sym.name)
    

HavocSymbol.emit = emit_havoc_symbol


temp_ctr = 0

def new_temp(header,sort=None):
    """
    Generates a new temporary variable name and appends its declaration to the header.

    Args:
        header (list): A list of strings representing the header where the variable declaration will be appended.
        sort (optional): The type of the variable. If None, the variable is assumed to be of type 'int'.

    Returns:
        str: The name of the newly generated temporary variable.
    """
    name = new_temp_name()
    if sort is None:
        indent(header)
        header.append(('int' if sort == None else ctype(sort)) + ' ' + name + ';\n')
    else:
        code_line(header,sym_decl(il.Symbol(name,sort)));
    return name

def new_temp_name():
    global temp_ctr
    name = '__tmp' + str(temp_ctr)
    temp_ctr += 1
    return name

def find_definition(sym):
    for ldf in im.module.definitions:
        if ldf.formula.defines() == sym:
            return ldf
    return None

def get_bound_exprs(v0,variables,body,exists,res):
    """
    Recursively collects bound expressions from a given logical formula.

    This function traverses a logical formula represented by `body` and collects
    expressions that are bound by certain logical operators (e.g., Not, Implies, Or, And).
    The collected expressions are appended to the `res` list along with a boolean flag
    indicating the context of their existence.

    Args:
        v0 (Variable): The variable to check for in derived expressions.
        variables (list): A list of variables in the logical formula.
        body (Expression): The logical formula to traverse.
        exists (bool): A flag indicating the current context of existence.
        res (list): A list to store the collected bound expressions and their context.

    Returns:
        None: The function modifies the `res` list in place.
    """
    global is_derived
    if isinstance(body,il.Not):
        return get_bound_exprs(v0,variables,body.args[0],not exists,res)
    if il.is_app(body) and body.rep.name in ['<','<=','>','>=']:
        res.append((body,not exists))
    if isinstance(body,il.Implies) and not exists:
        get_bound_exprs(v0,variables,body.args[0],not exists,res)
        get_bound_exprs(v0,variables,body.args[1],exists,res)
        return
    if isinstance(body,il.Or) and not exists:
        for arg in body.args:
            get_bound_exprs(v0,variables,arg,exists,res)
        return
    if isinstance(body,il.And) and exists:
        for arg in body.args:
            get_bound_exprs(v0,variables,arg,exists,res)
        return
    if il.is_app(body) and body.rep in is_derived and v0 in body.args:
        ldf = find_definition(body.rep)
        if ldf is None:  # happens for native definitions
            return
        if all(il.is_variable(v) for v in ldf.formula.args[0].args):
            subst = dict((v.name,a) for v,a in zip(ldf.formula.args[0].args,body.args))
            thing = ilu.substitute_ast(ldf.formula.args[1],subst)
            get_bound_exprs(v0,variables,thing,exists,res)
    
def sort_has_negative_values(sort):
    return sort.name in il.sig.interp and il.sig.interp[sort.name] == 'int'

class BoundsError(object):
    def __init__(self,ast,msg):
        self.ast = ast
        self.msg = msg
    def throw(self):
        raise iu.IvyError(self.ast,self.msg)
        
def get_bounds(header,v0,variables,body,exists,varname=None):
    """
    Compute the lower and upper bounds for a given variable within a specified context.

    Args:
        header (str): The header information used for code evaluation.
        v0 (Variable): The variable for which bounds are being determined.
        variables (list): A list of variables present in the context.
        body (Expression): The body of the expression where the variable is used.
        exists (bool): A flag indicating the existence of certain conditions.
        varname (str, optional): The name of the variable. Defaults to None.

    Returns:
        tuple: A tuple containing the lower bound and upper bound as strings.

    Raises:
        BoundsError: If a lower or upper bound cannot be determined.
    """
    bes = []
    get_bound_exprs(v0,variables,body,exists,bes)
    los = []
    his = []
    for be in bes:
        expr,neg = be
        op = expr.rep.name
        strict = op in ['<','>']
        args = expr.args if op in ['<','<='] else [expr.args[1],expr.args[0]]
        if neg:
            strict = not strict
            args = [args[1],args[0]]
        if args[0] == v0 and args[1] != v0 and args[1] not in variables:
            e = code_eval(header,args[1])
            his.append('('+e+')+1' if not strict else e)
        if args[1] == v0 and args[0] != v0 and args[0] not in variables:
            e = code_eval(header,args[0])
            los.append('('+e+')+1' if strict else e)
    if not sort_has_negative_values(v0.sort):
        los.append("0")
    if sort_card(v0.sort) != None:
        his.append(csortcard(v0.sort))
    varname = varname if varname != None else v0
    itp = il.sig.interp.get(v0.sort.name,None)
    if isinstance(itp,il.RangeSort):
        los.append(code_eval(header,itp.lb))
        his.append(code_eval(header,itp.ub)+'+1')
    if not los:
        return BoundsError(None,'cannot find a lower bound for {}'.format(varname))
    if not his:
        if il.is_uninterpreted_sort(v0.sort) and iu.compose_names(v0.sort.name,'cardinality') in im.module.attributes:
            his.append(other_varname(iu.compose_names(v0.sort.name,im.module.attributes[iu.compose_names(v0.sort.name,'cardinality')].rep)))
        else:
            return BoundsError(None,'cannot find an upper bound for {}'.format(varname))
    return los[0],his[0]

def get_all_bounds(header, variables, body, exists, varnames):
    """
    Recursively computes bounds for a list of variables.

    Args:
        header (str): The header information required for computing bounds.
        variables (list): A list of variables for which bounds need to be computed.
        body (str): The body of the expression or function where the variables are used.
        exists (bool): A flag indicating whether the variables exist in the given context.
        varnames (list): A list of variable names corresponding to the variables.

    Returns:
        list: A list of computed bounds for the given variables.

    Raises:
        BoundsError: If there is an error in computing bounds for any variable.
    """
#    get_bound_exprs(v0,variables,body,exists,bes)
    if not variables:
        return []
    v0 = variables[0]
    variables = variables[1:]
    varname = varnames[0]
    varnames = varnames[1:]
    b = get_bounds(header,v0,variables,body,exists,varname=varname)
    if isinstance(b,BoundsError):
        b.throw()
    return [b] + get_all_bounds(header,variables,body,exists,varnames)

def get_extensional_bound_exprs(v0, body, exists, res):
    """
    Recursively collects extensional bound expressions from a given logical body.

    Args:
        v0 (Variable): The variable to check within the body.
        body (Expression): The logical expression to analyze.
        exists (bool): A flag indicating whether the variable should exist in the expression.
        res (list): A list to store the resulting expressions that meet the criteria.

    Returns:
        None: The function modifies the `res` list in place.
    """
    global is_derived
    if isinstance(body,il.Not):
        return get_extensional_bound_exprs(v0,body.args[0],not exists,res)
    if il.is_app(body) and body.rep in the_extensional_relations:
        if v0 in body.args and exists:
            res.append(body)
    if isinstance(body,il.Implies) and not exists:
        get_extensional_bound_exprs(v0,body.args[0],not exists,res)
        get_extensional_bound_exprs(v0,body.args[1],exists,res)
        return
    if isinstance(body,il.Or) and not exists:
        for arg in body.args:
            get_extensional_bound_exprs(v0,arg,exists,res)
        return
    if isinstance(body,il.And) and exists:
        for arg in body.args:
            get_extensional_bound_exprs(v0,arg,exists,res)
        return
    if il.is_app(body) and body.rep in is_derived and v0 in body.args:
        ldf = find_definition(body.rep)
        if ldf is None:  # happens for native definitions
            return
        if all(il.is_variable(v) for v in ldf.formula.args[0].args):
            subst = dict((v.name,a) for v,a in zip(ldf.formula.args[0].args,body.args))
            thing = ilu.substitute_ast(ldf.formula.args[1],subst)
            get_extensional_bound_exprs(v0,thing,exists,res)


def emit_quant(variables, body, header, code, exists=False):
    """
    Emit C++ code for a quantified expression.

    This function generates C++ code for a quantified expression, either existential or universal,
    based on the provided variables and body. The generated code is appended to the `header` and `code` lists.

    Args:
        variables (list): A list of variables involved in the quantification.
        body (object): The body of the quantified expression.
        header (list): A list to which the generated C++ code header will be appended.
        code (list): A list to which the generated C++ code will be appended.
        exists (bool, optional): If True, generates code for an existential quantifier. If False, generates code for a universal quantifier. Defaults to False.

    Raises:
        IvyError: If a type is not a variant type but is used as the first argument of `*>`.
        IvyError: If a sort has an iterable attribute but no iterator.
        BoundsError: If the bounds for iteration cannot be determined.

    Returns:
        None
    """
    global indent_level
    if len(variables) == 0:
        body.emit(header,code)
        return

    if (exists and len(variables) == 1 and il.is_app(body)
        and body.func.name == '*>' and body.args[1] == variables[0]):
        vsort = body.args[0].sort
        vsortname = vsort.name
        if vsortname not in im.module.variants:
            raise iu.IvyError(None,'type {} is not a variant type but used as first argument of *>'.format(vsortname))
        variants = im.module.variants[vsortname]
        rsort = variables[0].sort
        for idx, sort in enumerate(variants):
            if sort == rsort:
                cpptype = sort_to_cpptype[vsort]
                lhs = code_eval(header,body.args[0])
                isa = cpptype.isa(idx,lhs)
                code.append(isa)
                return
        raise iu.IvyError(None,'type {} is not a variant of type {}'.format(vsortname,rsort))

    v0 = variables[0]
    variables = variables[1:]
    has_iter = il.is_uninterpreted_sort(v0.sort) and iu.compose_names(v0.sort.name,'iterable') in im.module.attributes
    if has_iter:
        iter = iu.compose_names(v0.sort.name,'iter')
    res = new_temp(header)
    idx = v0.name
    indent(header)
    header.append(res + ' = ' + str(0 if exists else 1) + ';\n')
    indent(header)
    if has_iter:
        iter_sort_name = iter
        if iter_sort_name not in il.sig.sorts:
            iter_sort_name = iu.compose_names(iter,'t')
        if iter_sort_name not in il.sig.sorts:
            print(iter_sort_name)
            raise iu.IvyError(None,'sort {} has iterable attribute but no iterator'.format(v0.sort))
        iter_sort = il.sig.sorts[iter_sort_name]
        zero = []
        emit_constant(il.Symbol('0',v0.sort),header,zero)
        header.append('for (' + ctypefull(iter_sort) + ' ' + idx + ' = '
                          + varname(iu.compose_names(iter,'create') + '('))
        header.extend(zero)
        header.append('); !' + varname(iu.compose_names(iter,'is_end')) + '(' + idx + ');' 
                       + idx + '=' + varname(iu.compose_names(iter,'next')) + '(' + idx + ')) {\n')
    else:
        
        berr = get_bounds(header,v0,variables,body,exists)
        if not isinstance(berr,BoundsError) and is_any_integer_type(v0.sort):
            lo,hi = berr
            ct = ctype(v0.sort)
            ct = 'int' if ct == 'bool' else ct if ct in int_ctypes else 'int'
            header.append('for (' + ct + ' ' + idx + ' = ' + lo + '; ' + idx + ' < ' + hi + '; ' + idx + '++) {\n')
        else:
            ebnds = []
            get_extensional_bound_exprs(v0,body,exists,ebnds)
            if not ebnds:
                if not isinstance(berr,BoundsError):
                    berr = BoundsError(None,"cannot iterate over sort {}".format(v0.sort))
                berr.throw()
            ebnd = ebnds[0]
            header.append('for(auto it={}.memo.begin(),en={}.memo.end(); it != en; ++it)if (it->second) {{ \n'.format(varname(ebnd.rep),varname(ebnd.rep)))
            for pos,v in enumerate(ebnd.args):
                if v == v0 or v in variables:
                    ct = ctype(v.sort)
                    ct = 'auto'
                    if len(ebnd.args) > 1:
                        header.append('    ' + ct + ' ' + v.name + ' = it->first.arg' + str(pos) + ';\n')
                    else:
                        header.append('    ' + ct + ' ' + v.name + ' = it->first;\n')
            variables = [v for v in variables if v not in ebnd.args]

    indent_level += 1
    subcode = []
    emit_quant(variables,body,header,subcode,exists)
    indent(header)
    header.append('if (' + ('!' if not exists else ''))
    header.extend(subcode)
    header.append(') '+ res + ' = ' + str(1 if exists else 0) + ';\n')
    indent_level -= 1
    indent(header)
    header.append('}\n')
    code.append(res)    


lg.ForAll.emit = lambda self,header,code: emit_quant(list(self.variables),self.body,header,code,False)
lg.Exists.emit = lambda self,header,code: emit_quant(list(self.variables),self.body,header,code,True)

def code_line(impl,line):
    indent(impl)
    impl.append(line+';\n')

def code_asgn(impl,lhs,rhs):
    code_line(impl,lhs + ' = ' + rhs)

def code_decl(impl,sort,name):
    code_line(impl,ctype(sort) + ' ' + name)

def code_eval(impl,expr):
    code = []
    expr.emit(impl,code)
    return ''.join(code)

def emit_some(self, header, code):
    """
    Emit code for handling the 'Some' and 'SomeMinMax' constructs in Ivy.

    This function generates C++ code for the Ivy constructs 'Some' and 'SomeMinMax'.
    It handles the translation of these constructs into appropriate C++ code, including
    variable declarations, loops, conditionals, and assignments.

    Parameters:
    self (ivy_ast.Some or ivy_ast.SomeMinMax): The Ivy AST node representing the 'Some' or 'SomeMinMax' construct.
    header (list): A list to which the generated C++ header code will be appended.
    code (list): A list to which the generated C++ code will be appended.

    Returns:
    None
    """
    if isinstance(self,ivy_ast.Some):
        fmla = self.fmla()
        if len(self.params()) == 1 and il.is_app(fmla) and fmla.func.name == '*>' and fmla.args[1] == self.params()[0]:
            if fmla.args[0].sort.name in im.module.variants:
                cpptype = sort_to_cpptype[fmla.args[0].sort]
                for idx,sort in enumerate(im.module.variants[fmla.args[0].sort.name]):
                    if sort == fmla.args[1].sort:
                        lhs = code_eval(header,fmla.args[0])
                        isa = cpptype.isa(idx,lhs)
                        code_line(header,'if ({}) {} = {}'.format(isa,varname(fmla.args[1].name),cpptype.downcast(idx,lhs)))
                        code.append(isa)
                        return
                code.append('false')
                return
            
        vs = [il.Variable('X__'+str(idx),p.sort) for idx,p in enumerate(self.params())]
        subst = dict(list(zip(self.params(),vs)))
        fmla = ilu.substitute_constants_ast(self.fmla(),subst)
        params = self.params()
    else:
        vs = self.params()
        params = [new_temp(header)]
        code_line(header,params[0] + ' = ___ivy_choose(' + csortcard(vs[0].sort) + ',"' + str(vs[0]) + '",0)')
        fmla = self.fmla()
    for v in vs:
        check_iterable_sort(v.sort)
    some = new_temp(header)
    code_asgn(header,some,'0')
    if isinstance(self,ivy_ast.SomeMinMax):
        minmax = new_temp(header)
    open_loop(header,vs,bounds=get_all_bounds(header,vs,fmla,True,self.params()))
    open_if(header,code_eval(header,fmla))
    if isinstance(self,ivy_ast.SomeMinMax):
        index = new_temp(header)
        idxfmla =  ilu.substitute_constants_ast(self.index(),subst)
        code_asgn(header,index,code_eval(header,idxfmla))
        open_if(header,some)
        sort = self.index().sort
        op = il.Symbol('<',il.RelationSort([sort,sort]))
        idx = il.Symbol(index,sort)
        mm = il.Symbol(minmax,sort)
        pred = op(idx,mm) if isinstance(self,ivy_ast.SomeMin) else op(mm,idx)
        open_if(header,code_eval(header,il.Not(pred)))
        code_line(header,'continue')
        close_scope(header)
        close_scope(header)
        code_asgn(header,minmax,index)
    for p,v in zip(params,vs):
        code_asgn(header,varname(p),varname(v))
    code_line(header,some+'= 1')
    # optimization: if minimizing first params, first hit is minimum, so exit loop
    # this is particularly helpful when searching a big type like int!
    if isinstance(self,ivy_ast.SomeMinMax) and self.params()[0] == self.index():
        code_line(header,'break')
    close_scope(header)
    close_loop(header,vs)
    if isinstance(self,ivy_ast.Some):
        code.append(some)
       
    else:
        iv = self.if_value()
        if iv == None:
            code.append(varname(params[0]))
        else:
            thing = il.Symbol(params[0],vs[0].sort)
            ot = ilu.substitute_ast(iv,{vs[0].name:thing})
            code.append('(' + some + ' ? (' + code_eval(header,ot) + ') : ('
                        + code_eval(header,self.else_value()) + '))')
            

ivy_ast.Some.emit = emit_some

il.Some.emit = emit_some

def emit_unop(self, header, code, op):
    """
    Appends a unary operation to the code list and emits the argument.

    Args:
        header: The header information (not used in this function).
        code (list): The list to which the operation and its argument will be appended.
        op (str): The unary operation to be appended to the code list.

    Returns:
        None
    """
    code.append(op)
    self.args[0].emit(header,code)

lg.Not.emit = lambda self,header,code: emit_unop(self,header,code,'!')

def emit_binop(self, header, code, op, ident=None):
    """
    Emits a binary operation in the form of a string representation.

    Parameters:
    - header: A header object that may be used by the emit method of the arguments.
    - code: A list of strings where the emitted code will be appended.
    - op: A string representing the binary operator.
    - ident: An optional identifier to be used when there are no arguments.

    Behavior:
    - If there are no arguments (`self.args` is empty), the method asserts that `ident` is not None and appends `ident` to `code`.
    - If there are arguments, it emits the first argument, then iterates over the remaining arguments, appending the operator and emitting each argument.
    - The emitted binary operation is enclosed in parentheses.
    """
    if len(self.args) == 0:
        assert ident != None
        code.append(ident)
        return
    code.append('(')
    self.args[0].emit(header,code)
    for a in self.args[1:]:
        code.append(' ' + op + ' ')
        a.emit(header,code)
    code.append(')')
    
def emit_implies(self, header, code):
    """
    Appends a logical implication to the provided code list.

    This method generates a logical implication expression in C++ code
    and appends it to the `code` list. The implication is represented
    as `(!A || B)` where `A` and `B` are the first and second arguments
    of the current object, respectively.

    Args:
        header: Unused parameter, kept for consistency with other emit methods.
        code (list): The list to which the generated code will be appended.

    Returns:
        None
    """
    code.append('(')
    code.append('!')
    self.args[0].emit(header,code)
    code.append(' || ')
    self.args[1].emit(header,code)
    code.append(')')
    

lg.Eq.emit = lambda self,header,code: emit_binop(self,header,code,'==')
lg.Iff.emit = lambda self,header,code: emit_binop(self,header,code,'==')
lg.Implies.emit = emit_implies
lg.And.emit = lambda self,header,code: emit_binop(self,header,code,'&&','true')
lg.Or.emit = lambda self,header,code: emit_binop(self,header,code,'||','false')

def emit_ternop(self, header, code):
    """
    Emits a ternary operation in C++ code.

    This method appends a ternary operation to the provided code list. 
    The ternary operation is constructed using the `self.args` list, 
    where `self.args[0]` is the condition, `self.args[1]` is the 
    expression if the condition is true, and `self.args[2]` is the 
    expression if the condition is false.

    Args:
        header: A header object that may be used by the emit method of 
                the arguments.
        code (list): A list of strings representing the code being 
                        generated. The ternary operation will be appended 
                        to this list.
    """
    code.append('(')
    self.args[0].emit(header,code)
    code.append(' ? ')
    self.args[1].emit(header,code)
    code.append(' : ')
    self.args[2].emit(header,code)
    code.append(')')
    
lg.Ite.emit = emit_ternop

def emit_traced_lhs(self, trace, captured_args):
    """
    Appends a string representation of the left-hand side (LHS) of an expression to the trace list.

    This method constructs a string representation of the LHS of an expression, including its arguments,
    and appends it to the provided trace list. If the expression is a constant, it simply appends the
    representation of the constant. If the expression has arguments, it appends the arguments in a
    comma-separated format within parentheses.

    Args:
        trace (list): A list to which the string representation of the LHS will be appended.
        captured_args (list): A list of arguments that have been captured so far. This list may be modified
                                and returned with any additional captured arguments.

    Returns:
        list: The list of captured arguments, potentially modified to exclude those that have been processed.
    """
    trace.append('<< "{}"'.format(self.rep))
    if il.is_constant(self):
        return
    if self.args:
        trace.append(' << "("')
    num_args = len(self.args)
    if self.func.name in im.module.destructor_sorts:
        captured_args = emit_traced_lhs(self.args[0],trace,captured_args)
        if num_args > 1:
            trace.append(' << ","')
        num_args -= 1
    if captured_args is None:
        captured_args = []
    trace.append(' << ","'.join(' << ' + a for a in captured_args[:num_args]))
    if self.args:
        trace.append(' << ")"')
    return captured_args[num_args:]

def emit_assign_simple(self, header):
    """
    Generates C++ code for a simple assignment operation.

    This function constructs the C++ code for an assignment operation, 
    potentially including tracing information if the `opt_trace` option is enabled.
    
    Args:
        self: The instance of the class containing this method.
        header (list): A list to which the generated C++ code will be appended.
    
    The function performs the following steps:
    1. Initializes a list `code` to store the generated code.
    2. Adds indentation to the `code` list.
    3. If tracing is enabled and the left-hand side (LHS) of the assignment does not contain a colon:
        - Initializes a list `trace` to store tracing information.
        - Adds indentation to the `trace` list.
        - Appends tracing information to `trace`.
        - Determines if the LHS is a constant and emits the appropriate code.
        - Appends the assignment operator (`=`) to `code`.
        - Emits the right-hand side (RHS) of the assignment and appends it to `code`.
        - Extends `trace` with the RHS information and appends it to `header`.
    4. If tracing is not enabled or the LHS contains a colon:
        - Emits the LHS and appends it to `code`.
        - Appends the assignment operator (`=`) to `code`.
        - Determines the sorts of the LHS and RHS.
        - If the sorts are variants, appends the upcasted RHS to `code`.
        - Otherwise, emits the RHS and appends it to `code`.
    5. Appends a semicolon (`;`) to `code`.
    6. Extends `header` with the contents of `code`.
    """
    code = []
    indent(code)
    if opt_trace.get() and ':' not in self.args[0].rep.name:
        trace = []
        indent(trace)
        trace.append('__ivy_out ' + number_format + ' << "  write("')
        cargs = []
        if il.is_constant(self.args[0]):
            self.args[0].emit(header,code)
        else:
            emit_app(self.args[0],header,code,cargs)
        emit_traced_lhs(self.args[0],trace,cargs)
        code.append(' = ')
        rhs = []
        self.args[1].emit(header,rhs)
        code.extend(rhs)
        trace.extend(' << "," << (' + ''.join(rhs) + ') << ")" << std::endl;\n')
        header.extend(trace)
    else:
        self.args[0].emit(header,code)
        code.append(' = ')
        lsort,rsort = [a.sort for a in self.args]
        if im.module.is_variant(lsort,rsort):
            code.append(sort_to_cpptype[lsort].upcast(im.module.variant_index(lsort,rsort),code_eval(header,self.args[1])))
        else:
            self.args[1].emit(header,code)
    code.append(';\n')    
    header.extend(code)

def emit_assign_large(self, header):
    """
    Generates and emits a large assignment statement in C++ code.

    This method constructs a C++ assignment statement for a given expression,
    handling cases where the expression involves variables and conditional logic.
    It uses intermediate variables and constructs a conditional expression if necessary.

    Args:
        self: The instance of the class containing this method.
        header (str): The header string to be used in the generated C++ code.

    Returns:
        None
    """
    dom = self.args[0].rep.sort.dom
    vs = variables(dom)
    vs = [x if isinstance(x,il.Variable) else y for x,y in zip(self.args[0].args,vs)]
    eqs = [il.Equals(x,y) for x,y in zip(self.args[0].args,vs) if not isinstance(x,il.Variable)]
    expr = il.Ite(il.And(*eqs),self.args[1],self.args[0].rep(*vs)) if eqs else self.args[1]
    global thunks

    code_line(header,varname(self.args[0].rep)+' = ' + make_thunk(thunks,vs,expr))


def open_bounded_loops(variables, body, exists=True):
    """
    Generates C++ loop headers for iterating over bounded variables.

    This function takes a list of variables and a body of code, and generates
    C++ loop headers to iterate over these variables within the given bounds.
    If the variable is of an integer type, it generates a standard for-loop.
    If the variable is not of an integer type, it generates a loop to iterate
    over extensional bounds.

    Args:
        variables (list): A list of variables to iterate over.
        body (str): The body of code where the variables are used.
        exists (bool, optional): A flag indicating if the variables exist. Defaults to True.

    Returns:
        list: A list of strings representing the C++ loop headers.

    Raises:
        BoundsError: If bounds cannot be determined for a variable.
    """
    header = []
    while variables:
        v0 = variables[0]
        idx = v0.name
        variables = variables[1:]
        berr = get_bounds(header,v0,variables,body,exists)
        if not isinstance(berr,BoundsError) and is_any_integer_type(v0.sort):
            lo,hi = berr
            ct = ctype(v0.sort)
            ct = 'int' if ct == 'bool' else ct if ct in int_ctypes else 'int'
            header.append('for (' + ct + ' ' + idx + ' = ' + lo + '; ' + idx + ' < ' + hi + '; ' + idx + '++) {\n')
        else:
            ebnds = []
            get_extensional_bound_exprs(v0,body,exists,ebnds)
            if not ebnds:
                if not isinstance(berr,BoundsError):
                    berr = BoundsError(None,"cannot iterate over sort {}".format(v0.sort))
                return berr
            ebnd = ebnds[0]
            header.append('for(auto it={}.memo.begin(),en={}.memo.end(); it != en; ++it)if (it->second) {{\n'.format(varname(ebnd.rep),varname(ebnd.rep)))
            for pos,v in enumerate(ebnd.args):
                if v == v0 or v in variables:
                    ct = ctype(v.sort)
                    ct = 'auto'
                    if len(ebnd.args) > 1:
                        header.append('    ' + ct + ' ' + v.name + ' = it->first.arg' + str(pos) + ';\n')
                    else:
                        header.append('    ' + ct + ' ' + v.name + ' = it->first;\n')
            variables = [v for v in variables if v not in ebnd.args]
    return header

def close_bounded_loops(header,loops):
    for i in loops:
        if i.endswith('{\n'):
            header.append('}\n')


def emit_assign(self, header):
    """
    Emits the C++ code for an assignment operation in the context of the Ivy language.

    This function handles different cases of assignment based on the types and 
    properties of the left-hand side (LHS) and right-hand side (RHS) expressions. 
    It generates the appropriate C++ code and appends it to the provided header list.

    Args:
        header (list): A list of strings representing the lines of C++ code to be 
                        generated. The generated code for the assignment will be 
                        appended to this list.

    Notes:
        - If the LHS has no free variables, a simple assignment is emitted.
        - If the RHS is a conditional expression (ite) and the LHS matches the 
            false branch of the conditional, special handling is applied.
        - If the assignment involves bounded loops, these loops are opened and 
            closed appropriately in the generated code.
        - Temporary symbols and variables are used to handle complex assignments 
            involving multiple variables and types.
    """
    global indent_level
    with ivy_ast.ASTContext(self):
#        if is_large_type(self.args[0].rep.sort) and lu.free_variables(self.args[0]):
#        if is_large_lhs(self.args[0]):
#            
#            emit_assign_large(self,header)
#            return
        vs = list(lu.free_variables(self.args[0]))
#        for v in vs:
#            check_iterable_sort(v.sort)
        if len(vs) == 0:
            emit_assign_simple(self,header)
            return
        bexpr = il.And()
        if il.is_ite(self.args[1]) and self.args[0] == self.args[1].args[2]:
            if self.modifies()[0] not in ilu.symbols_ast(self.args[1].args[0]):
                bexpr = self.args[1].args[0]
        loops = open_bounded_loops(vs,bexpr)
        if isinstance(loops,BoundsError):
            emit_assign_large(self,header)
            return
        sort = self.args[1].sort
        tsort = il.FunctionSort(*([v.sort for v in vs] + [sort]))
        sym = il.Symbol(new_temp(header,sort=tsort),tsort)
        lhs = sym(*vs) if vs else sym
        header.extend(loops)
#        global temp_ctr
#        tmp = '__tmp' + str(temp_ctr)
#        temp_ctr += 1
#        indent(header)
#        header.append(ctype(self.args[1].sort) + '  ' + tmp)
#        for v in vs:
#            header.append('[' + str(sort_card(v.sort)) + ']')
#        header.append(';\n')
#        for idx in vs:
#            indent(header)
#            vn = varname(idx.name)
#            lb,ub = sort_bounds(dsort)
#            #        dcard = sort_card(dsort)
#            header.append('for (int ' + vn + ' = ' + lb + '; ' + vn + ' < ' + ub + '; ' + vn + '++) {\n')
#            indent_level += 1
        code = []
        indent(code)
        lhs.emit(header,code)
        # code.append(tmp + ''.join('['+varname(v.name)+']' for v in vs) + ' = ')
        code.append(' = ');
        self.args[1].emit(header,code)
        code.append(';\n')    
        header.extend(code)
        close_bounded_loops(header,loops)
#        for idx in vs:
#            indent_level -= 1
#            indent(header)
#            header.append('}\n')
        header.extend(loops)
        code = []
        indent(code)
        self.args[0].emit(header,code)
        code.append(' = ' + code_eval(header,lhs) + ';\n')
        header.extend(code)
        close_bounded_loops(header,loops)
    
ia.AssignAction.emit = emit_assign

def emit_havoc(self,header):
    print(self)
    print(self.lineno)
    assert False

ia.HavocAction.emit = emit_havoc

def emit_sequence(self,header):
    """
    Emits a sequence of code into the provided header list.

    This function appends a sequence of code to the `header` list, 
    starting with an indented opening brace '{', followed by the 
    emitted code for each argument in `self.args`, and ending with 
    an indented closing brace '}'.

    Args:
        header (list): A list of strings representing the lines of code 
                        to which the sequence will be appended.

    Modifies:
        The `header` list by appending the emitted sequence of code.
    """
    global indent_level
    indent(header)
    header.append('{\n')
    indent_level += 1
    for a in self.args:
        a.emit(header)
    indent_level -= 1 
    indent(header)
    header.append('}\n')

ia.Sequence.emit = emit_sequence

def emit_assert(self,header):
    """
    Generates and appends an assertion statement to the provided header list.

    This method constructs an assertion statement using the formula associated
    with the current instance. It formats the assertion with the appropriate
    line number and appends it to the header list.

    Args:
        self: The instance of the class containing the formula to be asserted.
        header (list): The list to which the generated assertion code will be appended.

    Returns:
        None
    """
    code = []
    indent(code)
    code.append('ivy_assert(')
    with ivy_ast.ASTContext(self):
        il.close_formula(self.formula).emit(header,code)
    code.append(', "{}");\n'.format(iu.lineno_str(self).replace('\\','\\\\')))
    header.extend(code)

ia.AssertAction.emit = emit_assert

def emit_assume(self, header):
    """
    Emits an assumption statement in C++ code.

    This function generates a C++ assumption statement using the provided
    formula and appends it to the given header list. The assumption is
    formatted as `ivy_assume(formula, "line_number");`.

    Args:
        self: The instance of the class containing the formula to be emitted.
        header (list): A list of strings representing the lines of the header
                        where the assumption statement will be appended.

    Returns:
        None
    """
    code = []
    indent(code)
    code.append('ivy_assume(')
    with ivy_ast.ASTContext(self):
        il.close_formula(self.formula).emit(header,code)
    code.append(', "{}");\n'.format(iu.lineno_str(self).replace('\\','\\\\')))
    header.extend(code)

ia.AssumeAction.emit = emit_assume


# def emit_call(self,header,ignore_vars=False):
#     # tricky: a call can have variables on the lhs. we lower this to
#     # a call with temporary return actual followed by assignment
#     # tricker: in a parameterized initializer, the rhs may also have variables.
#     with ivy_ast.ASTContext(self):
#     # we iterate over these.
#         if not ignore_vars and len(self.args) == 2 and list(ilu.variables_ast(self.args[1])):
#             vs = list(iu.unique(ilu.variables_ast(self.args[0])))
#             sort = self.args[1].sort
#             if vs:
#                 sort = il.FunctionSort(*([v.sort for v in vs] + [sort]))
#             sym = il.Symbol(new_temp(header,sort=sort),sort)
#             lhs = sym(*vs) if vs else sym
#             open_loop(header,vs)
#             emit_call(self.clone([self.args[0],lhs]),header,ignore_vars=True)
#             close_loop(header,vs)
#             ac = ia.AssignAction(self.args[1],lhs)
#             if hasattr(self,'lineno'):
#                 ac.lineno = self.lineno
#             emit_assign(ac,header)
#             return
#         if target.get() in ["gen","test"]:
#             indent(header)
#             header.append('___ivy_stack.push_back(' + str(self.unique_id) + ');\n')
#         code = []
#         indent(code)
#         retvals = []
#         args = list(self.args[0].args)
#         nargs = len(args)
#         name = self.args[0].rep
#         action = im.module.actions[name]
#         fmls = list(action.formal_params)
#         if len(self.args) >= 2:
#             pt,rt = get_param_types(name,action)
#             for rpos in range(len(rt)):
#                 rv = self.args[1 + rpos]
#                 pos = rt[rpos].pos if isinstance(rt[rpos],ReturnRefType) else None
#                 if pos is not None:
#                     if pos < nargs:
#                         iparg = self.args[0].args[pos]
#                         if (iparg != rv or
#                             any(j != pos and may_alias(arg,iparg) for j,arg in enumerate(self.args[0].args))):
#                             retval = new_temp(header,rv.sort)
#                             code.append(retval + ' = ')
#                             self.args[0].args[pos].emit(header,code)
#                             code.append('; ')
#                             retvals.append((rv,retval))
#                             args = [il.Symbol(retval,self.args[1].sort) if idx == pos else a for idx,a in enumerate(args)]
#                     else:
#                         args.append(self.args[1+rpos])
#                         fmls.append(rv)
#             if not isinstance(rt[0],ReturnRefType):
#                 self.args[1].emit(header,code)
#                 code.append(' = ')
#         code.append(varname(str(self.args[0].rep)) + '(')
#         first = True
#         for p,fml in zip(args,fmls):
#             if not first:
#                 code.append(', ')
#             lsort,rsort = fml.sort,p.sort
#             if im.module.is_variant(lsort,rsort):
#                 code.append(sort_to_cpptype[lsort].upcast(im.module.variant_index(lsort,rsort),code_eval(header,p)))
#             else:
#                 p.emit(header,code)
#             first = False
#         code.append(');\n')    
#         for (rv,retval) in retvals:
#             indent(code) 
#             rv.emit(header,code)
#             code.append(' = ' + retval + ';\n')
#         header.extend(code)
#         if target.get() in ["gen","test"]:
#             indent(header)
#             header.append('___ivy_stack.pop_back();\n')

def emit_call(self, header):
    """
    Emit the code for a function call, handling special cases where the call 
    involves variables on the left-hand side (lhs) and generating appropriate 
    temporary variables and assignments.

    Args:
        self: The instance of the class containing the function call information.
        header (list): The list to which the generated code lines will be appended.

    Special Cases:
        - If the call has variables on the lhs, it lowers this to a call with 
            temporary return actual followed by assignment.
        - If the target is "gen" or "test", it manages the stack by pushing and 
            popping the unique ID of the call.

    Code Generation:
        - Generates code for the function call, including handling of return 
            values and parameter types.
        - Manages temporary variables and assignments for return values.
        - Emits the final function call code and appends it to the header.

    Note:
        - This function assumes the presence of several helper functions and 
            classes such as `ilu.variables_ast`, `il.Symbol`, `ia.AssignAction`, 
            `emit_assign`, `indent`, `get_param_types`, `ReturnRefType`, 
            `may_alias`, `new_temp`, `varname`, `sort_to_cpptype`, and `code_eval`.
    """
    # tricky: a call can have variables on the lhs. we lower this to
    # a call with temporary return actual followed by assignment 
    if len(self.args) == 2 and list(ilu.variables_ast(self.args[1])):
        sort = self.args[1].sort
        sym = il.Symbol(new_temp(header,sort=sort),sort)
        emit_call(self.clone([self.args[0],sym]),header)
        ac = ia.AssignAction(self.args[1],sym)
        if hasattr(self,'lineno'):
            ac.lineno = self.lineno
        emit_assign(ac,header)
        return
    if target.get() in ["gen","test"]:
        indent(header)
        header.append('___ivy_stack.push_back(' + str(self.unique_id) + ');\n')
    code = []
    indent(code)
    retvals = []
    args = list(self.args[0].args)
    nargs = len(args)
    name = self.args[0].rep
    action = im.module.actions[name]
    fmls = list(action.formal_params)
    if len(self.args) >= 2:
        pt,rt = get_param_types(name,action)
        for rpos in range(len(rt)):
            rv = self.args[1 + rpos]
            pos = rt[rpos].pos if isinstance(rt[rpos],ReturnRefType) else None
            if pos is not None:
                if pos < nargs:
                    iparg = self.args[0].args[pos]
                    if (iparg != rv or
                        any(j != pos and may_alias(arg,iparg) for j,arg in enumerate(self.args[0].args))):
                        retval = new_temp(header,rv.sort)
                        code.append(retval + ' = ')
                        self.args[0].args[pos].emit(header,code)
                        code.append('; ')
                        retvals.append((rv,retval))
                        args = [il.Symbol(retval,self.args[1].sort) if idx == pos else a for idx,a in enumerate(args)]
                else:
                    args.append(self.args[1+rpos])
                    fmls.append(rv)
        if not isinstance(rt[0],ReturnRefType):
            self.args[1].emit(header,code)
            code.append(' = ')
    code.append(varname(str(self.args[0].rep)) + '(')
    first = True
    for p,fml in zip(args,fmls):
        if not first:
            code.append(', ')
        lsort,rsort = fml.sort,p.sort
        if im.module.is_variant(lsort,rsort):
            code.append(sort_to_cpptype[lsort].upcast(im.module.variant_index(lsort,rsort),code_eval(header,p)))
        else:
            p.emit(header,code)
        first = False
    code.append(');\n')    
    for (rv,retval) in retvals:
        indent(code) 
        rv.emit(header,code)
        code.append(' = ' + retval + ';\n')
    header.extend(code)
    if target.get() in ["gen","test"]:
        indent(header)
        header.append('___ivy_stack.pop_back();\n')

ia.CallAction.emit = emit_call

def emit_crash(self,header):
    pass

ia.CrashAction.emit = emit_crash

def local_start(header, params, nondet_id=None):
    """
    Generates the initial part of a C++ function definition, including the function header and 
    declarations for the parameters. Optionally, it can generate non-deterministic symbols for 
    the parameters.

    Args:
        header (list): A list of strings representing the lines of the C++ function being generated.
        params (list): A list of parameter objects, each containing a 'sort' and 'name' attribute.
        nondet_id (optional): An identifier for generating non-deterministic symbols. If None, 
                                non-deterministic symbols are not generated.

    Returns:
        None
    """
    global indent_level
    indent(header)
    header.append('{\n')
    indent_level += 1
    for p in params:
        indent(header)
        code_line(header,sym_decl(p))
#        header.append(ctype(p.sort) + ' ' + varname(p.name) + ';\n')
        if nondet_id != None:
            mk_nondet_sym(header,p,p.name,nondet_id)

def local_end(header):
    """
    Decreases the global indentation level, appends the closing brace '}' 
    followed by a newline to the given header, and adjusts the indentation 
    accordingly.

    Args:
        header (list): A list of strings representing the lines of code 
                       to which the closing brace and newline will be appended.
    """
    global indent_level
    indent_level -= 1
    indent(header)
    header.append('}\n')


def emit_local(self, header):
    """
    Emits local variables and statements to the provided header.

    This function generates code for local variables and statements by calling
    `local_start`, emitting the arguments, and then calling `local_end`.

    Args:
        header: The header to which the local variables and statements are emitted.
    """
    local_start(header,self.args[0:-1],self.unique_id)
    self.args[-1].emit(header)
    local_end(header)

ia.LocalAction.emit = emit_local

def emit_if(self, header):
    """
    Generates C++ code for an if-else statement based on the provided AST nodes.

    Args:
        header (list): A list of strings representing the lines of code generated so far.

    Notes:
        - The method modifies the `header` list in place by appending the generated code.
        - The `self.args` list is expected to contain the condition and the branches of the if-else statement.
        - If `self.args[0]` is an instance of `ivy_ast.Some`, it handles local variable scoping.
        - The global variable `indent_level` is used to manage code indentation.
    """
    global indent_level
    code = []
    if isinstance(self.args[0],ivy_ast.Some):
        local_start(header,self.args[0].params())
    indent(code)
    code.append('if(');
    self.args[0].emit(header,code)
    header.extend(code)
    header.append('){\n')
    indent_level += 1
    self.args[1].emit(header)
    indent_level -= 1
    indent(header)
    header.append('}\n')
    if len(self.args) == 3:
        indent(header)
        header.append('else {\n')
        indent_level += 1
        self.args[2].emit(header)
        indent_level -= 1
        indent(header)
        header.append('}\n')
    if isinstance(self.args[0],ivy_ast.Some):
        local_end(header)

ia.IfAction.emit = emit_if

def emit_while(self, header):
    """
    Generates C++ code for a while loop based on the given condition and body.

    Args:
        header (list): A list of strings representing the lines of code generated so far.

    Notes:
        - If the condition is an instance of `ivy_ast.Some`, it initializes local variables.
        - The condition is evaluated and if it results in an empty code list, a simple while loop is generated.
        - If the condition results in a non-empty code list, a more complex while loop with an if-else structure is generated.
        - The function manages the indentation and scope of the generated code.
    """
    global indent_level
    code = []
    if isinstance(self.args[0],ivy_ast.Some):
        local_start(header,self.args[0].params())

    cond = code_eval(code,self.args[0])
    if len(code) == 0:
        open_scope(header,line='while('+cond+')')
        self.args[1].emit(header)
        close_scope(header)
    else:
        open_scope(header,line='while(true)')
        header.extend(code);
        open_scope(header,line='if('+cond+')')
        self.args[1].emit(header)
        close_scope(header)
        open_scope(header,line='else')
        code_line(header,'break')
        close_scope(header)
        close_scope(header)
    if isinstance(self.args[0],ivy_ast.Some):
        local_end(header)
        
ia.WhileAction.emit = emit_while

def emit_choice(self, header):
    """
    Emits C++ code for a choice construct based on the number of arguments.

    This function generates C++ code that represents a choice among multiple
    arguments. If there is only one argument, it directly emits the code for
    that argument. If there are multiple arguments, it creates a temporary
    variable to hold a non-deterministic choice among the arguments and emits
    code for each argument within an if-else construct.

    Args:
        header (list): A list of strings representing the lines of C++ code
                       being generated. The generated code will be appended
                       to this list.

    Global Variables:
        indent_level (int): The current indentation level for the generated
                            code. This is used to properly format the emitted
                            code with the correct indentation.

    Notes:
        - The function uses a global variable `indent_level` to manage code
          indentation.
        - The function assumes the existence of helper functions `new_temp`,
          `mk_nondet`, and `indent`, which are used to generate temporary
          variables, create non-deterministic choices, and manage indentation,
          respectively.
        - The `self.args` attribute is expected to be a list of objects that
          have an `emit` method, which generates code for each argument.
        - The `self.unique_id` attribute is used to ensure unique naming for
          the non-deterministic choice variable.
    """
    global indent_level
    if len(self.args) == 1:
        self.args[0].emit(header)
        return
    tmp = new_temp(header)
    mk_nondet(header,tmp,len(self.args),"___branch",self.unique_id)
    for idx,arg in enumerate(self.args):
        indent(header)
        if idx != 0:
            header.append('else ')
        if idx != len(self.args)-1:
            header.append('if(' + tmp + ' == ' + str(idx) + ')');
        header.append('{\n')
        indent_level += 1
        arg.emit(header)
        indent_level -= 1
        indent(header)
        header.append('}\n')

ia.ChoiceAction.emit = emit_choice

def emit_print_expr(impl, expr):
    """
    Generates C++ code to print the evaluation of an expression with variable context.

    Args:
        impl: The implementation context where the generated code will be added.
        expr: The expression to be evaluated and printed.

    The function performs the following steps:
    1. Extracts the variables from the expression and determines their sorts.
    2. For each variable, generates code to print the variable's context.
    3. Generates code to evaluate and print the expression.
    4. Closes the variable context loops and finalizes the print statement.
    """
    vs = list(ilu.variables_ast(expr))
    dom = [v.sort for v in vs]
    for d,v in zip(dom,vs):
        code_line(impl,'std::cout << "["')
        open_loop(impl,[v])
        code_line(impl,'if ({}) std::cout << ","'.format(varname(v)))
    code_line(impl,'std::cout << ' + code_eval(impl,expr))
    for d,v in zip(dom,vs):
        close_loop(impl,[v])
        code_line(impl,'std::cout << "]"')


def emit_debug(self, header): 
    """
    Emits debug information to the provided header.

    This function generates C++ code that outputs a JSON-like structure
    to the standard output. The first argument in `self.args` is treated
    as an event and is quoted if necessary. Subsequent arguments are
    treated as key-value pairs and are printed in the format:
    "key : value".

    Args:
        self: The instance containing the arguments to be processed.
        header: The header to which the generated C++ code lines are added.

    Returns:
        None
    """
    def quote(event):
        if not event.startswith('"'):
            event = '"' + event + '"'
        event = event.replace('"','\\"')
        return event
    event = quote(self.args[0].rep)
    code_line(header,'std::cout << "{" << std::endl')
    code_line(header,'std::cout << "    \\"event\\" : {}," << std::endl'.format(event))
    for eqn in self.args[1:]:
        code_line(header,'std::cout << "    {} : "'.format(quote(eqn.args[0].rep)))
        emit_print_expr(header,eqn.args[1])
        code_line(header, 'std::cout << "," << std::endl')
    code_line(header,'std::cout << "}" << std::endl')

ia.DebugAction.emit = emit_debug

native_classname = None

def native_reference(atom):
    """
    Generates a native reference string for a given atom.

    This function converts an `ivy_ast.Atom` instance into a string that represents
    a native reference in C++ code. The conversion depends on the type and properties
    of the atom, including whether it is an action, a sort, or a variable.

    Args:
        atom (ivy_ast.Atom): The atom to be converted into a native reference string.

    Returns:
        str: A string representing the native reference of the atom in C++ code.
    """
    if isinstance(atom,ivy_ast.Atom) and atom.rep in im.module.actions:
        res = thunk_name(atom.rep) + '(this'
        res += ''.join(', ' + varname(arg.rep) for arg in atom.args) + ')'
        return res
    if atom.rep in im.module.sig.sorts:
        res = ctype(im.module.sig.sorts[atom.rep],classname=native_classname)
#        print 'type(atom): {} atom.rep: {} res: {}'.format(type(atom),atom.rep,res)
        return res
    res = varname(atom.rep)
    s = atom.rep
    if hasattr(s,'sort') and is_large_type(s.sort) and len(s.sort.dom) > 1:
        res +=('[' + ctuple(s.sort.dom,classname=native_classname) + '(')
        first = True
        for a in atom.args:
            if not first:
                res += ','
            res += varname(a)
            first = False
        res += ')]'
        return res
    for arg in atom.args:
        n = arg.name if hasattr(arg,'name') else arg.rep
        res += '[' + varname(n) + ']'
    return res

def native_reference_in_type(arg):
    """
    Determines the native reference for a given argument based on its type.

    If the argument is an instance of `ivy_ast.Atom` and its `rep` attribute
    is found in the module's actions, it returns a thunk name for the `rep`.
    Otherwise, it returns the native reference for the argument.

    Args:
        arg: The argument whose native reference is to be determined. It can
             be of any type, but specific behavior is defined for instances
             of `ivy_ast.Atom`.

    Returns:
        The native reference for the argument, which could be a thunk name
        if the argument is an `ivy_ast.Atom` with a `rep` in the module's
        actions, or a general native reference otherwise.
    """
    if isinstance(arg,ivy_ast.Atom):
        if arg.rep in im.module.actions:
            return thunk_name(arg.rep)
    return native_reference(arg)


def emit_native_action(self,header):
    """
    Generates and emits native action code based on the provided header and arguments.

    This function processes the `self.args` list to generate native action code. It splits the first argument's code
    by the backtick character (`) and processes each field based on specific conditions:
    - If a field ends with '%', it uses the `native_typeof` function.
    - If a field ends with '"', it uses the `native_z3name` function.
    - Otherwise, it uses the `native_reference` function.

    The processed fields are then concatenated and passed to the `indent_code` function along with the header.

    Args:
        header (str): The header to be used in the generated code.
    """
    fields = self.args[0].code.split('`')
    def nfun(idx):
        return native_typeof if fields[idx-1].endswith('%') else native_z3name if fields[idx-1].endswith('"') else native_reference
    def dm(s):
        return s[:-1] if s.endswith('%') else s
    fields = [(nfun(idx)(self.args[int(s)+1]) if idx % 2 == 1 else dm(s)) for idx,s in enumerate(fields)]
    indent_code(header,''.join(fields))

ia.NativeAction.emit = emit_native_action

def emit_repl_imports(header,impl,classname):
    pass

def emit_repl_boilerplate1(header, impl, classname):
    """
    Generates boilerplate code for a REPL (Read-Eval-Print Loop) in C++.

    This function appends C++ code to the provided `impl` list, which includes:
    - A function `ask_ret` that prompts the user for input within a specified range.
    - A class `classname_repl` that inherits from `classname` and overrides the `ivy_assert` and `ivy_assume` methods to provide custom assertion and assumption handling.
    - A function `isLineInFinalizeAction` to check if a line is within an action called `_finalize`.
    - Signal handlers for generating signals.
    - Utility functions for parsing commands and values.

    Args:
        header (list): A list to which the header code will be appended.
        impl (list): A list to which the implementation code will be appended.
        classname (str): The name of the class to be used in the generated code.
    """
    impl.append("""

int ask_ret(long long bound) {
    int res;
    while(true) {
        __ivy_out << "? ";
        std::cin >> res;
        if (res >= 0 && res < bound) 
            return res;
        std::cerr << "value out of range" << std::endl;
    }
}

""")

    impl.append("""

    class classname_repl : public classname {

    public:

    virtual void ivy_assert(bool truth,const char *msg){
        if (!truth) {
            int i;
            __ivy_out << "assertion_failed(\\"" << msg << "\\")\\n";

            std::string::size_type pos = std::string(msg).find(".ivy");
            std::string path = "";
            if (pos != std::string::npos)
                path = std::string(msg+0,msg+pos);

            std::string lineNumber = "1";
            std::string::size_type pos_n = std::string(msg).find("line");
            if (pos_n != std::string::npos)
                    lineNumber = std::string(msg+pos_n,msg+std::string(msg).length());
            int num;
            sscanf(lineNumber.c_str(),"%*[^0-9]%d", &num);
            lineNumber = std::to_string(num);

            std::string mode = "";
            if(const char* env_p2 = std::getenv("TEST_TYPE")) { 
                mode = std::string(env_p2);
            }
            
            std::string current_protocol = "";
            if(const char* current_protocol_env = std::getenv("PROTOCOL_TESTED")) { 
                current_protocol = std::string(current_protocol_env);
            }
            
            std::string command = "";
            if(path.find("test") != std::string::npos) 
		    path = std::string("/opt/panther_ivy/protocol-testing/") + current_protocol + std::string("/") + current_protocol + std::string("_tests/") + mode + std::string("_tests/") + path;
        
            command = std::string("/bin/sed \'") + lineNumber + std::string("!d\' ")  + path + std::string(".ivy > temps.txt");
            //std::cerr << command.c_str() << "\\n";

            if (system(NULL)) i=system(command.c_str());
            else exit (EXIT_FAILURE);

	        std::ifstream ifs("temps.txt"); //.rdbuf()
	        std::stringstream strStream;
	        strStream << ifs.rdbuf();
	        std::string str = strStream.str();
            str.erase(std::remove(str.begin(), str.end(), \'\\n\'), str.end());
            str.erase(std::remove(str.begin(), str.end(), \'\\t\'), str.end());
            const std::size_t pos_str = str.find_first_not_of(' ');
            if (pos_str != std::string::npos)
                str.erase(0, pos_str);
            std::cerr << str << "\\n";
	        if(std::remove("temps.txt") != 0) 
		        std::cerr << "error: remove(temps.txt) failed\\n";
	        std::cerr << msg << ": error: assertion failed\\n";
            __ivy_out << "assertion_failed(" << str << ")\\n";
            CLOSE_TRACE
            __ivy_exit(1);
        }
    }

    #include <string>
    
    // Function to check if a line is within an action called _finalize
    bool isLineInFinalizeAction(const std::string &path, const std::string &lineToCheck, int lineNumber) {
        std::ifstream file(path);
        if (!file.is_open()) {
            std::cerr << "Error opening file: " << path << "\\n";
            return false;
        }

        std::string line;
        bool inFinalize = false;
        int currentLineNumber = 0;
        std::string targetLine;

        while (std::getline(file, line)) {
            currentLineNumber++;
            if (currentLineNumber == lineNumber) {
                targetLine = line;
                break;
            }
        }

        file.clear();
        file.seekg(0, std::ios::beg);
        currentLineNumber = 0;

        while (std::getline(file, line)) {
            currentLineNumber++;
            if (line.find("export action _finalize") != std::string::npos && currentLineNumber < lineNumber) {
                inFinalize = true;
            }

            if (inFinalize && currentLineNumber == lineNumber) {
                if (line.find(lineToCheck) != std::string::npos) {
                    file.close();
                    return true;
                }
            }

            if (line.find("}") != std::string::npos && inFinalize) {
                inFinalize = false;
            }
        }

        file.close();
        return false;
    }
    

    virtual void ivy_assume(bool truth,const char *msg){
        if (!truth) {
            int i;
            __ivy_out << "assumption_failed(\\"" << msg << "\\")\\n";
            
            std::string::size_type pos = std::string(msg).find(".ivy");
            std::string path = "";
            if (pos != std::string::npos)
                path = std::string(msg+0,msg+pos);
            
            std::string lineNumber = "1";
            std::string::size_type pos_n = std::string(msg).find("line");
            if (pos_n != std::string::npos)
                lineNumber = std::string(msg+pos_n,msg+std::string(msg).length());
            int num;
            sscanf(lineNumber.c_str(),"%*[^0-9]%d", &num);
            lineNumber = std::to_string(num);
            
            std::string mode = "";
            if(const char* env_p2 = std::getenv("TEST_TYPE")) { 
                mode = std::string(env_p2);
            }
            
            std::string current_protocol = "";
            if(const char* current_protocol_env = std::getenv("PROTOCOL_TESTED")) { 
                current_protocol = std::string(current_protocol_env);
            }
            
            std::string command = "";
            if(path.find("test") != std::string::npos) 
		    path = std::string("/opt/panther_ivy/protocol-testing/") + current_protocol + std::string("/") + current_protocol + std::string("_tests/") + mode + std::string("_tests/") + path;
        
            command = std::string("/bin/sed \'") + lineNumber + std::string("!d\' ")  + path + std::string(".ivy > temps.txt");
            //std::cerr << command.c_str() << "\\n";

            if (system(NULL)) i=system(command.c_str());
            else exit (EXIT_FAILURE);

	        std::ifstream ifs("temps.txt"); //.rdbuf()
	        std::stringstream strStream;
	        strStream << ifs.rdbuf();
	        std::string str = strStream.str();
            str.erase(std::remove(str.begin(), str.end(), \'\\n\'), str.end());
            str.erase(std::remove(str.begin(), str.end(), \'\\t\'), str.end());
            const std::size_t pos_str = str.find_first_not_of(' ');
            if (pos_str != std::string::npos)
                str.erase(0, pos_str);
            std::cerr << str << "\\n";
	        if(std::remove("temps.txt") != 0) 
		        std::cerr << "error: remove(temps.txt) failed\\n";
	        std::cerr << msg << ": error: assumption failed\\n";
            __ivy_out << "assumption_failed(" << str << ")\\n";
            CLOSE_TRACE
            
            bool is_LineInFinalizeAction = isLineInFinalizeAction(path + std::string(".ivy"), str, num);
            std::cerr << "is_LineInFinalizeAction: " << is_LineInFinalizeAction << "\\n";
            if (!is_LineInFinalizeAction) __ivy_exit(1);
        }
    }
        
    """.replace('classname',classname).replace('CLOSE_TRACE','__ivy_out << "}" << std::endl;' if opt_trace.get() else ''))

    emit_param_decls(impl,classname+'_repl',im.module.params)
    impl.append(' : '+classname+'('+','.join(map(varname,im.module.params))+'){}\n')
    
    for imp in im.module.imports:
        name = imp.imported()
        if not imp.scope() and name in im.module.actions:
            action = im.module.actions[name]
            emit_method_decl(impl,name,action);
            if target.get() == "test":
                impl.append("{}\n")
                continue
            impl.append('{\n    __ivy_out ' + number_format + ' << "< ' + name[5:] + '"')
            if action.formal_params:
                impl.append(' << "("')
                first = True
                for arg in action.formal_params:
                    if not first:
                        impl.append(' << ","')
                    first = False
                    impl.append(' << {}'.format(varname(arg.rep.name)))
                impl.append(' << ")"')
            impl.append(' << std::endl;\n')
            if action.formal_returns:
                impl.append('    return ask_ret(__CARD__{});\n'.format(action.formal_returns[0].sort))
            impl.append('}\n')

    

    impl.append("""
    };
    struct SignalData {
        classname* ivy_ptr;
        std::vector<gen *>  *generators_ref;
        std::vector<double> *weights_ref;
    };
""".replace('classname',classname))

    impl.append("""
// Override methods to implement low-level network service

    
    //chris
    void signal1_handler_generating(int signo) {
        std::cerr << "call_generating = 1 -> NOT SLEEPING\\n";
        std::cerr << signo << "\\n";
        call_generating = 1;
    }
    
    void signal2_handler_generating(int signo) {
        std::cerr << "call_generating = 0 -> SLEEPING\\n";
        std::cerr << signo << "\\n";
        call_generating = 0;
    }
    
    void signal3_handler_generating(int signo, siginfo_t *info, void *context) {
        call_generating = 1;
        struct SignalData *data_recvd = (struct SignalData *)info->si_value.sival_ptr;
        std::cerr << "-> force generating\\n";
        std::cerr << signo << "\\n";
        double totalweight = 1.0;
        bool do_over = false;
        double frnd = 0.0;
        int num_gens = 1; //chris maybe 2 ?
        double choices = totalweight + 5.0;
        if (do_over) {
           do_over = false;
        }  else {
            frnd = choices * (((double)rand())/(((double)RAND_MAX)+1.0));
        }
        // std::cout << "frnd = " << frnd << std::endl;
        if (frnd < totalweight) {
            int idx = 0;
            double sum = 0.0;
            while (idx < num_gens-1) {
                sum += (data_recvd->weights_ref)->at(idx);
                if (frnd < sum)
                    break;
                idx++;
            }
            gen &g = *(data_recvd->generators_ref)->at(idx);
            data_recvd->ivy_ptr->__lock();
#ifdef _WIN32
            LARGE_INTEGER before;
            QueryPerformanceCounter(&before);
#endif      
            bool sat = false;
            if (call_generating) {
                data_recvd->ivy_ptr->_generating = true;
                sat = g.generate(*data_recvd->ivy_ptr);
            } 
#ifdef _WIN32
            LARGE_INTEGER after;
            QueryPerformanceCounter(&after);
//            __ivy_out << "idx: " << idx << " sat: " << sat << " time: " << (((double)(after.QuadPart-before.QuadPart))/freq.QuadPart) << std::endl;
#endif
            if (sat){
                g.execute(*data_recvd->ivy_ptr);
                data_recvd->ivy_ptr->_generating = false;
                data_recvd->ivy_ptr->__unlock();
#ifdef _WIN32
                Sleep(sleep_ms);
#endif
            }
            else {
                data_recvd->ivy_ptr->_generating = false;
                data_recvd->ivy_ptr->__unlock();
                //cycle--;
            }
            //continue;
        }


        fd_set rdfds;
        FD_ZERO(&rdfds);
        int maxfds = 0;

        for (unsigned i = 0; i < readers.size(); i++) {
            reader *r = readers[i];
            int fds = r->fdes();
            if (fds >= 0) {
                FD_SET(fds,&rdfds);
            }
            if (fds > maxfds)
                maxfds = fds;
        }

#ifdef _WIN32
        int timer_min = 15;
#else
        int timer_min = 5;
        if(const char* env_p2 = std::getenv("TIMEOUT_IVY")) { 
            timer_min = std::stoi(std::string(env_p2));
        }
#endif

        struct timeval timeout;
        timeout.tv_sec = timer_min/1000;
        timeout.tv_usec = 1000 * (timer_min % 1000);

#ifdef _WIN32
        int foo;
        if (readers.size() == 0){  // winsock can't handle empty fdset!
            Sleep(timer_min);
            foo = 0;
        }
        else
            foo = select(maxfds+1,&rdfds,0,0,&timeout);
#else
        int foo = select(maxfds+1,&rdfds,0,0,&timeout);
        //chris: self-pipe trick
        while (foo == -1 & errno == EINTR) {
            std::cerr << "select failed - restart with self pipe trick " << std::endl;
            foo = select(maxfds+1,&rdfds,0,0,&timeout);
            continue;
        }
            
#endif

        if (foo < 0)
#ifdef _WIN32
            {std::cerr << "select failed: " << WSAGetLastError() << std::endl; __ivy_exit(1);}
#else
            {perror("select failed"); __ivy_exit(1);}
#endif
        
        if (foo == 0){
           // std::cout << "TIMEOUT\\n";            
           //cycle--;
           for (unsigned i = 0; i < timers.size(); i++){
               if (timer_min >= timers[i]->ms_delay()) {
                   //cycle++;
                   break;
               }
           }
           for (unsigned i = 0; i < timers.size(); i++)
               timers[i]->timeout(timer_min);
        }
        else {
            int fdc = 0;
            for (unsigned i = 0; i < readers.size(); i++) {
                reader *r = readers[i];
                if (FD_ISSET(r->fdes(),&rdfds))
                    fdc++;
            }
            // std::cout << "fdc = " << fdc << std::endl;
            int fdi = fdc * (((double)rand())/(((double)RAND_MAX)+1.0));
            fdc = 0;
            for (unsigned i = 0; i < readers.size(); i++) {
                reader *r = readers[i];
                if (FD_ISSET(r->fdes(),&rdfds)) {
                    if (fdc == fdi) {
                        // std::cout << "reader = " << i << std::endl;
                        r->read();
                        if (r->background()) {
                           //cycle--;
                           do_over = true;
                        }
                        break;
                    }
                    fdc++;

                }
            }
        }
    }
    
bool is_white(int c) {
    return (c == ' ' || c == '\\t' || c == '\\n' || c == '\\r');
}

bool is_ident(int c) {
    return c == '_' || c == '.' || (c >= 'A' &&  c <= 'Z')
        || (c >= 'a' &&  c <= 'z')
        || (c >= '0' &&  c <= '9');
}

void skip_white(const std::string& str, int &pos){
    while (pos < str.size() && is_white(str[pos]))
        pos++;
}

struct syntax_error {
    int pos;
    syntax_error(int pos) : pos(pos) {}
};

void throw_syntax(int pos){
    throw syntax_error(pos);
}

std::string get_ident(const std::string& str, int &pos) {
    std::string res = "";
    while (pos < str.size() && is_ident(str[pos])) {
        res.push_back(str[pos]);
        pos++;
    }
    if (res.size() == 0)
        throw_syntax(pos);
    return res;
}

ivy_value parse_value(const std::string& cmd, int &pos) {
    ivy_value res;
    res.pos = pos;
    skip_white(cmd,pos);
    if (pos < cmd.size() && cmd[pos] == '[') {
        while (true) {
            pos++;
            skip_white(cmd,pos);
            if (pos < cmd.size() && cmd[pos] == ']')
                break;
            res.fields.push_back(parse_value(cmd,pos));
            skip_white(cmd,pos);
            if (pos < cmd.size() && cmd[pos] == ']')
                break;
            if (!(pos < cmd.size() && cmd[pos] == ','))
                throw_syntax(pos);
        }
        pos++;
    }
    else if (pos < cmd.size() && cmd[pos] == '{') {
        while (true) {
            ivy_value field;
            pos++;
            skip_white(cmd,pos);
            field.atom = get_ident(cmd,pos);
            skip_white(cmd,pos);
            if (!(pos < cmd.size() && cmd[pos] == ':'))
                 throw_syntax(pos);
            pos++;
            skip_white(cmd,pos);
            field.fields.push_back(parse_value(cmd,pos));
            res.fields.push_back(field);
            skip_white(cmd,pos);
            if (pos < cmd.size() && cmd[pos] == '}')
                break;
            if (!(pos < cmd.size() && cmd[pos] == ','))
                throw_syntax(pos);
        }
        pos++;
    }
    else if (pos < cmd.size() && cmd[pos] == '"') {
        pos++;
        res.atom = "";
        while (pos < cmd.size() && cmd[pos] != '"') {
            char c = cmd[pos++];
            if (c == '\\\\') {
                if (pos == cmd.size())
                    throw_syntax(pos);
                c = cmd[pos++];
                c = (c == 'n') ? 10 : (c == 'r') ? 13 : (c == 't') ? 9 : c;
            }
            res.atom.push_back(c);
        }
        if(pos == cmd.size())
            throw_syntax(pos);
        pos++;
    }
    else 
        res.atom = get_ident(cmd,pos);
    return res;
}

void parse_command(const std::string &cmd, std::string &action, std::vector<ivy_value> &args) {
    int pos = 0;
    skip_white(cmd,pos);
    action = get_ident(cmd,pos);
    skip_white(cmd,pos);
    if (pos < cmd.size() && cmd[pos] == '(') {
        pos++;
        skip_white(cmd,pos);
        args.push_back(parse_value(cmd,pos));
        while(true) {
            skip_white(cmd,pos);
            if (!(pos < cmd.size() && cmd[pos] == ','))
                break;
            pos++;
            args.push_back(parse_value(cmd,pos));
        }
        if (!(pos < cmd.size() && cmd[pos] == ')'))
            throw_syntax(pos);
        pos++;
    }
    skip_white(cmd,pos);
    if (pos != cmd.size())
        throw_syntax(pos);
}

struct bad_arity {
    std::string action;
    int num;
    bad_arity(std::string &_action, unsigned _num) : action(_action), num(_num) {}
};

void check_arity(std::vector<ivy_value> &args, unsigned num, std::string &action) {
    if (args.size() != num)
        throw bad_arity(action,num);
}

""".replace('classname',classname))


def emit_repl_boilerplate1a(header, impl, classname):
    """
    Generates and appends C++ boilerplate code for a REPL (Read-Eval-Print Loop) to the provided implementation list.

    Args:
        header (list): A list to which the header code can be appended.
        impl (list): A list to which the implementation code will be appended.
        classname (str): The name of the class to be used in the generated boilerplate code.

    The generated boilerplate code includes:
    - A `stdin_reader` class that reads from standard input and processes lines.
    - A `cmd_reader` class that inherits from `stdin_reader` and processes commands specific to the provided classname.
    """
    impl.append("""

class stdin_reader: public reader {
    std::string buf;
    std::string eof_flag;

public:
    bool eof(){
      return eof_flag.size();
    }
    virtual int fdes(){
        return 0;
    }
    virtual void read() {
        char tmp[257];
        int chars = ::read(0,tmp,256);
        if (chars == 0) {  // EOF
            if (buf.size())
                process(buf);
            eof_flag = "eof";
        }
        tmp[chars] = 0;
        buf += std::string(tmp);
        size_t pos;
        while ((pos = buf.find('\\n')) != std::string::npos) {
            std::string line = buf.substr(0,pos+1);
            buf.erase(0,pos+1);
            process(line);
        }
    }
    virtual void process(const std::string &line) {
        __ivy_out << line;
    }
};

class cmd_reader: public stdin_reader {
    int lineno;
public:
    classname_repl &ivy;    

    cmd_reader(classname_repl &_ivy) : ivy(_ivy) {
        lineno = 1;
        if (isatty(fdes()))
            __ivy_out << "> "; __ivy_out.flush();
    }

    virtual void process(const std::string &cmd) {
        std::string action;
        std::vector<ivy_value> args;
        try {
            parse_command(cmd,action,args);
            ivy.__lock();
""".replace('classname',classname))


def emit_repl_boilerplate2(header, impl, classname):
    """
    Appends a boilerplate C++ code snippet to the implementation list.

    This function adds a predefined C++ code snippet to the `impl` list, which
    handles various exceptions and outputs error messages to the standard error
    stream. The snippet also includes a prompt for user input if the file
    descriptor is a terminal.

    Args:
        header (list): A list to which the header code can be appended (not used in this function).
        impl (list): A list to which the implementation code is appended.
        classname (str): The name of the class to be used in the boilerplate code.

    Returns:
        None
    """
    impl.append("""
            {
                std::cerr << "undefined action: " << action << std::endl;
            }
            ivy.__unlock();
        }
        catch (syntax_error& err) {
            ivy.__unlock();
            std::cerr << "line " << lineno << ":" << err.pos << ": syntax error" << std::endl;
        }
        catch (out_of_bounds &err) {
            ivy.__unlock();
            std::cerr << "line " << lineno << ":" << err.pos << ": " << err.txt << " bad value" << std::endl;
        }
        catch (bad_arity &err) {
            ivy.__unlock();
            std::cerr << "action " << err.action << " takes " << err.num  << " input parameters" << std::endl;
        }
        if (isatty(fdes()))
            __ivy_out << "> "; __ivy_out.flush();
        lineno++;
    }
};



""".replace('classname',classname))

def emit_winsock_init(impl):
    """
    Appends a string containing the boilerplate code for initializing Winsock on Windows to the provided list.

    This function adds a multi-line string to the `impl` list, which contains the necessary code to initialize
    Winsock on a Windows platform. The code includes version checks and error handling as recommended by the 
    Windows documentation.

    Args:
        impl (list): A list to which the Winsock initialization code will be appended.

    Returns:
        None
    """
    impl.append("""
#ifdef _WIN32
    // Boilerplate from windows docs

    {
        WORD wVersionRequested;
        WSADATA wsaData;
        int err;

    /* Use the MAKEWORD(lowbyte, highbyte) macro declared in Windef.h */
        wVersionRequested = MAKEWORD(2, 2);

        err = WSAStartup(wVersionRequested, &wsaData);
        if (err != 0) {
            /* Tell the user that we could not find a usable */
            /* Winsock DLL.                                  */
            printf("WSAStartup failed with error: %d\\n", err);
            return 1;
        }

    /* Confirm that the WinSock DLL supports 2.2.*/
    /* Note that if the DLL supports versions greater    */
    /* than 2.2 in addition to 2.2, it will still return */
    /* 2.2 in wVersion since that is the version we      */
    /* requested.                                        */

        if (LOBYTE(wsaData.wVersion) != 2 || HIBYTE(wsaData.wVersion) != 2) {
            /* Tell the user that we could not find a usable */
            /* WinSock DLL.                                  */
            printf("Could not find a usable version of Winsock.dll\\n");
            WSACleanup();
            return 1;
        }
    }
#endif
""")


def emit_repl_boilerplate3(header, impl, classname):
    """
    Appends a boilerplate code snippet to the implementation list for a REPL (Read-Eval-Print Loop) setup.

    Args:
        header (str): The header file content (not used in this function).
        impl (list): The list to which the boilerplate code will be appended.
        classname (str): The name of the class to be used in the boilerplate code.

    Returns:
        None
    """
    impl.append("""

    ivy.__unlock();

    cmd_reader *cr = new cmd_reader(ivy);

    // The main thread runs the console reader

    while (!cr->eof())
        cr->read();
    return 0;

""".replace('classname',classname))

def emit_repl_boilerplate3server(header, impl, classname):
    """
    Appends a boilerplate C++ code snippet to the implementation list for a server.

    This function generates a C++ code snippet that includes unlocking a mutex,
    waiting for all reader threads to terminate, and then returning 0. The generated
    code is appended to the provided implementation list.

    Args:
        header (str): The header file content (not used in this function).
        impl (list): The list to which the generated C++ code snippet will be appended.
        classname (str): The name of the class to be used in the generated code snippet.

    Returns:
        None
    """
    impl.append("""

    
    ivy.__unlock();

    // The main thread waits for all reader threads to die

    for(unsigned i = 0; true ; i++) {
        ivy.__lock();
        if (i >= ivy.thread_ids.size()){
            ivy.__unlock();
            break;
        }
        pthread_t tid = ivy.thread_ids[i];
        ivy.__unlock();
        pthread_join(tid,NULL);
    }
    return 0;

""".replace('classname',classname))

def emit_repl_boilerplate3test(header, impl, classname):
    """
    Generates and appends C++ boilerplate code for a REPL (Read-Eval-Print Loop) test to the provided implementation list.

    Args:
        header (list): A list to which the generated C++ header code will be appended.
        impl (list): A list to which the generated C++ implementation code will be appended.
        classname (str): The name of the class to be used in the generated code.

    The function performs the following tasks:
    - Initializes various components and binds readers.
    - Sets up signal handling for SIGUSR3.
    - Generates initialization code for actions and their weights.
    - Appends the main loop for the REPL test, which includes:
        - Randomly selecting actions based on their weights.
        - Handling timeouts and reader events.
        - Executing selected actions and handling their results.
    - Finalizes the test and cleans up resources.

    Note:
        This function assumes the existence of certain global variables and structures such as `ivy`, `readers`, `timers`, `im`, and `iu`.
    """
    impl.append("""
        ivy.__unlock();
        initializing = false;
        for(int rdridx = 0; rdridx < readers.size(); rdridx++) {
            readers[rdridx]->bind();
        }
                    
        init_gen my_init_gen(ivy);
        my_init_gen.generate(ivy);
        std::vector<gen *> generators;
        std::vector<double> weights;
        struct sigaction sa3;
        sa3.sa_sigaction = signal3_handler_generating;
        sa3.sa_flags = SA_RESTART | SA_SIGINFO;
        sigemptyset(&sa3.sa_mask);
                

        if (sigaction(SIGUSR3, &sa3, NULL) == -1) {
            perror("sigaction");
            return 1;
        }
        struct SignalData signal_data;
        signal_data.ivy_ptr = &ivy;
        signal_data.generators_ref = &generators;
        signal_data.weights_ref = &weights;
        sigdata.sival_ptr = &signal_data;
        
""")
    totalweight = 0.0
    num_public_actions = 0
    for actname in sorted(im.module.public_actions):
        if actname == 'ext:_finalize':
            continue
        num_public_actions += 1
        action = im.module.actions[actname]
        impl.append("std::cerr << \"action: {}\\n\";\n".format(actname))
        impl.append("std::cerr << \"varname(actname): {}\\n\";\n".format(varname(actname)))
        impl.append("std::cerr << \"index : {}\\n\";\n".format(num_public_actions-1))
        impl.append("        generators.push_back(new {}_gen(ivy));\n".format(varname(actname)))
        aname = (actname[4:] if actname.startswith('ext:') else actname) +'.weight'
        if aname in im.module.attributes:
            astring = im.module.attributes[aname].rep
            if astring.startswith('"'):
                astring = astring[1:-1]
            try:
                aval = float(astring)
            except ValueError:
                raise iu.IvyError(None,'bad weight attribute for action{}: {}'.format(actname,astring))
        else:
            aval = 1.0
        impl.append("        weights.push_back({});\n".format(aval))
        totalweight += aval
    impl.append("        double totalweight = {};\n".format(totalweight))
    impl.append("        int num_gens = {};\n".format(num_public_actions))
            
    final_code = 'ivy.__lock(); ivy.ext___finalize(); ivy.__unlock();' if 'ext:_finalize' in im.module.public_actions else ''
    
    impl.append("""

#ifdef _WIN32
    LARGE_INTEGER freq;
    QueryPerformanceFrequency(&freq);
#endif
    double frnd = 0.0;
    bool do_over = false;
    for(int cycle = 0; cycle < test_iters; cycle++) {
//        std::cout << "totalweight = " << totalweight << std::endl;
//        double choices = totalweight + readers.size() + timers.size();
        double choices = totalweight + 5.0;
        if (do_over) {
           do_over = false;
        }  else {
            frnd = choices * (((double)rand())/(((double)RAND_MAX)+1.0));
        }
        // std::cout << "frnd = " << frnd << std::endl;
        if (frnd < totalweight) {
            int idx = 0;
            double sum = 0.0;
            while (idx < num_gens-1) {
                sum += weights[idx]; // should not be execute with num_gen=1
                if (frnd < sum)
                    break;
                idx++;
            }
            gen &g = *generators[idx];
            ivy.__lock();
#ifdef _WIN32
            LARGE_INTEGER before;
            QueryPerformanceCounter(&before);
#endif      
            //std::chrono::high_resolution_clock::time_point start = std::chrono::high_resolution_clock::now();
            bool sat = false;
            if (call_generating) {
                ivy._generating = true;
                sat = g.generate(ivy);
            }
            //std::chrono::high_resolution_clock::time_point end = std::chrono::high_resolution_clock::now();
            //unsigned long long duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
            //if(duration > 300) {
            //    std::cerr << "Generating action: " << idx << std::endl;
            //    std::cerr << "Performance generation measurement: " << duration << " milliseconds" << std::endl; 
            //}
#ifdef _WIN32
            LARGE_INTEGER after;
            QueryPerformanceCounter(&after);
//            __ivy_out << "idx: " << idx << " sat: " << sat << " time: " << (((double)(after.QuadPart-before.QuadPart))/freq.QuadPart) << std::endl;
#endif
            if (sat){
                g.execute(ivy);
                ivy._generating = false;
                ivy.__unlock();
#ifdef _WIN32
                Sleep(sleep_ms);
#endif
            }
            else {
                ivy._generating = false;
                ivy.__unlock();
                cycle--;
            }
            continue;
        }


        fd_set rdfds;
        FD_ZERO(&rdfds);
        int maxfds = 0;

        for (unsigned i = 0; i < readers.size(); i++) {
            reader *r = readers[i];
            int fds = r->fdes();
            if (fds >= 0) {
                FD_SET(fds,&rdfds);
            }
            if (fds > maxfds)
                maxfds = fds;
        }

#ifdef _WIN32
        int timer_min = 15;
#else
        int timer_min = 5;
        if(const char* env_p2 = std::getenv("TIMEOUT_IVY")) { 
            timer_min = std::stoi(std::string(env_p2));
        }
#endif

        struct timeval timeout;
        timeout.tv_sec = timer_min/1000;
        timeout.tv_usec = 1000 * (timer_min % 1000);

#ifdef _WIN32
        int foo;
        if (readers.size() == 0){  // winsock can't handle empty fdset!
            Sleep(timer_min);
            foo = 0;
        }
        else
            foo = select(maxfds+1,&rdfds,0,0,&timeout);
#else
        int foo = select(maxfds+1,&rdfds,0,0,&timeout);
        //chris: self-pipe trick
        while (foo == -1 & errno == EINTR) {
            std::cerr << "select failed - restart with self pipe trick " << std::endl;
            foo = select(maxfds+1,&rdfds,0,0,&timeout);
            continue;
        }
            
#endif

        if (foo < 0)
#ifdef _WIN32
            {std::cerr << "select failed: " << WSAGetLastError() << std::endl; __ivy_exit(1);}
#else
            {perror("select failed"); __ivy_exit(1);}
#endif
        
        if (foo == 0){
           // std::cout << "TIMEOUT\\n";            
           cycle--;
           for (unsigned i = 0; i < timers.size(); i++){
               if (timer_min >= timers[i]->ms_delay()) {
                   cycle++;
                   break;
               }
           }
           for (unsigned i = 0; i < timers.size(); i++)
               timers[i]->timeout(timer_min);
        }
        else {
            int fdc = 0;
            for (unsigned i = 0; i < readers.size(); i++) {
                reader *r = readers[i];
                if (FD_ISSET(r->fdes(),&rdfds))
                    fdc++;
            }
            // std::cout << "fdc = " << fdc << std::endl;
            int fdi = fdc * (((double)rand())/(((double)RAND_MAX)+1.0));
            fdc = 0;
            for (unsigned i = 0; i < readers.size(); i++) {
                reader *r = readers[i];
                if (FD_ISSET(r->fdes(),&rdfds)) {
                    if (fdc == fdi) {
                        // std::cout << "reader = " << i << std::endl;
                        r->read();
                        if (r->background()) {
                           cycle--;
                           do_over = true;
                        }
                        break;
                    }
                    fdc++;

                }
            }
        }            
    }
    
    FINALIZE
#ifdef _WIN32
                Sleep(final_ms);  // HACK: wait for late responses
#endif
    __ivy_out << "test_completed" << std::endl;
    if (runidx == runs-1) {
        struct timespec ts;
        int ms = 50;
        ts.tv_sec = ms/1000;
        ts.tv_nsec = (ms % 1000) * 1000000;
        nanosleep(&ts,NULL);
        exit(0);
    }
    for (unsigned i = 0; i < readers.size(); i++)
        delete readers[i];
    readers.clear();
    for (unsigned i = 0; i < timers.size(); i++)
        delete timers[i];
    timers.clear();


""".replace('classname',classname).replace('FINALIZE',final_code))

    # impl.append("""
    # void atexit_handler_1()
    # {
    #     std::cout << "At exit #1\n";
    #     FINALIZE
    # }
    
    # void atexit_handler_2()
    # {
    #     std::cout << "At exit #2\n";
    #     FINALIZE
    # }""")

def emit_boilerplate1(header, impl, classname):
    """
    Generates the boilerplate code for a C++ class that interfaces with the Z3 theorem prover.

    Args:
        header (list): A list to which the generated header code will be appended.
        impl (list): A list to which the generated implementation code will be appended.
        classname (str): The name of the class to be generated.

    The generated class includes methods for:
    - Creating and managing Z3 expressions and sorts.
    - Evaluating Z3 expressions.
    - Applying Z3 functions.
    - Randomizing Z3 expressions.
    - Adding assertions to the Z3 solver.
    - Solving the Z3 constraints and retrieving the model.
    """
    header.append("""
#include <string>
#include <vector>
#include <sstream>
#include <cstdlib>
""")
    header.append("""

using namespace hash_space;

inline z3::expr forall(const std::vector<z3::expr> &exprs, z3::expr const & b) {
    Z3_app *vars = new  Z3_app [exprs.size()];
    std::copy(exprs.begin(),exprs.end(),vars);
    Z3_ast r = Z3_mk_forall_const(b.ctx(), 0, exprs.size(), vars, 0, 0, b);
    b.check_error();
    delete[] vars;
    return z3::expr(b.ctx(), r);
}

class gen : public ivy_gen {

public:
    z3::context ctx;
    z3::solver slvr;
    z3::model model;

    hash_map<std::string, z3::sort> enum_sorts;
    hash_map<Z3_sort, z3::func_decl_vector> enum_values;
    hash_map<std::string, std::pair<unsigned long long, unsigned long long> > int_ranges;
    hash_map<std::string, z3::func_decl> decls_by_name;
    hash_map<Z3_symbol,int> enum_to_int;
    std::vector<Z3_symbol> sort_names;
    std::vector<Z3_sort> sorts;
    std::vector<Z3_symbol> decl_names;
    std::vector<Z3_func_decl> decls;
    std::vector<z3::expr> alits;
    int tmp_ctr;

    gen(): slvr(ctx), model(ctx,(Z3_model)0) {
        enum_sorts.insert(std::pair<std::string, z3::sort>("bool",ctx.bool_sort()));
        tmp_ctr = 0;
    }


public:
    virtual bool generate(classname& obj)=0;
    virtual void execute(classname& obj)=0;
    virtual ~gen(){}
    
    std::string fresh_name() {
        std::ostringstream ss;
        ss << "$tmp" << tmp_ctr++;
        return(ss.str());
    }

    z3::expr mk_apply_expr(const char *decl_name, unsigned num_args, const int *args){
        z3::func_decl decl = decls_by_name.find(decl_name)->second;
        std::vector<z3::expr> expr_args;
        unsigned arity = decl.arity();
        assert(arity == num_args);
        for(unsigned i = 0; i < arity; i ++) {
            z3::sort sort = decl.domain(i);
            expr_args.push_back(int_to_z3(sort,args[i]));
        }
        return decl(arity,&expr_args[0]);
    }

    long long eval(const z3::expr &apply_expr) {
        try {
            z3::expr foo = model.eval(apply_expr,true);
            // std::cout << apply_expr << " = " << foo << std::endl;
            if (foo.is_int()) {
                assert(foo.is_numeral());
                int v;
                if (Z3_get_numeral_int(ctx,foo,&v) != Z3_TRUE) {
                    std::cerr << "integer value from Z3 too large for machine int: " << foo << std::endl;
                    assert(false);
                }
                return v;
            }
            if (foo.is_bv()) {
                assert(foo.is_numeral());
                uint64_t v;
                if (Z3_get_numeral_uint64(ctx,foo,&v) != Z3_TRUE) {
                    std::cerr << "bit vector value from Z3 too large for machine uint64: " << foo << std::endl;
                    assert(false);
                }
                return v;
            }
            assert(foo.is_app());
            if (foo.is_bool())
                return (foo.decl().decl_kind() == Z3_OP_TRUE) ? 1 : 0;
            return enum_to_int[foo.decl().name()];
        }
        catch (const z3::exception &e) {
            std::cerr << e << std::endl;
            throw e;
        }
    }

    __strlit eval_string(const z3::expr &apply_expr) {
        try {
            z3::expr foo = model.eval(apply_expr,true);
            assert(Z3_is_string(ctx,foo));
            return Z3_get_string(ctx,foo);
        }
        catch (const z3::exception &e) {
            std::cerr << e << std::endl;
            throw e;
        }
    }
    // TODO add int128_t CHRIS
    long long eval_apply(const char *decl_name, unsigned num_args, const int *args) {
        z3::expr apply_expr = mk_apply_expr(decl_name,num_args,args);
        //        std::cout << "apply_expr: " << apply_expr << std::endl;
        try {
            z3::expr foo = model.eval(apply_expr,true);
            if (foo.is_int()) {
                assert(foo.is_numeral());
                int v;
                if (Z3_get_numeral_int(ctx,foo,&v) == Z3_TRUE) {
                   return v;
                }
                uint64_t vl;
                if (Z3_get_numeral_uint64(ctx,foo,&vl) != Z3_TRUE) {
                    assert(false && "bit vector value from Z3 too large for machine uint64");
                }
                return vl;
            }
            if (foo.is_bv()) {
                assert(foo.is_numeral());
                uint64_t v;
                if (Z3_get_numeral_uint64(ctx,foo,&v) != Z3_TRUE) {
                    assert(false && "bit vector value from Z3 too large for machine uint64");
                }
                return v;
            }
            if (foo.is_bv() || foo.is_int()) {
                assert(foo.is_numeral());
                unsigned v;
                if (Z3_get_numeral_uint(ctx,foo,&v) != Z3_TRUE)
                    assert(false && "bit vector value too large for machine int");
                return v;
            }
            assert(foo.is_app());
            if (foo.is_bool())
                return (foo.decl().decl_kind() == Z3_OP_TRUE) ? 1 : 0;
            return enum_to_int[foo.decl().name()];
        }
        catch (const z3::exception &e) {
            std::cerr << e << std::endl;
            throw e;
        }
    }

    long long eval_apply(const char *decl_name) {
        return eval_apply(decl_name,0,(int *)0);
    }

    long long eval_apply(const char *decl_name, int arg0) {
        return eval_apply(decl_name,1,&arg0);
    }
    
    long long eval_apply(const char *decl_name, int arg0, int arg1) {
        int args[2] = {arg0,arg1};
        return eval_apply(decl_name,2,args);
    }

    long long eval_apply(const char *decl_name, int arg0, int arg1, int arg2) {
        int args[3] = {arg0,arg1,arg2};
        return eval_apply(decl_name,3,args);
    }

    long long eval_apply(const char *decl_name, int arg0, int arg1, int arg2, int arg3) {
        int args[4] = {arg0,arg1,arg2,arg3};
        return eval_apply(decl_name,4,args);
    }

    z3::expr apply(const char *decl_name, std::vector<z3::expr> &expr_args) {
        z3::func_decl decl = decls_by_name.find(decl_name)->second;
        unsigned arity = decl.arity();
        assert(arity == expr_args.size());
        return decl(arity,&expr_args[0]);
    }

    z3::expr apply(const char *decl_name) {
        std::vector<z3::expr> a;
        return apply(decl_name,a);
    }

    z3::expr apply(const char *decl_name, z3::expr arg0) {
        std::vector<z3::expr> a;
        a.push_back(arg0);
        return apply(decl_name,a);
    }
    
    z3::expr apply(const char *decl_name, z3::expr arg0, z3::expr arg1) {
        std::vector<z3::expr> a;
        a.push_back(arg0);
        a.push_back(arg1);
        return apply(decl_name,a);
    }
    
    z3::expr apply(const char *decl_name, z3::expr arg0, z3::expr arg1, z3::expr arg2) {
        std::vector<z3::expr> a;
        a.push_back(arg0);
        a.push_back(arg1);
        a.push_back(arg2);
        return apply(decl_name,a);
    }

    z3::expr apply(const char *decl_name, z3::expr arg0, z3::expr arg1, z3::expr arg2, z3::expr arg3) {
        std::vector<z3::expr> a;
        a.push_back(arg0);
        a.push_back(arg1);
        a.push_back(arg2);
        a.push_back(arg3);
        return apply(decl_name,a);
    }

    z3::expr apply(const char *decl_name, z3::expr arg0, z3::expr arg1, z3::expr arg2, z3::expr arg3, z3::expr arg4) {
        std::vector<z3::expr> a;
        a.push_back(arg0);
        a.push_back(arg1);
        a.push_back(arg2);
        a.push_back(arg3);
        a.push_back(arg4);
        return apply(decl_name,a);
    }

    z3::expr int_to_z3(const z3::sort &range, int64_t value) {
        if (range.is_bool())
            return ctx.bool_val((bool)value);
        if (range.is_bv())
            return ctx.bv_val((int)value,range.bv_size());
        if (range.is_int())
            return ctx.int_val((int)value);
        return enum_values.find(range)->second[(int)value]();
    }

    z3::expr int_to_z3(const z3::sort &range, const std::string& value) {
        return ctx.string_val(value);
    }

    std::pair<unsigned long long, unsigned long long> sort_range(const z3::sort &range, const std::string &sort_name) {
        std::pair<unsigned long long, unsigned long long> res;
        res.first = 0;
        if (range.is_bool())
            res.second = 1;
        else if (range.is_bv()) {
            int size = range.bv_size();
            if (size >= 64) 
                res.second = (unsigned long long)(-1);
            else res.second = (1 << size) - 1;
        }
        else if (range.is_int()) {
            if (int_ranges.find(sort_name) != int_ranges.end())
                res = int_ranges[sort_name];
            else res.second = 4;  // bogus -- we need a good way to randomize ints
        }
        else res.second = enum_values.find(range)->second.size() - 1;
        // std::cout <<  "sort range: " << range << " = " << res.first << " .. " << res.second << std::endl;
        return res;
    }

    int set(const char *decl_name, unsigned num_args, const int *args, int value) {
        z3::func_decl decl = decls_by_name.find(decl_name)->second;
        std::vector<z3::expr> expr_args;
        unsigned arity = decl.arity();
        assert(arity == num_args);
        for(unsigned i = 0; i < arity; i ++) {
            z3::sort sort = decl.domain(i);
            expr_args.push_back(int_to_z3(sort,args[i]));
        }
        z3::expr apply_expr = decl(arity,&expr_args[0]);
        z3::sort range = decl.range();
        z3::expr val_expr = int_to_z3(range,value);
        z3::expr pred = apply_expr == val_expr;
        //        std::cout << "pred: " << pred << std::endl;
        slvr.add(pred);
        return 0;
    }

    int set(const char *decl_name, int value) {
        return set(decl_name,0,(int *)0,value);
    }

    int set(const char *decl_name, int arg0, int value) {
        return set(decl_name,1,&arg0,value);
    }
    
    int set(const char *decl_name, int arg0, int arg1, int value) {
        int args[2] = {arg0,arg1};
        return set(decl_name,2,args,value);
    }

    int set(const char *decl_name, int arg0, int arg1, int arg2, int value) {
        int args[3] = {arg0,arg1,arg2};
        return set(decl_name,3,args,value);
    }

    void add_alit(const z3::expr &pred){
        if (__ivy_modelfile.is_open()) 
            __ivy_modelfile << "pred: " << pred << std::endl;
        std::ostringstream ss;
        ss << "alit:" << alits.size();
        z3::expr alit = ctx.bool_const(ss.str().c_str());
        if (__ivy_modelfile.is_open()) 
            __ivy_modelfile << "alit: " << alit << std::endl;
        alits.push_back(alit);
        slvr.add(!alit || pred);
    }

    unsigned long long random_range(std::pair<unsigned long long, unsigned long long> rng) {
        unsigned long long res = 0;
        for (unsigned i = 0; i < 4; i++) res = (res << 16) | (rand() & 0xffff);
        unsigned long long card = rng.second - rng.first;
        if (card != (unsigned long long)(-1))
            res = (res % (card+1)) + rng.first;
        return res;
    }

    void randomize(const z3::expr &apply_expr, const std::string &sort_name) {
        z3::sort range = apply_expr.get_sort();
//        std::cout << apply_expr << " : " << range << std::endl;
        unsigned long long value = random_range(sort_range(range,sort_name));
        z3::expr val_expr = int_to_z3(range,value);
        z3::expr pred = apply_expr == val_expr;
        add_alit(pred);
    }

    void randomize(const char *decl_name, unsigned num_args, const int *args, const std::string &sort_name) {
        z3::func_decl decl = decls_by_name.find(decl_name)->second;
        z3::expr apply_expr = mk_apply_expr(decl_name,num_args,args);
        z3::sort range = decl.range();
        unsigned long long value = random_range(sort_range(range,sort_name));
        z3::expr val_expr = int_to_z3(range,value);
        z3::expr pred = apply_expr == val_expr;
        add_alit(pred);
    }

    void randomize(const char *decl_name, const std::string &sort_name) {
        randomize(decl_name,0,(int *)0,sort_name);
    }

    void randomize(const char *decl_name, int arg0, const std::string &sort_name) {
        randomize(decl_name,1,&arg0,sort_name);
    }
    
    void randomize(const char *decl_name, int arg0, int arg1, const std::string &sort_name) {
        int args[2] = {arg0,arg1};
        randomize(decl_name,2,args,sort_name);
    }

    void randomize(const char *decl_name, int arg0, int arg1, int arg2, const std::string &sort_name) {
        int args[3] = {arg0,arg1,arg2};
        randomize(decl_name,3,args,sort_name);
    }

    void push(){
        slvr.push();
    }

    void pop(){
        slvr.pop();
    }

    z3::sort sort(const char *name) {
        if (std::string("bool") == name)
            return ctx.bool_sort();
        return enum_sorts.find(name)->second;
    }

    void mk_enum(const char *sort_name, unsigned num_values, char const * const * value_names) {
        z3::func_decl_vector cs(ctx), ts(ctx);
        z3::sort sort = ctx.enumeration_sort(sort_name, num_values, value_names, cs, ts);
        // can't use operator[] here because the value classes don't have nullary constructors
        enum_sorts.insert(std::pair<std::string, z3::sort>(sort_name,sort));
        enum_values.insert(std::pair<Z3_sort, z3::func_decl_vector>(sort,cs));
        sort_names.push_back(Z3_mk_string_symbol(ctx,sort_name));
        sorts.push_back(sort);
        for(unsigned i = 0; i < num_values; i++){
            Z3_symbol sym = Z3_mk_string_symbol(ctx,value_names[i]);
            decl_names.push_back(sym);
            decls.push_back(cs[i]);
            enum_to_int[sym] = i;
        }
    }

    void mk_bv(const char *sort_name, unsigned width) {
        z3::sort sort = ctx.bv_sort(width);
        // can't use operator[] here because the value classes don't have nullary constructors
        enum_sorts.insert(std::pair<std::string, z3::sort>(sort_name,sort));
    }

    void mk_int(const char *sort_name) {
        z3::sort sort = ctx.int_sort();
        // can't use operator[] here because the value classes don't have nullary constructors
        enum_sorts.insert(std::pair<std::string, z3::sort>(sort_name,sort));
    }

    void mk_string(const char *sort_name) {
        z3::sort sort = ctx.string_sort();
        // can't use operator[] here because the value classes don't have nullary constructors
        enum_sorts.insert(std::pair<std::string, z3::sort>(sort_name,sort));
    }

    void mk_sort(const char *sort_name) {
        Z3_symbol symb = Z3_mk_string_symbol(ctx,sort_name);
        z3::sort sort(ctx,Z3_mk_uninterpreted_sort(ctx, symb));
//        z3::sort sort = ctx.uninterpreted_sort(sort_name);
        // can't use operator[] here because the value classes don't have nullary constructors
        enum_sorts.insert(std::pair<std::string, z3::sort>(sort_name,sort));
        sort_names.push_back(symb);
        sorts.push_back(sort);
    }

    void mk_decl(const char *decl_name, unsigned arity, const char **domain_names, const char *range_name) {
        std::vector<z3::sort> domain;
        for (unsigned i = 0; i < arity; i++) {
            if (enum_sorts.find(domain_names[i]) == enum_sorts.end()) {
                std::cout << "unknown sort: " << domain_names[i] << std::endl;
                exit(1);
            }
            domain.push_back(enum_sorts.find(domain_names[i])->second);
        }
        std::string bool_name("Bool");
        z3::sort range = (range_name == bool_name) ? ctx.bool_sort() : enum_sorts.find(range_name)->second;   
        z3::func_decl decl = ctx.function(decl_name,arity,&domain[0],range);
        decl_names.push_back(Z3_mk_string_symbol(ctx,decl_name));
        decls.push_back(decl);
        decls_by_name.insert(std::pair<std::string, z3::func_decl>(decl_name,decl));
    }

    void mk_const(const char *const_name, const char *sort_name) {
        mk_decl(const_name,0,0,sort_name);
    }

    void add(const std::string &z3inp) {
        z3::expr fmla(ctx,Z3_parse_smtlib2_string(ctx, z3inp.c_str(), sort_names.size(), &sort_names[0], &sorts[0], decl_names.size(), &decl_names[0], &decls[0]));
        ctx.check_error();

        slvr.add(fmla);
    }

    bool solve() {
        // std::cout << alits.size();
        static bool show_model = true;
        if (__ivy_modelfile.is_open()) 
            __ivy_modelfile << "begin check:\\n" << slvr << "end check:\\n" << std::endl;
        while(true){
            if (__ivy_modelfile.is_open()) {
                __ivy_modelfile << "(check-sat"; 
                for (unsigned i = 0; i < alits.size(); i++)
                    __ivy_modelfile << " " << alits[i];
                __ivy_modelfile << ")" << std::endl;
            }
            z3::check_result res = slvr.check(alits.size(),&alits[0]);
            if (res != z3::unsat)
                break;
            z3::expr_vector core = slvr.unsat_core();
            if (core.size() == 0){
//                if (__ivy_modelfile.is_open()) 
//                    __ivy_modelfile << "begin unsat:\\n" << slvr << "end unsat:\\n" << std::endl;
                return false;
            }
            if (__ivy_modelfile.is_open()) 
                for (unsigned i = 0; i < core.size(); i++)
                    __ivy_modelfile << "core: " << core[i] << std::endl;
            unsigned idx = rand() % core.size();
            z3::expr to_delete = core[idx];
            if (__ivy_modelfile.is_open()) 
                __ivy_modelfile << "to delete: " << to_delete << std::endl;
            for (unsigned i = 0; i < alits.size(); i++)
                if (z3::eq(alits[i],to_delete)) {
                    alits[i] = alits.back();
                    alits.pop_back();
                    break;
                }
        }
        model = slvr.get_model();
        alits.clear();
""".replace('classname',classname))
    if target.get() != "gen":
        header.append("""
        if(__ivy_modelfile.is_open()){
            __ivy_modelfile << "begin sat:\\n" << slvr << "end sat:\\n" << std::endl;
            __ivy_modelfile << model;
            __ivy_modelfile.flush();
        }
""")
    header.append("""
        return true;
    }

    int choose(int rng, const char *name){
        if (decls_by_name.find(name) == decls_by_name.end())
            return 0;
        return eval_apply(name);
    }
};
""".replace('classname',classname))

target = iu.EnumeratedParameter("target",["impl","gen","repl","test","class"],"gen")
opt_classname = iu.Parameter("classname","")
opt_build = iu.BooleanParameter("build",False)
opt_trace = iu.BooleanParameter("trace",False)
opt_test_iters = iu.Parameter("test_iters","100")
opt_test_runs = iu.Parameter("test_runs","1")
opt_compiler = iu.EnumeratedParameter("compiler",["g++","cl","default"],"default")
opt_main = iu.Parameter("main","main")
opt_stdafx = iu.BooleanParameter("stdafx",False)
opt_outdir = iu.Parameter("outdir","")

emit_main = True

def add_conjs_to_actions():
    """
    Adds conjunctions as assertions to the module's actions and initializers.

    This function performs the following steps:
    1. Creates a list of `AssertAction` objects from the labeled conjunctions in the module.
    2. Constructs a sequence of these assertions.
    3. Updates the module's actions by appending the sequence of assertions to each public action.
    4. Adds the sequence of assertions to the module's initializers under the name "__check_invariants".
    5. Adds the sequence of assertions to the module's initial actions.

    Note:
        - The function modifies the `im.module.actions`, `im.module.initializers`, and `im.module.initial_actions` in place.
    """
    asserts = [ia.AssertAction(conj.formula).set_lineno(conj.lineno) for conj in im.module.labeled_conjs]
    seq = ia.Sequence(*asserts)
    im.module.actions = dict((actname,ia.append_to_action(action,seq)) if actname in im.module.public_actions else (actname,action)
                             for actname,action in im.module.actions.items())
    im.module.initializers.append(("__check_invariants",seq))
    seq = ia.Sequence(*asserts)
    seq.formal_params = []
    im.module.initial_actions.append(seq)
        


def main():
    main_int(False)

def ivyc():
    main_int(True)

def main_int(is_ivyc):
    """
    Main function for initializing and compiling Ivy modules to C++.

    Args:
        is_ivyc (bool): Flag indicating if the function is called from ivyc.

    This function sets various parameters and configurations for Ivy, reads
    parameters, and processes isolates. It handles different targets such as
    'repl', 'gen', 'test', and 'class'. Depending on the target and isolate,
    it generates C++ code, compiles it, and optionally builds the resulting
    binaries. The function also manages error printing and module copying
    contexts to ensure proper handling of Ivy modules and isolates.

    The function performs the following steps:
    1. Sets determinization, native enums, and sort interpretation.
    2. Configures Ivy parameters based on the target.
    3. Reads Ivy parameters and sets additional parameters.
    4. Processes isolates and generates C++ code for each isolate.
    5. Compiles and optionally builds the generated C++ code.
    6. Handles platform-specific compilation commands and library specifications.
    7. Writes process descriptors for 'repl' and 'test' targets.

    Raises:
        iu.IvyError: If the target is not 'repl' and emit_main is True for version 2 compiler.
    """
    ia.set_determinize(True)
    slv.set_use_native_enums(True)
    iso.set_interpret_all_sorts(True)
    ic.set_verifying(False)

    # set different defaults for ivyc

    if is_ivyc:
        target.set("repl")
        opt_build.set("true")

    ivy_init.read_params()
    iu.set_parameters({'coi':'false',"create_imports":'true',"enforce_axioms":'true','ui':'none','isolate_mode':'test' if target.get() == 'test' else 'compile','assume_invariants':'false'})
    if target.get() == "gen":
        iu.set_parameters({'filter_symbols':'false'})
    else:
        iu.set_parameters({'keep_destructors':'true'})
        
    if target.get() == 'class':
        target.set('repl')
        global emit_main
        emit_main = False
        
    with iu.ErrorPrinter():
        if len(sys.argv) == 2 and ic.get_file_version(sys.argv[1]) >= [2]:
            if not target.get() == 'repl' and emit_main:
                raise iu.IvyError(None,'Version 2 compiler supports only target=repl')
            cdir = os.path.join(os.path.dirname(__file__), 'ivy2/s3')
            cmd = 'IVY_INCLUDE_PATH={} {} {}'.format(os.path.join(cdir,'include'),os.path.join(cdir,'ivyc_s3'),sys.argv[1])
            print(cmd)
            sys.stdout.flush()
            status = os.system(cmd)
            exit(status)


    with im.Module():
        if target.get() == 'test':
            im.module.sig.add_symbol('_generating',il.BooleanSort())
        ivy_init.ivy_init(create_isolate=False)

        if iu.version_le(iu.get_string_version(),"1.6"):
            iso.set_interpret_all_sorts(True)

        isolate = ic.isolate.get()
# In current version
        # if is_ivyc:
        #     if isolate != None:
        #         isolates = [isolate]
        #     else:
        #         if target.get() == 'test':
        #             isolates = ['this'] # CHRIS : ERROR here, should be old version
        #         else:
        #             extracts = list((x,y) for x,y in im.module.isolates.iteritems()
        #                             if isinstance(y,ivy_ast.ExtractDef))
        #             if len(extracts) == 0:
        #                 isol = ivy_ast.ExtractDef(ivy_ast.Atom('extract'),ivy_ast.Atom('this'))
        #                 isol.with_args = 1
        #                 im.module.isolates['extract'] = isol
        #                 isolates = ['extract']
        #             else:
        #                 isolates = [ex[0] for ex in extracts]
        #             print extracts
        #         print isolates
#                    elif len(extracts) == 1:
#                        isolates = [extracts[0][0]]
# Old version 
        if is_ivyc:
            if isolate != None:
                isolates = [isolate]
            else:
                extracts = list((x,y) for x,y in im.module.isolates.items()
                                if isinstance(y,ivy_ast.ExtractDef))
                if len(extracts) == 0:
                    isol = ivy_ast.ExtractDef(ivy_ast.Atom('extract'),ivy_ast.Atom('this'))
                    isol.with_args = 1
                    im.module.isolates['extract'] = isol
                    isolates = ['extract']
                elif len(extracts) == 1:
                    isolates = [extracts[0][0]]
                print(isolates)
                print(extracts)
        else:
            if isolate != None:
                isolates = [isolate]
            else:
                if isolate == 'all':
                    if target.get() == 'repl':
                        isolates = sorted(list(m for m in im.module.isolates if isinstance(m,ivy_ast.ExtractDef)))
                    else:
                        isolates = sorted(list(m for m in im.module.isolates if not isinstance(m,ivy_ast.ExtractDef)))
                else:
                    isolates = [isolate]

                if len(isolates) == 0:
                    isolates = [None]

                if isolates == [None] and not iu.version_le(iu.get_string_version(),"1.6"):
                    isolates = ['this']

        import json
        processes = []
        mod_name = opt_classname.get() or im.module.name
        for isolate in isolates:
            with im.module.copy():
                with iu.ErrorPrinter():

                    def do_cmd(cmd):
                        print(cmd)
                        status = os.system(cmd)
                        if status:
                            exit(1)
    
                    if isolate:
                        if len(isolates) > 1:
                            print("Compiling isolate {}...".format(isolate))

                    if (not iu.version_le(iu.get_string_version(),"1.6") and
                        target.get() == 'repl' and isolate in im.module.isolates):
                        the_iso = im.module.isolates[isolate]
                        if not isinstance(the_iso,ivy_ast.ExtractDef):
                            the_iso = ivy_ast.ExtractDef(*the_iso.args)
                            the_iso.with_args = len(the_iso.args)
                            im.module.isolates[isolate] = the_iso
                        
                    # iso.compile_with_invariants.set("true" if target.get()=='test'
                    #                                 and not iu.version_le(iu.get_string_version(),"1.7")
                    #                                 else "false")

                    iso.create_isolate(isolate) # ,ext='ext'

                    if im.module.labeled_conjs:
                        add_conjs_to_actions()

                    # Tricky: cone of influence may eliminate this symbol, but
                    # run-time accesses it.
                    if '_generating' not in im.module.sig.symbols:
                        im.module.sig.add_symbol('_generating',il.BooleanSort())


                    im.module.labeled_axioms.extend(im.module.labeled_props)
                    im.module.labeled_props = []
#                    if target.get() != 'repl':
#                        ifc.check_fragment(True)
                    with im.module.theory_context():
                        basename = mod_name
                        if len(isolates) > 1:
                            basename = basename + '_' + isolate
                        classname = varname(basename).replace('-','_')
                        with ivy_cpp.CppContext():
                            header,impl = module_to_cpp_class(classname,basename)
            #        print header
            #        print impl
                    builddir = 'build' if os.path.exists('build') else '.'
                    f = open(outfile(builddir+'/'+basename+'.h'),'w')
                    f.write(header)
                    f.close()
                    f = open(outfile(builddir+'/'+basename+'.cpp'),'w')
                    f.write(impl)
                    f.close()
                if opt_build.get():
                    import platform
                    libpath = os.path.join(os.path.dirname(os.path.dirname(__file__)),'lib')
                    specfilename = os.path.join(libpath,'specs')
                    if os.path.isfile(specfilename):
                        try:
                            with open(specfilename) as inp:
                                libs = json.load(inp)
                        except:
                            sys.stderr.write('bad format in {}\n'.format(specfilename))
                            exit(1)
                    else:
                        libs = []    
                    cpp11 = any((x == 'cppstd' or x.endswith('.cppstd')) and y.rep=='cpp11' for x,y in im.module.attributes.items())
                    gpp11_spec = ' -std=c++11 ' if cpp11 else ' -std=c++11 ' 
                    libspec = ''
                    for x,y in im.module.attributes.items():
                        p,c = iu.parent_child_name(x)
                        if c == 'libspec':
                            if platform.system() == 'Windows':
                                libspec += ''.join(' {}'.format(ll) for ll in y.rep.strip('"').split(',') if ll.endswith('.lib'))
                            else:
                                libspec += ''.join(' -l' + ll for ll in y.rep.strip('"').split(',') if not ll.endswith('.lib'))
                    if platform.system() == 'Windows':
                        # if 'Z3DIR' in os.environ:
                        #     incspec = '/I %Z3DIR%\\include'
                        #     libpspec = '/LIBPATH:%Z3DIR%\\lib /LIBPATH:%Z3DIR%\\bin'
                        # else:
                        #     import z3
                        #     z3path = os.path.dirname(os.path.abspath(z3.__file__))
                        #     incspec = '/I {}'.format(z3path)
                        #     libpspec = '/LIBPATH:{}'.format(z3path)
                        _dir = os.path.dirname(os.path.abspath(__file__))
                        incspec = '/I {}'.format(os.path.join(_dir,'include'))
                        libpspec = '/LIBPATH:{}'.format(os.path.join(_dir,'lib'))
                        if not os.path.exists('libz3.dll'):
                            print('Copying libz3.dll to current directory.')
                            print('If the binary {}.exe is moved to another directory, this file must also be moved.'.format(basename))
                            do_cmd('copy {} libz3.dll'.format(os.path.join(_dir,'lib','libz3.dll')))
                        for lib in libs:
                            _incdir = lib[1] if len(lib) >= 2 else []
                            _libdir = lib[2] if len(lib) >= 3 else []
                            _incdir = [_incdir] if isinstance(_incdir,str) else _incdir
                            _libdir = [_libdir] if isinstance(_libdir,str) else _libdir
                            incspec += ''.join(' /I {} '.format(d) for d in _incdir)
                            libpspec += ''.join(' /LIBPATH:{} '.format(d) for d in _libdir)
                        vsdir = find_vs()
                        if opt_compiler.get() != 'g++':
                            cmd = '"{}\\VC\\vcvarsall.bat" amd64& cl /EHsc /Zi {}.cpp ws2_32.lib'.format(vsdir,basename)
                            if target.get() in ['gen','test']:
                                cmd = '"{}\\VC\\vcvarsall.bat" amd64& cl /MDd /EHsc /Zi {} {}.cpp ws2_32.lib libz3.lib /link {}'.format(vsdir,incspec,basename,libpspec)
                            cmd += libspec
                        else:
                            cmd = "g++ {} -I %Z3DIR%/include -L %Z3DIR%/lib -L %Z3DIR%/bin -g -o {} {}.cpp -lws2_32".format(gpp11_spec,basename,basename)
                            if target.get() in ['gen','test']:
                                cmd = cmd + ' -lz3'
                        if opt_outdir.get():
                            cmd = 'cd {} & '.format(opt_outdir.get()) + cmd
                    else:
                        if target.get() in ['gen','test']: # -Wl,
                            paths = ' '.join('-I {} -L {} -Xlinker -rpath -Xlinker {}'.format(os.path.join(_dir,'include'),os.path.join(_dir,'lib'),os.path.join(_dir,'lib')) for _dir in get_lib_dirs())
                        else:
                            paths = ''
                        for lib in libs:
                            _dir = lib[1] # -Wl,
                            _libdir = lib[2] if len(lib) >= 3 else (_dir  + '/lib')
                            paths += ' -I {}/include -L {} -Xlinker -rpath -Xlinker {}'.format(_dir,_libdir, _libdir)
                        if emit_main: #  -Wno-return-type
                            cmd = "g++ -Wno-parentheses-equality {} {} -g -o {} {}.cpp".format(gpp11_spec,paths,basename,basename)
                        else:
                            cmd = "g++ -Wno-parentheses-equality {} {} -g -c {}.cpp".format(gpp11_spec,paths,basename)
                        if target.get() in ['gen','test']:
                            cmd = cmd + ' -lz3'
                        cmd += libspec
                        cmd += ' -pthread'
                        #cmd = cmd.replace("-ldl","-lrt -ldl")
                        from os import environ
                        if environ.get('IS_NOT_DOCKER') is not None:
                            cmd += ' -D IS_NOT_DOCKER'
                            
                        if environ.get('GPERF') is not None:
                            cmd += ' -lprofiler -ltcmalloc' # CPU profiler
                    print(cmd)
                    # else:
                    #     if target.get() in ['gen','test']:
                    #         if 'Z3DIR' in os.environ:
                    #             paths = '-I $Z3DIR/include -L $Z3DIR/lib -Wl,-rpath=$Z3DIR/lib' 
                    #         else:
                    #             _dir = os.path.dirname(os.path.abspath(__file__))
                    #             paths = ' -I {} -L {} -Wl,-rpath={}'.format(os.path.join(_dir,'include'),os.path.join(_dir,'lib'),os.path.join(_dir,'lib')) # -static
                    #     else:
                    #         paths = ''
                    #     for lib in libs:
                    #         _dir = lib[1]
                    #         _libdir = lib[2] if len(lib) >= 3 else (_dir  + '/lib')
                    #         paths += ' -I {}/include -L {} -Wl,-rpath={}'.format(_dir,_libdir,_libdir)
                    #     if emit_main:
                    #         cmd = "g++ {} {} -g -o {} {}.cpp".format(gpp11_spec,paths,basename,basename)
                    #     else:
                    #         cmd = "g++ {} {} -g -c {}.cpp".format(gpp11_spec,paths,basename) # -static -lrt 
                    #     if target.get() in ['gen','test']:
                    #         cmd = cmd + ' -lz3'
                    #     cmd += libspec
                    #     cmd += ' -pthread'
                    #     cmd = cmd.replace("-ldl","-lrt -ldl")
                    #     from os import environ
                    #     if environ.get('IS_NOT_DOCKER') is not None:
                    #         cmd += ' -D IS_NOT_DOCKER'
                            
                    #     if environ.get('GPERF') is not None:
                    #         cmd += ' -lprofiler -ltcmalloc' # CPU profiler
                    # print cmd
                    sys.stdout.flush()
                    with iu.WorkingDir(builddir):
                        status = os.system(cmd)
                        if status:
                            exit(1)
                        if target.get() in ['repl','test'] and not iu.version_le(iu.get_string_version(),"1.6"):
                            def describe_params(params,defaults):
                                res = []
                                for param,default in zip(params,defaults):
                                    desc = {}
                                    if isinstance(param,ivy_ast.App):
                                        desc['name'] = param.rep
                                    else:
                                        desc['name'] = param.name
                                    sort_desc = {}
                                    param_sort = il.find_sort(param.sort) if isinstance(param.sort,str) else param.sort
                                    if il.is_function_sort(param_sort):
                                        sort_desc['name'] = str(param_sort.rng)
                                        sort_desc['indices'] = describe_params(variables(param_sort.dom),[None for x in param_sort.dom] )
                                        desc['type'] = sort_desc
                                    else:
                                        desc['type'] = str(param.sort)
                                    if default is not None:
                                        desc['default'] = str(default)
                                    itp = il.sig.interp.get(str(param.sort),None)
                                    def bound_val(b):
                                        if b.is_numeral():
                                            return int(b.name)
                                        return b.name
                                    if isinstance(itp,il.RangeSort):
                                        desc['range'] = [bound_val(itp.lb),bound_val(itp.ub)]
                                    res.append(desc)
                                return res
                            descriptor = {}
                            descriptor['binary'] = basename
                            descriptor['name'] = str(isolate)
                            if isolate in im.module.isolates:
                                the_iso = im.module.isolates[isolate]
                                params = [p.to_const('iso:') if isinstance(p,ivy_ast.Variable) else p for p in the_iso.params()]
                                descriptor['indices'] = describe_params(params,[None for x in the_iso.params()])
                            descriptor['params'] = describe_params(im.module.params,im.module.param_defaults)
                            processes.append(descriptor)
        if target.get() in ['repl','test']:
            # print 'descriptor:{}'.format(descriptor)
            try:
                descriptor = {'processes' : processes}
                if target.get() == 'test':
                    descriptor['test_params'] = ['iters','runs','seed','delay','wait','modelfile']
                with open(mod_name + '.dsc','w') as dscf:
                    json.dump(descriptor,dscf)
            except:
                sys.stderr.write('cannot write to file: {}\n'.format(mod_name + '.dsc'))
                exit(1)

def outfile(name):
    return (opt_outdir.get() + '/' + name) if opt_outdir.get() else name
        
def find_vs():
    try:
        windir = os.getenv('WINDIR')
        drive = windir[0]
    except:
        drive = 'C'
    for v in range(15,9,-1):
        for w in ['',' (x86)']:
            dir = '{}:\\Program Files{}\\Microsoft Visual Studio {}.0'.format(drive,w,v)
            if os.path.exists(dir):
                return dir
    raise iu.IvyError(None,'Cannot find a suitable version of Visual Studio (require 10.0-15.0)')

if __name__ == "__main__":
    main_int(True)
        
hash_h = """
/*++
  Copyright (c) Microsoft Corporation

  This hash template is borrowed from Microsoft Z3
  (https://github.com/Z3Prover/z3).

  Simple implementation of bucket-list hash tables conforming roughly
  to SGI hash_map and hash_set interfaces, though not all members are
  implemented.

  These hash tables have the property that insert preserves iterators
  and references to elements.

  This package lives in namespace hash_space. Specializations of
  class "hash" should be made in this namespace.

  --*/

#pragma once

#ifndef HASH_H
#define HASH_H

#ifdef _WINDOWS
#pragma warning(disable:4267)
#endif

#include <string>
#include <vector>
#include <map>
#include <iterator>
#include <fstream>

namespace hash_space {

    unsigned string_hash(const char * str, unsigned length, unsigned init_value);

    template <typename T> class hash {
    public:
        size_t operator()(const T &s) const {
            return s.__hash();
        }
    };

    template <>
        class hash<int> {
    public:
        size_t operator()(const int &s) const {
            return s;
        }
    };

    template <>
        class hash<long long> {
    public:
        size_t operator()(const long long &s) const {
            return s;
        }
    };

    template <>
        class hash<unsigned> {
    public:
        size_t operator()(const unsigned &s) const {
            return s;
        }
    };

    template <>
        class hash<unsigned long long> {
    public:
        size_t operator()(const unsigned long long &s) const {
            return s;
        }
    };

    template <>
        class hash<bool> {
    public:
        size_t operator()(const bool &s) const {
            return s;
        }
    };

    template <>
        class hash<std::string> {
    public:
        size_t operator()(const std::string &s) const {
            return string_hash(s.c_str(), (unsigned)s.size(), 0);
        }
    };

    template <>
        class hash<std::pair<int,int> > {
    public:
        size_t operator()(const std::pair<int,int> &p) const {
            return p.first + p.second;
        }
    };

    template <typename T>
        class hash<std::vector<T> > {
    public:
        size_t operator()(const std::vector<T> &p) const {
            hash<T> h;
            size_t res = 0;
            for (unsigned i = 0; i < p.size(); i++)
                res += h(p[i]);
            return res;
        }
    };

    template <typename K, typename V>
        class hash<std::map<K,V> > {
    public:
        size_t operator()(const std::map<K,V> &p) const {
            hash<K> hk;
            hash<V> hv;
            size_t res = 0;
            for (typename std::map<K,V>::const_iterator it = p.begin(), en = p.end(); it != en; ++it)
                res += hk(it->first) + hv(it->second);
            return res;
        }
    };

    template <class T>
        class hash<std::pair<T *, T *> > {
    public:
        size_t operator()(const std::pair<T *,T *> &p) const {
            return (size_t)p.first + (size_t)p.second;
        }
    };

    template <class T>
        class hash<T *> {
    public:
        size_t operator()(T * const &p) const {
            return (size_t)p;
        }
    };

    enum { num_primes = 29 };

    static const unsigned long primes[num_primes] =
        {
            7ul,
            53ul,
            97ul,
            193ul,
            389ul,
            769ul,
            1543ul,
            3079ul,
            6151ul,
            12289ul,
            24593ul,
            49157ul,
            98317ul,
            196613ul,
            393241ul,
            786433ul,
            1572869ul,
            3145739ul,
            6291469ul,
            12582917ul,
            25165843ul,
            50331653ul,
            100663319ul,
            201326611ul,
            402653189ul,
            805306457ul,
            1610612741ul,
            3221225473ul,
            4294967291ul
        };

    inline unsigned long next_prime(unsigned long n) {
        const unsigned long* to = primes + (int)num_primes;
        for(const unsigned long* p = primes; p < to; p++)
            if(*p >= n) return *p;
        return primes[num_primes-1];
    }

    template<class Value, class Key, class HashFun, class GetKey, class KeyEqFun>
        class hashtable
    {
    public:

        typedef Value &reference;
        typedef const Value &const_reference;
    
        struct Entry
        {
            Entry* next;
            Value val;
      
        Entry(const Value &_val) : val(_val) {next = 0;}
        };
    

        struct iterator
        {      
            Entry* ent;
            hashtable* tab;

            typedef std::forward_iterator_tag iterator_category;
            typedef Value value_type;
            typedef std::ptrdiff_t difference_type;
            typedef size_t size_type;
            typedef Value& reference;
            typedef Value* pointer;

        iterator(Entry* _ent, hashtable* _tab) : ent(_ent), tab(_tab) { }

            iterator() { }

            Value &operator*() const { return ent->val; }

            Value *operator->() const { return &(operator*()); }

            iterator &operator++() {
                Entry *old = ent;
                ent = ent->next;
                if (!ent) {
                    size_t bucket = tab->get_bucket(old->val);
                    while (!ent && ++bucket < tab->buckets.size())
                        ent = tab->buckets[bucket];
                }
                return *this;
            }

            iterator operator++(int) {
                iterator tmp = *this;
                operator++();
                return tmp;
            }


            bool operator==(const iterator& it) const { 
                return ent == it.ent;
            }

            bool operator!=(const iterator& it) const {
                return ent != it.ent;
            }
        };

        struct const_iterator
        {      
            const Entry* ent;
            const hashtable* tab;

            typedef std::forward_iterator_tag iterator_category;
            typedef Value value_type;
            typedef std::ptrdiff_t difference_type;
            typedef size_t size_type;
            typedef const Value& reference;
            typedef const Value* pointer;

        const_iterator(const Entry* _ent, const hashtable* _tab) : ent(_ent), tab(_tab) { }

            const_iterator() { }

            const Value &operator*() const { return ent->val; }

            const Value *operator->() const { return &(operator*()); }

            const_iterator &operator++() {
                const Entry *old = ent;
                ent = ent->next;
                if (!ent) {
                    size_t bucket = tab->get_bucket(old->val);
                    while (!ent && ++bucket < tab->buckets.size())
                        ent = tab->buckets[bucket];
                }
                return *this;
            }

            const_iterator operator++(int) {
                const_iterator tmp = *this;
                operator++();
                return tmp;
            }


            bool operator==(const const_iterator& it) const { 
                return ent == it.ent;
            }

            bool operator!=(const const_iterator& it) const {
                return ent != it.ent;
            }
        };

    private:

        typedef std::vector<Entry*> Table;

        Table buckets;
        size_t entries;
        HashFun hash_fun ;
        GetKey get_key;
        KeyEqFun key_eq_fun;
    
    public:

    hashtable(size_t init_size) : buckets(init_size,(Entry *)0) {
            entries = 0;
        }
    
        hashtable(const hashtable& other) {
            dup(other);
        }

        hashtable& operator= (const hashtable& other) {
            if (&other != this)
                dup(other);
            return *this;
        }

        ~hashtable() {
            clear();
        }

        size_t size() const { 
            return entries;
        }

        bool empty() const { 
            return size() == 0;
        }

        void swap(hashtable& other) {
            buckets.swap(other.buckets);
            std::swap(entries, other.entries);
        }
    
        iterator begin() {
            for (size_t i = 0; i < buckets.size(); ++i)
                if (buckets[i])
                    return iterator(buckets[i], this);
            return end();
        }
    
        iterator end() { 
            return iterator(0, this);
        }

        const_iterator begin() const {
            for (size_t i = 0; i < buckets.size(); ++i)
                if (buckets[i])
                    return const_iterator(buckets[i], this);
            return end();
        }
    
        const_iterator end() const { 
            return const_iterator(0, this);
        }
    
        size_t get_bucket(const Value& val, size_t n) const {
            return hash_fun(get_key(val)) % n;
        }
    
        size_t get_key_bucket(const Key& key) const {
            return hash_fun(key) % buckets.size();
        }

        size_t get_bucket(const Value& val) const {
            return get_bucket(val,buckets.size());
        }

        Entry *lookup(const Value& val, bool ins = false)
        {
            resize(entries + 1);

            size_t n = get_bucket(val);
            Entry* from = buckets[n];
      
            for (Entry* ent = from; ent; ent = ent->next)
                if (key_eq_fun(get_key(ent->val), get_key(val)))
                    return ent;
      
            if(!ins) return 0;

            Entry* tmp = new Entry(val);
            tmp->next = from;
            buckets[n] = tmp;
            ++entries;
            return tmp;
        }

        Entry *lookup_key(const Key& key) const
        {
            size_t n = get_key_bucket(key);
            Entry* from = buckets[n];
      
            for (Entry* ent = from; ent; ent = ent->next)
                if (key_eq_fun(get_key(ent->val), key))
                    return ent;
      
            return 0;
        }

        const_iterator find(const Key& key) const {
            return const_iterator(lookup_key(key),this);
        }

        iterator find(const Key& key) {
            return iterator(lookup_key(key),this);
        }

        std::pair<iterator,bool> insert(const Value& val){
            size_t old_entries = entries;
            Entry *ent = lookup(val,true);
            return std::pair<iterator,bool>(iterator(ent,this),entries > old_entries);
        }
    
        iterator insert(const iterator &it, const Value& val){
            Entry *ent = lookup(val,true);
            return iterator(ent,this);
        }

        size_t erase(const Key& key)
        {
            Entry** p = &(buckets[get_key_bucket(key)]);
            size_t count = 0;
            while(*p){
                Entry *q = *p;
                if (key_eq_fun(get_key(q->val), key)) {
                    ++count;
                    *p = q->next;
                    delete q;
                }
                else
                    p = &(q->next);
            }
            entries -= count;
            return count;
        }

        void resize(size_t new_size) {
            const size_t old_n = buckets.size();
            if (new_size <= old_n) return;
            const size_t n = next_prime(new_size);
            if (n <= old_n) return;
            Table tmp(n, (Entry*)(0));
            for (size_t i = 0; i < old_n; ++i) {
                Entry* ent = buckets[i];
                while (ent) {
                    size_t new_bucket = get_bucket(ent->val, n);
                    buckets[i] = ent->next;
                    ent->next = tmp[new_bucket];
                    tmp[new_bucket] = ent;
                    ent = buckets[i];
                }
            }
            buckets.swap(tmp);
        }
    
        void clear()
        {
            for (size_t i = 0; i < buckets.size(); ++i) {
                for (Entry* ent = buckets[i]; ent != 0;) {
                    Entry* next = ent->next;
                    delete ent;
                    ent = next;
                }
                buckets[i] = 0;
            }
            entries = 0;
        }

        void dup(const hashtable& other)
        {
            clear();
            buckets.resize(other.buckets.size());
            for (size_t i = 0; i < other.buckets.size(); ++i) {
                Entry** to = &buckets[i];
                for (Entry* from = other.buckets[i]; from; from = from->next)
                    to = &((*to = new Entry(from->val))->next);
            }
            entries = other.entries;
        }
    };

    template <typename T> 
        class equal {
    public:
        bool operator()(const T& x, const T &y) const {
            return x == y;
        }
    };

    template <typename T>
        class identity {
    public:
        const T &operator()(const T &x) const {
            return x;
        }
    };

    template <typename T, typename U>
        class proj1 {
    public:
        const T &operator()(const std::pair<T,U> &x) const {
            return x.first;
        }
    };

    template <typename Element, class HashFun = hash<Element>, 
        class EqFun = equal<Element> >
        class hash_set
        : public hashtable<Element,Element,HashFun,identity<Element>,EqFun> {

    public:

    typedef Element value_type;

    hash_set()
    : hashtable<Element,Element,HashFun,identity<Element>,EqFun>(7) {}
    };

    template <typename Key, typename Value, class HashFun = hash<Key>, 
        class EqFun = equal<Key> >
        class hash_map
        : public hashtable<std::pair<Key,Value>,Key,HashFun,proj1<Key,Value>,EqFun> {

    public:

    hash_map()
    : hashtable<std::pair<Key,Value>,Key,HashFun,proj1<Key,Value>,EqFun>(7) {}

    Value &operator[](const Key& key) {
	std::pair<Key,Value> kvp(key,Value());
	return 
	hashtable<std::pair<Key,Value>,Key,HashFun,proj1<Key,Value>,EqFun>::
        lookup(kvp,true)->val.second;
    }
    };

    template <typename D,typename R>
        class hash<hash_map<D,R> > {
    public:
        size_t operator()(const hash_map<D,R> &p) const {
            hash<D > h1;
            hash<R > h2;
            size_t res = 0;
            
            for (typename hash_map<D,R>::const_iterator it=p.begin(), en=p.end(); it!=en; ++it)
                res += (h1(it->first)+h2(it->second));
            return res;
        }
    };

    template <typename D,typename R>
    inline bool operator ==(const hash_map<D,R> &s, const hash_map<D,R> &t){
        for (typename hash_map<D,R>::const_iterator it=s.begin(), en=s.end(); it!=en; ++it) {
            typename hash_map<D,R>::const_iterator it2 = t.find(it->first);
            if (it2 == t.end() || !(it->second == it2->second)) return false;
        }
        for (typename hash_map<D,R>::const_iterator it=t.begin(), en=t.end(); it!=en; ++it) {
            typename hash_map<D,R>::const_iterator it2 = s.find(it->first);
            if (it2 == t.end() || !(it->second == it2->second)) return false;
        }
        return true;
    }
}
#endif
"""

hash_cpp = """
/*++
Copyright (c) Microsoft Corporation

This string hash function is borrowed from Microsoft Z3
(https://github.com/Z3Prover/z3). 

--*/


#define mix(a,b,c)              \\
{                               \\
  a -= b; a -= c; a ^= (c>>13); \\
  b -= c; b -= a; b ^= (a<<8);  \\
  c -= a; c -= b; c ^= (b>>13); \\
  a -= b; a -= c; a ^= (c>>12); \\
  b -= c; b -= a; b ^= (a<<16); \\
  c -= a; c -= b; c ^= (b>>5);  \\
  a -= b; a -= c; a ^= (c>>3);  \\
  b -= c; b -= a; b ^= (a<<10); \\
  c -= a; c -= b; c ^= (b>>15); \\
}

#ifndef __fallthrough
#define __fallthrough
#endif

namespace hash_space {

// I'm using Bob Jenkin's hash function.
// http://burtleburtle.net/bob/hash/doobs.html
unsigned string_hash(const char * str, unsigned length, unsigned init_value) {
    unsigned a, b, c, len;

    /* Set up the internal state */
    len = length;
    a = b = 0x9e3779b9;  /* the golden ratio; an arbitrary value */
    c = init_value;      /* the previous hash value */

    /*---------------------------------------- handle most of the key */
    while (len >= 12) {
        a += reinterpret_cast<const unsigned *>(str)[0];
        b += reinterpret_cast<const unsigned *>(str)[1];
        c += reinterpret_cast<const unsigned *>(str)[2];
        mix(a,b,c);
        str += 12; len -= 12;
    } 

    /*------------------------------------- handle the last 11 bytes */
    c += length;
    switch(len) {        /* all the case statements fall through */
    case 11: 
        c+=((unsigned)str[10]<<24);
        __fallthrough;
    case 10: 
        c+=((unsigned)str[9]<<16);
        __fallthrough;
    case 9 : 
        c+=((unsigned)str[8]<<8);
        __fallthrough;
        /* the first byte of c is reserved for the length */
    case 8 : 
        b+=((unsigned)str[7]<<24);
        __fallthrough;
    case 7 : 
        b+=((unsigned)str[6]<<16);
        __fallthrough;
    case 6 : 
        b+=((unsigned)str[5]<<8);
        __fallthrough;
    case 5 : 
        b+=str[4];
        __fallthrough;
    case 4 : 
        a+=((unsigned)str[3]<<24);
        __fallthrough;
    case 3 : 
        a+=((unsigned)str[2]<<16);
        __fallthrough;
    case 2 : 
        a+=((unsigned)str[1]<<8);
        __fallthrough;
    case 1 : 
        a+=str[0];
        __fallthrough;
        /* case 0: nothing left to add */
    }
    mix(a,b,c);
    /*-------------------------------------------- report the result */
    return c;
}

}

"""
