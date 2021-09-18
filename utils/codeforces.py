import json
import random
import math

from utils import cf_api
from data import dbconn

db = dbconn.DbConn()
cf = cf_api.CodeforcesAPI()

authors = None


def isNonStandard(id):
    names = [
        'wild', 'fools', 'unrated', 'surprise', 'unknown', 'friday', 'q#', 'testing',
        'marathon', 'kotlin', 'onsite', 'experimental', 'abbyy']
    contest_name = db.get_contest_name(id)
    for x in names:
        if x in contest_name.lower():
            return True
    return False


def isAuthor(handles, problem):
    if str(problem.id) not in authors:
        return False
    for handle in handles:
        if handle in authors[str(problem.id)]:
            return True
    return False


def filter_problems(all_problems, user_problems, handles):
    with open('./data/authors.json') as f:
        global authors
        authors = json.load(f)
    unsolved = []
    names = [x.name for x in user_problems]
    names.sort()

    for problem in all_problems:
        if isNonStandard(problem.id) or isAuthor(handles, problem):
            continue

        found = False
        l, r = 0, len(names) - 1
        while l <= r:
            mid = int((l+r)/2)
            if names[mid] > problem.name:
                r = mid - 1
            elif names[mid] < problem.name:
                l = mid + 1
            else:
                found = True
                break

        if not found:
            unsolved.append(problem)

    return unsolved


async def find_problems(handles, ratings, tags=None):
    all_problems = db.get_problems()
    user_problems = []
    for handle in handles:
        resp = await cf.get_user_problems(handle)
        if not resp[0]:
            return resp
        user_problems.extend(resp[1])

    user_problems = list(set(user_problems))

    unsolved_problems = filter_problems(all_problems, user_problems, handles)

    selected = []
    for x in ratings:
        problem = None
        options = []
        if tags is None:
            options = [p for p in unsolved_problems if p.rating == x and p not in selected]
        else:
            for p in unsolved_problems:
                if p.rating == x and p not in selected:
                    good = True
                    p_tags = p.tags.split(',')
                    for tag in tags:
                        if tag not in p_tags:
                            good = False
                    if good:
                        options.append(p)
        weights = [int(p.id * math.sqrt(p.id)) for p in options]
        if options:
            problem = random.choices(options, weights, k=1)[0]
        if not problem:
            if tags is None:
                return [False, f"Not enough problems with rating {x} left!"]
            return [False, f"Not enough problems with rating {x} and tags: `{','.join(tags)}` left!"]
        selected.append(problem)

    return [True, selected]


def get_solve_time(sub, id, index, solo_time=0):
    best = 1e18
    for x in sub:
        if x.id == int(id) and x.index == index:
            if x.verdict == 'OK' and x.sub_time > solo_time:
                best = min(best, x.sub_time)
            if x.verdict is None or x.verdict == 'TESTING':
                return -1
    return best


async def check_solved(handles, id, index):
    ans = False
    for handle in handles:
        resp = await cf.get_user_problems(handle)
        if not resp[0]:
            return resp
        for p in resp[1]:
            if p.id == id and p.index == index:
                ans = True
    return ans
