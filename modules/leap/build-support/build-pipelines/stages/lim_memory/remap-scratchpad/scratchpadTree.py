# python libraries
import math
import operator
import random

# AWB dependencies
from scratchpadModules import Scratchpad, ScratchpadPlatform, ScratchpadTreeNode, ScratchpadTreeLeaf
from li_module import LIModule, LIChain, LIService

def constructScratchpadTreeTopology(clients, treeKary, treeMode):
    gurobiDisabled = False
    try:
        import gurobipy
    except ImportError:
        gurobiDisabled = True
        print "Use default tree building function since gurobipy is not available."
        pass
    if len(clients) <= treeKary: # special case: flat tree
        return clients, [len(clients)], []
    elif (gurobiDisabled and treeMode == 0) or (len(clients[0].weightVals) == 0 and treeMode == 0) or treeMode == 2: 
        return constructTreeTopologyUsingDP(clients, treeKary)
    elif treeMode == 1 or treeMode == 3:
        return constructBalancedTreeTopology(clients, treeKary)
    else: 
        print "Build minimum latency tree using Gurobi solver"
        # build ILP tree model
        K = treeKary                                          # max number of children
        D = (len(clients)-2)/(K-1) + 1                        # max depth
        P = D*(K-1) + 1 - len(clients)                        # number of dummy clients
        D = min(D,len(clients[0].weightVals))                 # reduce max depth if clients have less weight values 
        N = P + len(clients)                                  # number of leaves after adding dummies
        
        print "K=%d, D=%d, P=%d, N=%d" % (K, D, P, N)
       
        class DummyClient():
            def __init__(self):
                self.weightVals = [float(1)]*D
                self.id = "dummy"
        
        new_clients = clients + [DummyClient() for x in range(P)]
        # client weight function in depth (Note that solver has tolerance 1.00e-04)
        weightFunc = lambda n,d: float("inf") if d == 0 else (float(new_clients[n].weightVals[d-1])-1)*1000   
    
        m = gurobipy.Model()
    
        # variables 
        z = [[m.addVar(vtype=gurobipy.GRB.BINARY) for d in range(D+1)] for n in range(N)]  # z[n][d] = whether leaf n is at depth d
        x = [m.addVar() for d in range(D+1)]  # number of depth-d leaf nodes
        y = [m.addVar() for d in range(D+1)]  # number of depth-d internal nodes 
        m.update()
    
        # constraints: 
        for n in range(N): 
            m.addConstr( gurobipy.quicksum(z[n]) == 1 ) # each leaf has a unique depth
        
        for d in range(D+1): 
            m.addConstr( gurobipy.quicksum([ z[n][d] for n in range(N) ]) == x[d] ) # there are x[d] leaf nodes at depth d
        
        m.addConstr( (y[0] + x[0]) == 1 )            # only one node at root (depth 0)
        for d in range(1,D+1): 
            m.addConstr( (y[d] + x[d]) == K*y[d-1] ) # each internal node has exactly K children
        m.addConstr( y[D] == 0 )                     # no internal nodes at bottom
        
        # objective
        m.setObjective( gurobipy.quicksum([ gurobipy.quicksum([ weightFunc(n,d)*z[n][d] for d in range(D+1) ]) for n in range(N) ]) )
        
        # optimize
        m.optimize()
        
        # show results
        print 'x = ' + str([i.x for i in x])
        print 'y = ' + str([i.x for i in y])

        for d in range(D+1): 
            print 'Depth', d, ':', [new_clients[n].id for n in range(N) if z[n][d].x==1] + ['x']*int(round(y[d].x))
        
        # sort clients based on the depth assignment (from small depth to large)
        sorted_clients = []
        for d in range(1,D+1):
            sorted_clients += [new_clients[n] for n in range(N) if z[n][d].x == 1 and new_clients[n].id != "dummy"]
        
        num_leaves = [int(round(x[d].x)) for d in range(1,D+1) ]
        # remove dummies
        num_leaves[-1] -= P
        num_internals = [int(round(y[d].x)) for d in range(1,D) ]
        
        return sorted_clients, num_leaves, num_internals


def constructBalancedTreeTopology(clients, treeKary):    
    print "Build balanced tree"
    K = treeKary
    clients.sort(key=lambda x: x.latency, reverse=True)
    total_leaves = len(clients)
    depth = int(math.ceil(math.log(total_leaves,K))) # depth >= 2 since total_leaves > K
    
    # determine the number of leaf nodes and internal nodes at each depth
    num_leaves = [0]*depth
    num_internals = [K]*(depth-1)

    # leaf nodes can only be placed at the bottom two levels of a balanced tree
    num_leaves[depth-2] = int(math.pow(K, depth-1))
    ret = total_leaves - num_leaves[depth-2]
    internals = int(math.ceil(float(ret)/K))
    while num_leaves[depth-2] + internals > int(math.pow(K, depth-1)):
        num_leaves[depth-2] = int(math.pow(K, depth-1)) - internals
        ret = total_leaves - num_leaves[depth-2]
        internals = int(math.ceil(float(ret)/K))
    num_leaves[depth-1] = ret
    num_internals[depth-2] = internals
 
    return clients, num_leaves, num_internals

def constructTreeTopologyUsingDP(clients, treeKary):    
    
    print "Build minimum latency tree using dynamic programming (assume linear weight functions)"
    
    clients.sort(key=lambda x: x.latency, reverse=True)
    
    K = treeKary                               # max number of children
    D = (len(clients)-2)/(K-1) + 1             # max depth
    P = D*(K-1) + 1 - len(clients)             # number of dummy clients
    N = P + len(clients)                       # number of leaves after adding dummies
    print "K=%d, D=%d, P=%d, N=%d" % (K, D, P, N)
    a = [x.latency for x in clients] + [0] * P # slope of weight functions

    # v[d][b][n]: cost matrix
    v = [[[ float("inf") for n in range(N) ] for b in range(min(int(math.ceil(float(N)/K)),int(math.pow(K,d))))] for d in range(D)]
    
    # x[b][n]: number of leaf nodes at each depth 
    leaves = [[ [0]*D for n in range(N) ] for b in range(min(int(math.ceil(float(N)/K)),int(math.pow(K,D-1))))] 
    
    # base case
    for b_idx in range(min(int(math.ceil(float(N)/K)),int(math.pow(K,D-1)))):
        for n_idx in range(N):
            b = (b_idx + 1)*K
            n = n_idx + 1
            if b >= n: 
                v[D-1][b_idx][n_idx] = sum(a[N-n:])*D
                leaves[b_idx][n_idx] = [n]

    # iteration
    for d in range(D-1,0,-1):
        new_leaves = [[ [0]*D for n in range(N) ] for b in range(min(int(math.ceil(float(N)/K)),int(math.pow(K,D-1))))] 
        for b_idx in range(min(int(math.ceil(float(N)/K)),int(math.pow(K,d-1)))):
            for n_idx in range(N):
                b = (b_idx + 1)*K
                n = n_idx + 1
                if b >= n: 
                    v[d-1][b_idx][n_idx] = sum(a[N-n:])*d
                    new_leaves[b_idx][n_idx] = [n]
                else:
                    candidates = []
                    for x in range(b): 
                        if (b-x)*K >= (n-x): # rest leaf nodes are at depth d+1
                            val = sum(a[N-n:N-n+x])*d + sum(a[N-n+x:])*(d+1)
                        else: 
                            val = sum(a[N-n:N-n+x])*d + v[d][(b-x)-1][n-x-1]
                        candidates.append(val)
                    # choose minimum with largest index (prefer more leaves at smaller depths)
                    # min_idx, min_val = min(enumerate(candidates), key=operator.itemgetter(1)) 
                    min_val = min(candidates)
                    min_idx = max([i for i, x in enumerate(candidates) if x == min_val])
                    v[d-1][b_idx][n_idx] = min_val
                    if (b-min_idx)*K >= (n-min_idx): 
                       new_leaves[b_idx][n_idx] = [min_idx] + [n-min_idx]
                    else: 
                       new_leaves[b_idx][n_idx] = [min_idx] + leaves[b-min_idx-1][n-min_idx-1]
        leaves = new_leaves

    num_leaves = leaves[0][N-1]
    depth = len(num_leaves)
    num_internals = [0]*(depth-1)
    tree_nodes = num_leaves[-1]

    for d in range(depth-1,0,-1):
        num_internals[d-1] =  tree_nodes/K
        tree_nodes = num_internals[d-1] + num_leaves[d-1]

    # remove dummies
    num_leaves[-1] -= P
    
    return clients, num_leaves, num_internals

#
# This function builds scratchpad trees for all platforms
#
def buildScratchpadTrees(platforms, treeKary, treeMode): 
    remapIds = {}
    new_id = 1
    internal_node_id = 1
    for platform in platforms:
        controllers = platform.controllers
        network = [ScratchpadTreeNode("root"+str(x)) for x in range(len(controllers))]
        for i, controller in enumerate(controllers):
            clients = [x for x in platform.clients if i in x.controllerIdx]
            sorted_clients, num_leaves, num_internals = constructScratchpadTreeTopology(clients, treeKary, treeMode) 
            if treeMode == 3:  
                random.seed(1)
                random.shuffle(sorted_clients)
            
            # remap client IDs
            for client in sorted_clients:
                client.remappedIds[i] = str(new_id)
                if len(client.controllerIdx) > 1: 
                    remapIds[str(new_id)] = client.id + "*"
                else:
                    remapIds[str(new_id)] = client.id
                new_id += 1
                       
            # build scratchpad tree
            root  = network[i]
            depth = len(num_leaves) 
            
            if depth == 1: # build a flat tree
                # create leaf nodes
                child_nodes = [ScratchpadTreeLeaf(x,x.remappedIds[i],x.getBandwidthFraction(i)) for x in sorted_clients]
            else: # depth >= 2:
                # build tree from bottom to top                
                # create leaf nodes
                leaves = num_leaves[depth-1]
                child_nodes = [ScratchpadTreeLeaf(x,x.remappedIds[i],x.getBandwidthFraction(i)) for x in sorted_clients[len(sorted_clients)-leaves:]]
                sorted_clients = sorted_clients[:len(sorted_clients)-leaves]
                
                for d in range(depth-1,0,-1): 
                    current_nodes = []
                    for node_id in range(num_internals[d-1]):
                        n = ScratchpadTreeNode("n"+str(internal_node_id + node_id))
                        if len(child_nodes) % treeKary > 0:  
                            n.add_children(child_nodes[:len(child_nodes)%treeKary])
                            child_nodes = child_nodes[len(child_nodes)%treeKary:]
                        else:     
                            n.add_children(child_nodes[:treeKary])
                            child_nodes = child_nodes[treeKary:]
                        current_nodes.append(n)
                    internal_node_id += num_internals[d-1]
                    leaves = num_leaves[d-1]
                    current_nodes = [ScratchpadTreeLeaf(x,x.remappedIds[i],x.getBandwidthFraction(i)) for x in sorted_clients[len(sorted_clients)-leaves:]] + current_nodes
                    sorted_clients = sorted_clients[:len(sorted_clients)-leaves]
                    child_nodes = current_nodes 
                
            root.add_children(child_nodes) 
            print root
            print "Total tree weight: " + str(root.weight()) + "\n"
        platform.network = network
        platform.networkType = "tree"
    return remapIds

