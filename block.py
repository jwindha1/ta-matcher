# This tool is intented to anonymously and automatically create
# assignments of student groups to TAs for projects, taking into
# account block lists and previous project assignments

############ INPUT FILE FORMATS ############

# blocks.csv (needed for both labs and projects)
# - row: block
# - col: 0th col is ta login, 1st col is student login
# - no headers
# ------------------
# | ta1 | student1 |
# | ta1 | student2 |
# | ta2 | student3 |
# | ta3 | student1 |
# ------------------

# tas.csv
# - row: ta login
# - col: only one column
# - no headers
# -------
# | ta1 |
# | ta2 |
# | ta3 |
# | ta4 |
# -------

# project_student_pairs.csv
# - row: pair/group of student logins
# - col: no order/meaning
# - no headers
# -------------------------------------
# | pair1stu1 | pair1stu2 |           |
# | pair2stu1 | pair2stu2 | pair2stu3 |
# | pair3stu1 |           |           |
# -------------------------------------

# project_history.json (optional for projects)
# - read and written through this file, no need for external modification
# - stores which students have done projects for which tas so there is no
#   overlap in later projects

############ OUTPUT FILE FORMATS ############

# lab_student_assignment.csv (from labs)
# - row: no order/meaning
# - col: student logins for each lab
# - header row: lab names
# - no header col
# ----------------------------------
# | lab1     | lab2     | lab3     |
# | student1 | student3 | student6 |
# | student2 | student4 | student7 |
# |          | student5 |          |
# ----------------------------------

# project_student_assignment/{ta's login}.csv for every ta
# - row: pair/group of student logins assigned to the ta in the file name
# - col: no order/meaning
# - no headers
# -------------------------------------
# | pair1stu1 | pair1stu2 |           |
# | pair2stu1 | pair2stu2 | pair2stu3 |
# | pair3stu1 |           |           |
# -------------------------------------

############ INSTRUCTIONS ############

# to interact: call lab() or project()
# if you would like to use different filenames, use run_lab() or run_project()

import itertools
import math
import random
import pandas as pd
import csv
import json
import os

# Main data structures:

# blocks: {ta: [student]}
# lab2tas: {labname: {ta}}
# student_preferences: {student: [labname]}
# lab2students: {labname: {student}}
# tas: {ta}
# student_pairs: [{student}]
# history: {ta: {student}}
# ta2groups: {ta: [{student}]}

# input: filenames representing blocks and ta list
# output: blocks dict
def load_blocks(block_file, ta_lst):
    print("Loading blocks")
    blocks = {}
    with open(ta_lst, "r+") as f:
        reader = csv.reader(f, delimiter=',')
        tas = {item for sublist in list(reader) for item in sublist}
    for ta in tas:
        if ta != "": blocks[ta] = set()
    with open(block_file, "r+") as f:
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            ta = row[0]
            student = row[1]
            blocks[ta].add(student)
    return blocks

############ PROJECT CODE ############

# input: filanames representing tas and student pairs and optionally history json
# output: tas set, student_pairs list, and history dict
def load_project_data(ta_lst, students, proj_hist=None):
    print("Loading project data")
    # create tas
    with open(ta_lst, "r+") as f:
        reader = csv.reader(f, delimiter=',')
        tas = {item for sublist in list(reader) for item in sublist}
    if "" in tas: tas.remove("")

    # create student_pairs
    with open(students, "r+") as f:
        student_pairs = []
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            cleaned = set(row)
            if "" in cleaned: cleaned.remove("")
            student_pairs.append(cleaned)

    # create history
    if proj_hist is None:
        history = dict.fromkeys(tas)
        for h in history.keys():
            history[h] = set()
    else:
        with open(proj_hist) as f:
            history_raw = json.load(f)
        history = {k: set(v) for k, v in history_raw.items()}
    return tas, student_pairs, history

# input: two dicts
# output: True if a conflict was found; else False
def project_conflicts(ta2groups, blocks):
    print("Checking for a project conflict")
    found_conflict = False
    for ta, group in ta2groups.items():
        for pair in group:
            for student in pair:
                c = find_conflict(ta, student, blocks)
                if c:
                    print("Conflict: block requested by {0}".format(c[1]))
                    found_conflict = True
    return found_conflict

# input: tas set, three dicts
# output: ta2groups
def assign_project(tas, student_pairs, history, blocks):
    print("Assigning projects")
    ta2groups = dict.fromkeys(tas)  # {ta -> [{student}]}
    for g in ta2groups.keys():
        ta2groups[g] = list()
    max_groups_per_ta = math.ceil(len(student_pairs)/len(tas))
    for pair in student_pairs:
        group_placed = False
        # Create a set of TA options where none of the students are blocked or
        # have done a project for the TA before
        options = sorted(list(tas.copy()), key=lambda ta: len(ta2groups[ta]))
        for ta in options:
            for student in pair:
                if student in history[ta] or student in blocks[ta]:
                    if ta in options: options.remove(ta)
        if len(options) == 0:
            print("Group {0} had conflicts with all options".format(pair))
            continue
        # place group with the TA with least groups who fits all criteria
        for ta in options:
            if len(ta2groups[ta]) >= max_groups_per_ta: continue
            ta2groups[ta].append(pair)
            group_placed = True
            break
        # if all preferred tas were at capacity, place students with the ta who
        # has the fewest groups, overriding maximum
        if not group_placed:
            print("Group {0} placed over capacity".format(pair))
            smallest_option = min([(len(ta2groups[t]), t) for t in options])[1]
            ta2groups[smallest_option].append(pair)
    assert(not project_conflicts(ta2groups, blocks))
    return ta2groups

# input: history and ta2groups dicts, json filename if writing update
# output: updated history dict
def update_project_history(curr_history, curr_groups, fname=None):
    print("Updating project history")
    for ta, groups in curr_groups.items():
        for pair in groups:
            for student in pair:
                curr_history[ta].add(student)
    if fname is not None:
        with open(fname, "w") as f:
            json.dump({k: list(v) for k, v in curr_history.items()}, f)
    return curr_history

# input: ta2groups, name for assignment directory
# output: none
def download_project_assignments(ta2groups, subdirectory_path):
    print("Downloading project assignments")
    if not os.path.exists(subdirectory_path): os.mkdir(subdirectory_path)
    for ta, groups in ta2groups.items():
        with open(os.path.join(subdirectory_path, "{0}.csv".format(ta)), mode='w+') as f:
            writer = csv.writer(f, delimiter=',')
            writer.writerows(groups)

# input: filenames for everything needed, directory name, and optional history
#        json filename
# output: none
def run_project(block_file, ta_file, student_file, assignment_directory, history_file=None):
    print("Running project")
    blocks = load_blocks(block_file, ta_file)
    tas, student_pairs, history = load_project_data(ta_file, student_file, history_file)
    ta2groups = assign_project(tas, student_pairs, history, blocks)
    if history_file is None:
        history_file = "project_history.json"
    update_project_history(history, ta2groups, history_file)
    download_project_assignments(ta2groups, assignment_directory)

# wrapper function for run_project()
# input: a boolean indicating whether there exists a project history file
# output: none; generates project_student_assignment folder and project_history.json
def project(has_history):
    hist = "project_history.json" if has_history else None
    run_project("blocks.csv", "tas.csv", "project_student_pairs.csv", "project_student_assignment", hist)

project(False)
