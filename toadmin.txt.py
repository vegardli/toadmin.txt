#!/usr/bin/python

# Copyright 2016 Vegard Knutsen Lillevoll
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE. 

import pickle,os,re,datetime,argparse,string,signal,time

# Parse command-line options
parser = argparse.ArgumentParser(description="Automate certain todo list tasks")
parser.add_argument("--options_file", help="File to read and write options")
parser.add_argument("--review", action="store_true", help="Perform review")
parser.add_argument("--guided", action="store_true", help="Go through tasks needing attention step-by-step")
args = parser.parse_args()

# Used to see if todo.txt was modified from another program
todo_last_modified = time.time()
todo_externally_changed = False

# Variable to store todos
local_todos = None

# Default data file location
data_file = os.path.join(os.path.expanduser("~"), ".toadmin.txt")
if args.options_file:
    data_file = options.options_file

# Todo superclass, for both local and Habitica todos
class Todo:
    def __str__(self):
        outstr = ""

        if self.done:
            outstr += "x "
            if self.completed:
                outstr += self.completed.isoformat() + " "
            if self.created:
                outstr += self.created.isoformat() + " "

        else:
            if self.priority:
                outstr += self.priority
            if self.created:
                outstr += self.created.isoformat() + " "

        outstr += self.text

        for p in self.projects:
            outstr += " " + p
        for c in self.contexts:
            outstr += " " + c
        for k, v in self.addons.items():
            if type(v) == type(datetime.date.today()):
                outstr += " " + k + ":" + v.isoformat()

            else:
                outstr += " " + k + ":" + v

        return outstr + "\n"

    def human_str(self):
        a = self.addons
        self.addons = {}
        c = self.created
        self.created = None
        s = str(self)
        self.addons = a
        self.created = c
        return s.rstrip("\n")

    def get_dict(self):
        d = {}

        d['type'] = 'todo'
        d['completed'] = self.done

        if self.created:
            d['createdAt'] = self.created.isoformat()
        if self.completed:
            d['dateCompleted'] = self.completed
        
        if "habitica_id" in self.addons:
            d['id'] = self.addons['habitica_id']

        d['text'] = str(self)

        return d


class LocalTodo(Todo):
    def __init__(self, init_str):
        self.done = False
        self.created = None
        self.completed = None
        self.priority = None
        self.text = ""

        # Search for priority, date and text (incomplete tasks)
        incomplete_result = re.match("(\([A-Z]\) )?\s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", init_str)

        # Search for completeness, completion date, creation date and text (complete tasks)
        complete_result = re.match("x \s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?\s*([0-9]{4}-[0-9]{2}-[0-9]{2} )?(.+)", 
                init_str)

        if complete_result:
            # Task is complete
            self.done = True
            
            if complete_result.group(1):
                self.completed = datetime.datetime.strptime(complete_result.group(1).strip(), "%Y-%m-%d").date()

            if complete_result.group(2):
                self.created = datetime.datetime.strptime(complete_result.group(2).strip(), "%Y-%m-%d").date()

            self.text = complete_result.group(3)

        elif incomplete_result:
            # Task is incomplete
            self.priority = incomplete_result.group(1)

            if incomplete_result.group(2):
                self.created = datetime.datetime.strptime(incomplete_result.group(2).strip(), "%Y-%m-%d").date()

            self.text = incomplete_result.group(3)

        else:
            # TODO: Implement own exception
            raise Exception("Couldn't parse task: " + init_str)

        (self.text, self.projects, self.contexts, self.addons) = parse_todotext(self.text)

# Returns (text, projects, contexts, addons)
def parse_todotext(text):
    projects = []
    contexts = []
    addons = {}

    project_regex = re.compile(" \+[^ ]+")
    context_regex = re.compile(" \@[^ ]+")
    addon_regex = re.compile("([^ :]+):([^ :]+)")

    for p in project_regex.findall(text):
        projects.append(p.lstrip(" "))

    for c in context_regex.findall(text):
        contexts.append(c.lstrip(" "))

    for a in addon_regex.findall(text):
        if a[0] == "due":
            addons[a[0]] = datetime.datetime.strptime(a[1].strip(), "%Y-%m-%d").date()
            continue

        addons[a[0]] = a[1]

    # Remove projects, contexts and addons from text
    (text, n) = project_regex.subn("", text)
    (text, n) = context_regex.subn("", text)
    (text, n) = addon_regex.subn("", text)

    text = text.strip()

    return (text, projects, contexts, addons)

# Give Y/N or other prompt
def ask_question(text, alternatives = {"Y": "Yes", "N": "No"}):
    response = string.ascii_letters # Unlikely to be an option

    question = " (" + "/".join(sorted(alternatives.keys())) + ") "

    while not response in alternatives:
        response = input(text + question).strip().upper()

    print(alternatives[response])
    return response

def set_priority(todo):
    p = ask_question("Priority?", {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "": "No priority"}) 
    if p != "":
        todo.priority = "(" + p + ") "
        print("Priority set to " + todo.priority)
    else:
        todo.priority = ""
        print("No priority set.")

def add_metadata(todo):
    d = input("Add +projects, @contexts or other data: ")
    (text, projects, contexts, addons) = parse_todotext(" " + d)
    todo.projects += projects
    todo.contexts += contexts
    todo.addons.update(addons)

def load_options(data_file):
    return pickle.load(open(data_file, "rb"))

def save_options(data_file, options):
    pickle.dump(options, open(data_file, "wb"))

def load_todos():
    todos = []

    with open(options["todo.txt-location"], "r") as local_todos_file:
        for line in local_todos_file.readlines():
            if line.strip():
                todos.append(LocalTodo(line))

    return todos


def save_todos(local_todos):
    global todo_last_modified

    with open(options["todo.txt-location"], "w") as local_todos_file:
        for todo in local_todos:
            local_todos_file.write(str(todo))

    todo_last_modified = time.time()

def filter_match(task, filter):
    if len(filter) == 0:
        return True

    for i in filter:
        match = False
        for j in task.projects:
            if i == j:
                match = True
                break

        if not match:
            return False

    return True


# Get string showing numbered, grouped tasks. Returns (str, index_list)
def get_interactive_task_list(tasks, filter = []):
    next = []
    today = []
    scheduled = []
    waiting = []
    someday = []
    new = []
    other = []

    return_string = ""

    for task in local_todos:
        if task.done:
            continue

        if not filter_match(task, filter):
            continue

        if not "state" in task.addons:
            other.append(task)

        else:
            if task.addons['state'] == "next":
                next.append(task)
            
            elif task.addons['state'] == "today":
                today.append(task)
            
            elif task.addons['state'] == "scheduled":
                scheduled.append(task)
            
            elif task.addons['state'] == "waiting":
                waiting.append(task)
            
            elif task.addons['state'] == "someday":
                someday.append(task)

            elif task.addons['state'] == "new":
                new.append(task)

            else:
                return_string += "Warning: unrecognized state: " + task.addons['state'] + "\n"
                other.append(task)

    scheduled.sort(key = lambda x: x.addons["due"])

    index_list = next + today + scheduled + waiting + someday + new +other


    states = {0: "Next", 
            len(next): "Today", 
            len(next) + len(today): "Scheduled",
            len(next) + len(today) + len(scheduled): "Waiting",
            len(next) + len(today) + len(scheduled) + len(waiting): "Someday",
            len(next) + len(today) + len(scheduled) + len(waiting) + len(someday): "New",
            len(next) + len(today) + len(scheduled) + len(waiting) + len(someday) + len(new): "Other"}

    for i in range(len(index_list)):
        if i in states:
            return_string += "\n" + states[i] + "\n"

        if index_list[i].addons["state"] == "scheduled":
            return_string += (str(i).zfill(2) + ": (" + index_list[i].addons["due"].isoformat() + ") " + 
                    index_list[i].human_str() + "\n")

        else:
            return_string += str(i).zfill(2) + ": " + index_list[i].human_str() + "\n"

    return (return_string, index_list)

# Used to check if todo.txt has changed while entering commands
def interactive_check_todo_changes(signum, frame):
    global local_todos, todo_last_modified, todo_externally_changed
    if os.path.getmtime(options["todo.txt-location"]) > todo_last_modified:
        todo_externally_changed = True
        print("WARNING: todo.txt has been modified from another application. Reloading...")
        local_todos = do_auto_actions(load_todos())
        save_todos(local_todos)
        (s, l) = get_interactive_task_list(local_todos)
        print(s)
        print("Todos reloaded.")
        todo_last_modified = time.time()

def do_auto_actions(todos):
    for todo in todos:
        # Tag new tasks as new
        if not "state" in todo.addons and not todo.done:
            todo.addons["state"] = "new"

        # Complete tasks should be tagged as such
        if todo.done:
            todo.addons["state"] = "done"

        # Set creation date for undated tasks
        if not todo.created and not todo.done:
            todo.created = datetime.date.today()

        # Make scheduled tasks due today or earlier have state today
        if ((todo.addons["state"] == "scheduled" or todo.addons["state"] == "waiting") and "due" in todo.addons and 
                todo.addons["due"] <= datetime.date.today()):
            todo.addons["state"] = "today"

    return todos

# Load options
if os.path.isfile(data_file):
    options = load_options(data_file)

else:
    options = {}

# Take option input from user
if not "todo.txt-location" in options:
    options["todo.txt-location"] = input("todo.txt location: ")
    # Make sure the file can be written to
    open(options["todo.txt-location"], "a").close()
    save_options(data_file, options)


# Load todos from todo.txt
local_todos = load_todos()

# Perform automated actions
local_todos = do_auto_actions(local_todos)

next_todos = []
today_todos = []
for todo in local_todos:
    if todo.addons["state"] == "next":
        next_todos.append(todo)

    elif todo.addons["state"] == "today":
        today_todos.append(todo)

# If review is set, the tasks will be printed shortly anyways
if not args.review:
    # Print upcoming tasks
    if len(next_todos) > 0:
        print("Next:")
        for t in next_todos:
            print(t.human_str())

    if len(today_todos) > 0:
        print("Today:")
        for t in today_todos:
            print(t.human_str())


if args.guided:
    if len(next_todos) == 0 and args.review:
        if len(today_todos) > 0:
            if ask_question("No todos marked as next, go through list for today?") == "Y":
                for todo in today_todos:
                    print(todo.human_str())
                    if ask_question("Mark as next?") == "Y":
                        set_priority(todo)
                        todo.addons["state"] = "next"
                        print("Moved to next")


# Do review
if args.review and args.guided:
    for todo in local_todos:
        if todo.addons["state"] == "new":
            print("---")
            print(todo.human_str())

            r = ask_question("Does it take less than 2 minutes?", {"Y": "Yes", "N": "No", "S": "Skip"})
            if r == "Y":
                print("Do it now.")
                if ask_question("Is it done?") == "Y":
                    todo.done = True
                    del todo.addons["state"]
                    print("Task marked as done")
                    continue

                else:
                    continue

            elif r == "S":
                break


            add_metadata(todo)
            r = ask_question("Complete (N)ext, (T)oday, at a certain (D)ate or (S)omeday?", 
                    {"N": "Next", "T": "Today", "D": "Certain date", "S": "Someday"})

            if r == "N":
                set_priority(todo)
                todo.addons["state"] = "next"
                print("Marked as next")
                continue

            elif r == "T":
                set_priority(todo)
                todo.addons["state"] = "today"
                print("Marked as today")
                continue

            elif r == "D":
                while not "due" in todo.addons:
                    try:
                        todo.addons["due"] = datetime.datetime.strptime(
                                input("Enter date (YYYY-MM-DD): ").strip(), "%Y-%m-%d").date().isoformat()
                    except ValueError:
                        print("Format not recognized")
                
                todo.addons["state"] = "scheduled"

                continue

            elif r == "S":
                # Delegate to someday
                todo.priority = "(Z) "
                todo.addons["state"] = "someday"
                print("Task marked as \"someday\"")
                continue

            # TODO: Implement convert to project

quit = False
if args.review:
    # Enter interactive mode
    out = ""
    filter = []
    signal.signal(signal.SIGALRM, interactive_check_todo_changes)
    signal.setitimer(signal.ITIMER_REAL, 1, 1)

    while not quit:
        # Sort & save tasks
        local_todos.sort(key = lambda x: str(x))
        save_todos(local_todos)

        (s, index_list) = get_interactive_task_list(local_todos, filter)
        print(s)

        if len(filter) != 0:
            print("Filter: " + ", ".join(filter))

        if out != "":
            print(out)
        print("Q to quit")

        try:
            inp = input("> ")

        except KeyboardInterrupt:
            quit = True
            continue

        # If todo.txt is modified by another program, make sure we have correct task list numbers
        if todo_externally_changed:
            (s, index_list) = get_interactive_task_list(local_todos, filter)
            todo_externally_changed = False

        cmd = inp.split(" ")

        if cmd[0] == "q" or cmd[0] == "Q":
            quit = True

        elif cmd[0].lower() == "add":
            new_task_str = " ".join(cmd[1:])
            if len(new_task_str) < 1:
                out = "Please specify todo"
                continue

            new_task = LocalTodo(new_task_str)
            new_task.addons["state"] = "new"
            new_task.created = datetime.date.today()

            local_todos.append(new_task)

            out = "Created task \"" + new_task.text + "\""

        elif cmd[0].lower() == "filter":
            if len(cmd) == 1:
                out = "Please specify filter"
                continue

            if len(cmd) > 2:
                out = "Too many arguments for filter"
                continue

            if cmd[1][0] == "-":
                for i in range(len(filter)):
                    if filter[i][1:] == cmd[1][1:]:
                        del filter[i]
                        out = "Removed filter " + cmd[1][1:]
                        break

            else:
                filter.append(cmd[1].strip())
                out = "Added filter " + cmd[1]


        else:
            try:
                target = int(cmd[0])
                command = cmd[1]

            except ValueError:
                out = (cmd[0] + " is not a valid task number")
                continue

            except IndexError:
                out = ("Please specify a command")
                continue

            if command == "state":
                try:
                    new_state = cmd[2]

                except IndexError:
                    out = ("Please specify new state")
                    continue

                if new_state in ["new", "next", "today", "waiting", "new", "someday"]:
                    index_list[target].addons["state"] = new_state
                    out = ("Set state of " + index_list[target].text + " to " + new_state)

                elif new_state == "scheduled":
                    if "due" in index_list[target].addons:
                        del index_list[target].addons["due"]

                    os.system("cal -3")

                    while not "due" in index_list[target].addons:
                        try:
                            index_list[target].addons["due"] = datetime.datetime.strptime(
                                    input("Enter date (YYYY-MM-DD): ").strip(), "%Y-%m-%d").date()
                        except ValueError:
                            print("Format not recognized")

                    index_list[target].addons["state"] = new_state
                    continue

                else:
                    out = "Unrecognized state: " + new_state
                    continue


            elif command == "pri":
                try:
                    new_pri = cmd[2]

                except IndexError:
                    out = ("Please specify new priority")
                    continue
                
                if len(new_pri) == 1 and new_pri.upper() in string.ascii_uppercase:
                    index_list[target].priority = "(" + new_pri.upper() + ") "
                    out = "Set priority of " + index_list[target].text + " to " + index_list[target].priority
                    
                else:
                    out = "Please specify a single-letter priority"

            elif command == "done":
                index_list[target].done = True
                index_list[target].addons["state"] = "done"
                index_list[target].completed = datetime.date.today()
                out = "Marked " + index_list[target].text + " as done."


            else:
                out = ("Unknown command: " + cmd[1])
                continue


# Sort tasks
local_todos.sort(key = lambda x: str(x))

# Don't save if we have been in interactive mode, this reduces chances of overwriting changes made elsewhere
if not quit:
    # Save changes
    save_todos(local_todos)
