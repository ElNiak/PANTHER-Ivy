#
# Copyright (c) Microsoft Corporation. All Rights Reserved.
#

from . import ivy_module as im
from . import ivy_actions as ia
from . import ivy_logic as il
from . import ivy_transrel as tr
from . import ivy_logic_utils as ilu
from . import ivy_utils as iu
from . import ivy_art as art
from . import ivy_interp as itp
from . import ivy_theory as thy
from . import ivy_ast
from . import ivy_proof as ipr
from . import ivy_trace

import tempfile
import subprocess
from collections import defaultdict
import itertools
import sys
import os

verbose = True
logfile = None

# Expand the axiom schemata into axioms, for a given collection of
# function and constant symbols.

class Match(object):
    def __init__(self):
        self.stack = [[]]
        self.map = dict()
    def add(self,x,y):
        self.map[x] = y
        self.stack[-1].append(x)
    def push(self):
        self.stack.append([])
    def pop(self):
        for x in self.stack.pop():
            del self.map[x]
    def unify(self,x,y):
        if x not in self.map:
            if x.name.endswith('_finite') and not is_finite_sort(y):
                return False  # 
            self.add(x,y)
            return True
        return self.map[x] == y
    def unify_lists(self,xl,yl):
        if len(xl) != len(yl):
            return False
        for x,y in zip(xl,yl):
            if not self.unify(x,y):
                return False
        return True
    

def str_map(map):
    return '{' + ','.join('{}:{}'.format(x,y) for x,y in map.items()) + '}'

def match_schema_prems(prems,sort_constants,funs,match,bound_sorts):
    if len(prems) == 0:
        yield match.map.copy()
    else:
        prem = prems.pop()
        if isinstance(prem,ivy_ast.ConstantDecl):
            sym = prem.args[0]
            if il.is_function_sort(sym.sort):
                sorts = sym.sort.dom + (sym.sort.rng,)
                for f in funs:
                    fsorts = f.sort.dom + (f.sort.rng,)
                    match.push()
                    for s in sorts:
                        if s not in bound_sorts and s not in match.map:
                            match.add(s,s)
                    if match.unify_lists(sorts,fsorts):
                        match.add(sym,f)
                        for m in match_schema_prems(prems,sort_constants,funs,match,bound_sorts):
                            yield m
                    match.pop()
            else:
                if sym.sort in match.map or sym.sort not in bound_sorts:
                    cands = sort_constants[match.map.get(sym.sort,sym.sort)]
                else:
                    cands = [s for v in list(sort_constants.values()) for s in v]
                for cand in cands:
                    match.push()
                    if match.unify(sym.sort,cand.sort):
                        match.add(sym,cand)
                        for m in match_schema_prems(prems,sort_constants,funs,match,bound_sorts):
                            yield m
                    match.pop()
        elif isinstance(prem,il.UninterpretedSort):
            for m in match_schema_prems(prems,sort_constants,funs,match,bound_sorts):
                yield m
        prems.append(prem)
            
def apply_match(match,fmla):
    """ apply a match to a formula. 

    In effect, substitute all symbols in the match with the
    corresponding lambda terms and apply beta reduction
    """

    args = [apply_match(match,f) for f in fmla.args]
    if il.is_app(fmla):
        if fmla.rep in match:
            func = match[fmla.rep]
            return func(*args)
    elif il.is_binder(fmla):
        vs = [apply_match(match,v) for v in fmla.variables]
        return fmla.clone_binder(vs,apply_match(match,fmla.body))
    elif il.is_variable(fmla):
        return il.Variable(fmla.name,match.get(fmla.sort,fmla.sort))
    return fmla.clone(args)

def expand_schemata(mod,sort_constants,funs):
    match = Match()
    res = []
    for s in list(mod.sig.sorts.values()):
        if not il.is_function_sort(s):
            match.add(s,s)
    for name,lf in mod.schemata.items():
        schema = lf.formula
        if any(name.startswith(pref) for pref in ['rec[','lep[','ind[']):
            continue
        conc = schema.args[-1]
        prems = list(schema.args[:-1])
        bound_sorts = [s for s in prems if isinstance(s,il.UninterpretedSort)]
        for m in match_schema_prems(prems,sort_constants,funs,match,bound_sorts):
            # print ('m: {}'.format(str_map(m)))
            # print ('conc: {}'.format(conc))
            inst = apply_match(m,conc)
            res.append(ivy_ast.LabeledFormula(ivy_ast.Atom(name),inst))
    return res
                
# Here we deal with normalizing of terms. In particular, we order the
# equalities and convert x = x to true. This means we don't have to
# axiomatize symmetry and reflexivity. We assume terms we normalize
# are ground.

def term_ord(x,y):
    t1,t2 = str(type(x)),str(type(y))
    if t1 < t2:
        return -1
    if t1 > t2:
        return 1
    if il.is_app(x):
        if x.rep.name < y.rep.name:
            return -1
        if x.rep.name > y.rep.name:
            return 1
    l1,l2 = len(x.args),len(y.args)
    if l1 < l2:
        return -1
    if l1 > l2:
        return 1
    for x1,y1 in zip(x.args,y.args):
        res = term_ord(x1,y1)
        if res != 0:
            return res
    return 0

def clone_normal(expr,args):
    if il.is_eq(expr):
        x,y = args
        if x == y:
            return il.And()
        to = term_ord(x,y)
#        print 'term_ord({},{}) = {}'.format(x,y,to)
        if to == 1:
            x,y = y,x
        return expr.clone([x,y])
    return expr.clone(args)

def normalize(expr):
    if il.is_macro(expr):
        return normalize(il.expand_macro(expr))
    return clone_normal(expr,list(map(normalize,expr.args)))

def merge_match_lists(match_lists):
    res = []
    def try_merge(i,mp,mpi):
        mpo = mp.copy()
        for x,y in mpi.items():
            if x in mpo:
                if y != mpo[x]:
                    return
            else:
                mpo[x] = y
        recur(i+1,mpo)

    def recur(i,mp):
        if i == len(match_lists):
            res.append(mp)
        else:
            for mpi in match_lists[i]:
                try_merge(i,mp,mpi)
    recur(0,dict())
    return res

            
# This is where we do pattern-based eager instantiation of the axioms

def instantiate_axioms(mod,fmlas,triggers):

    global logfile
    if logfile is None:
        logfile_name = 'ivy_aut_inst.log'
        logfile = open(logfile_name,'w')

    sort_constants = defaultdict(list)
    syms = set()
    for fmla in fmlas:
        syms.update(ilu.used_symbols_ast(fmla))
    funs = set(sym for sym in syms if  il.is_function_sort(sym.sort))
    for c in syms:
        if not il.is_function_sort(c.sort):
            sort_constants[c.sort].append(c)

    # Expand the axioms schemata into axioms

    if verbose:
        print('Expanding schemata...')
    axioms = mod.labeled_axioms + expand_schemata(mod,sort_constants,funs)
    for a in axioms:
        logfile.write('axiom {}\n'.format(a))

    if verbose:
        print('Instantiating axioms...')
    
    # Get all the triggers. For now only automatic triggers

    def get_trigger(expr,vs):
        if il.is_quantifier(expr) or il.is_variable(expr):
            return None
        for a in expr.args:
            r = get_trigger(a,vs)
            if r is not None:
                return r
        if il.is_app(expr) or il.is_eq(expr):
            evs = ilu.used_variables_ast(expr)
            if all(v in evs for v in vs):
                return expr

#     triggers = []
#     for ax in axioms:
#         fmla = ax.formula
#         vs = list(ilu.used_variables_ast(fmla))
#         if vs:
#             trig = get_trigger(fmla,vs)
#             if trig is not None:
# #                iu.dbg('trig')
# #                iu.dbg('ax')
#                 print ('trig: {}, ax: {}'.format(trig,ax))
#                 triggers.append(([trig],ax))

    insts = set()
    global inst_list # python lamemess -- should be local but inner function cannot access
    inst_list = []

    def match(pat,expr,mp):
        if il.is_variable(pat):
            if pat in mp:
                return expr == mp[pat]
            mp[pat] = expr
            return True
        if il.is_app(pat):
            return (il.is_app(expr) and pat.rep == expr.rep
                    and all(match(x,y,mp) for x,y in zip(pat.args,expr.args)))
        if il.is_quantifier(pat):
            return False
        if type(pat) is not type(expr):
            return False
        if il.is_eq(expr):
            px,py = pat.args
            ex,ey = expr.args
            if px.sort != ex.sort:
                return False
            save = mp.copy()
            if match(px,ex,mp) and match(py,ey,mp):
                return True
            mp.clear()
            mp.update(save)
            return match(px,ey,mp) and match(py,ex,mp)
        return all(match(x,y,mp) for x,y in zip(pat.args,expr.args))
                                                                

    # TODO: make sure matches are ground
    def recur(expr,trig,res):
        for e in expr.args:
            recur(e,trig,res)
        mp = dict()
        if match(trig,expr,mp):
            res.append(mp)

    def trigger_matches(fmlas,trig):
        res = []
        for f in fmlas:
            recur(f,trig,res)
        return res

    # match triggers against the formulas
    for trigs,ax in triggers:
        trig_matches = [trigger_matches(fmlas,trig) for trig in trigs]
        matches = merge_match_lists(trig_matches)
        for mp in matches:
            # fmla = normalize(il.substitute(ax.formula,mp))
            fmla = il.substitute(ax.formula,mp)
            if fmla not in insts:
                insts.add(fmla)
                inst_list.append((ax,fmla))
                    
    for f in inst_list:
        logfile.write('    {}\n'.format(f))
    return inst_list

def auto_inst(self,decls,proof):
    goal = decls[0]
    conc = ipr.goal_conc(goal)

    triggers = []
    axmap = dict((ax.label.rep,ax) for ax in im.module.labeled_axioms)
    for decl in proof.tactic_decls:
        if isinstance(decl,ivy_ast.Trigger):
            trigger = ipr.compile_with_goal_vocab(decl,goal)
            axname = trigger.args[0].rep
            if axname not in axmap:
                raise iu.IvyError(trigger,'property ' + axname + ' not found')
            ax = axmap[axname]
            trigs = trigger.args[1:]
            triggers.append((trigs,ax))
        else:
            raise iu.IvyError(decl,'tactic does not take this type of argument')

    fmlas = [ipr.goal_conc(g) for g in ipr.goal_prems(goal) if ipr.is_goal(g)] + [conc]
    instances = instantiate_axioms(im.module,fmlas,triggers)

    used_names = set(x.label.rep for x in ipr.goal_prems(goal) if hasattr(x,'label'))
    used_names.update(axmap)
    renamer = iu.UniqueRenamer(used = used_names)

    prems = list(ipr.goal_prems(goal))
    
    for ax,fmla in instances:
        inst = ax.clone([ivy_ast.Atom(renamer(ax.label.rep)),fmla])
        inst.explicit = False
        prems.append(inst)

    goal = ipr.clone_goal(goal,prems,conc)
    return [goal] + decls[1:]
    
ipr.register_tactic('auto_inst',auto_inst)
