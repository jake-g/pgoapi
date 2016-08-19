import math
import random


def distL2(p1, p2):
    y1, x1 = p1
    y2, x2 = p2
    xdiff = x2 - x1
    ydiff = y2 - y1
    return math.sqrt(xdiff*xdiff + ydiff*ydiff)

def mk_matrix(coord, dist):
    """Compute a distance matrix for a set of points.

    Uses function 'dist' to calculate distance between
    any two points.  Parameters:
    -coord -- list of tuples with coordinates of all points, [(x1,y1),...,(xn,yn)]
    -dist -- distance function
    """
    n = len(coord)
    D = {}      # dictionary to hold n times n matrix
    for i in range(n-1):
        for j in range(i+1,n):
            (x1,y1) = coord[i]
            (x2,y2) = coord[j]
            D[i,j] = dist((x1,y1), (x2,y2))
            D[j,i] = D[i,j]
    return n,D

def mk_closest(D, n):
    """Compute a sorted list of the distances for each of the nodes.

    For each node, the entry is in the form [(d1,i1), (d2,i2), ...]
    where each tuple is a pair (distance,node).
    """
    C = []
    for i in range(n):
        dlist = [(D[i,j], j) for j in range(n) if j != i]
        dlist.sort()
        C.append(dlist)
    return C


def length(tour, D):
    """Calculate the length of a tour according to distance matrix 'D'."""
    z = D[tour[-1], tour[0]]    # edge from last to first city of the tour
    for i in range(1,len(tour)):
        z += D[tour[i], tour[i-1]]      # add length of edge from city i-1 to i
    return z


def randtour(n):
    """Construct a random tour of size 'n'."""
    sol = range(n)      # set solution equal to [0,1,...,n-1]
    random.shuffle(sol) # place it in a random order
    return sol


def nearest(last, unvisited, D):
    """Return the index of the node which is closest to 'last'."""
    near = unvisited[0]
    min_dist = D[last, near]
    for i in unvisited[1:]:
        if D[last,i] < min_dist:
            near = i
            min_dist = D[last, near]
    return near


def nearest_neighbor(n, i, D):
    """Return tour starting from city 'i', using the Nearest Neighbor.

    Uses the Nearest Neighbor heuristic to construct a solution:
    - start visiting city i
    - while there are unvisited cities, follow to the closest one
    - return to city i
    """
    unvisited = list(range(n))
    unvisited.remove(i)
    last = i
    tour = [i]
    while unvisited != []:
        next = nearest(last, unvisited, D)
        tour.append(next)
        unvisited.remove(next)
        last = next
    return tour



def exchange_cost(tour, i, j, D):
    """Calculate the cost of exchanging two arcs in a tour.

    Determine the variation in the tour length if
    arcs (i,i+1) and (j,j+1) are removed,
    and replaced by (i,j) and (i+1,j+1)
    (note the exception for the last arc).

    Parameters:
    -t -- a tour
    -i -- position of the first arc
    -j>i -- position of the second arc
    """
    n = len(tour)
    a,b = tour[i],tour[(i+1)%n]
    c,d = tour[j],tour[(j+1)%n]
    return (D[a,c] + D[b,d]) - (D[a,b] + D[c,d])


def exchange(tour, tinv, i, j):
    """Exchange arcs (i,i+1) and (j,j+1) with (i,j) and (i+1,j+1).

    For the given tour 't', remove the arcs (i,i+1) and (j,j+1) and
    insert (i,j) and (i+1,j+1).

    This is done by inverting the sublist of cities between i and j.
    """
    n = len(tour)
    if i>j:
        i,j = j,i
    assert i>=0 and i<j-1 and j<n
    path = tour[i+1:j+1]
    path.reverse()
    tour[i+1:j+1] = path
    for k in range(i+1,j+1):
        tinv[tour[k]] = k


def improve(tour, z, D, C):
    """Try to improve tour 't' by exchanging arcs; return improved tour length.

    If possible, make a series of local improvements on the solution 'tour',
    using a breadth first strategy, until reaching a local optimum.
    """
    n = len(tour)
    tinv = [0 for i in tour]
    for k in range(n):
        tinv[tour[k]] = k  # position of each city in 't'
    for i in range(n):
        a,b = tour[i],tour[(i+1)%n]
        dist_ab = D[a,b]
        improved = False
        for dist_ac,c in C[a]:
            if dist_ac >= dist_ab:
                break
            j = tinv[c]
            d = tour[(j+1)%n]
            dist_cd = D[c,d]
            dist_bd = D[b,d]
            delta = (dist_ac + dist_bd) - (dist_ab + dist_cd)
            if delta < 0:       # exchange decreases length
                exchange(tour, tinv, i, j);
                z += delta
                improved = True
                break
        if improved:
            continue
        for dist_bd,d in C[b]:
            if dist_bd >= dist_ab:
                break
            j = tinv[d]-1
            if j==-1:
                j=n-1
            c = tour[j]
            dist_cd = D[c,d]
            dist_ac = D[a,c]
            delta = (dist_ac + dist_bd) - (dist_ab + dist_cd)
            if delta < 0:       # exchange decreases length
                exchange(tour, tinv, i, j);
                z += delta
                break
    return z


def localsearch(tour, z, D, C=None):
    """Obtain a local optimum starting from solution t; return solution length.

    Parameters:
      tour -- initial tour
      z -- length of the initial tour
      D -- distance matrix
    """
    n = len(tour)
    if C == None:
        C = mk_closest(D, n)     # create a sorted list of distances to each node
    while 1:
        newz = improve(tour, z, D, C)
        if newz < z:
            z = newz
        else:
            break
    return z


def multistart_localsearch(k, n, D, report=None):
    """Do k iterations of local search, starting from random solutions.

    Parameters:
    -k -- number of iterations
    -D -- distance matrix
    -report -- if not None, call it to print verbose output

    Returns best solution and its cost.
    """
    C = mk_closest(D, n) # create a sorted list of distances to each node
    bestt=None
    bestz=None
    for i in range(0,k):
        tour = randtour(n)
        z = length(tour, D)
        z = localsearch(tour, z, D, C)
        if z < bestz or bestz == None:
            bestz = z
            bestt = list(tour)
            if report:
                report(z, tour)

    return bestt, bestz
