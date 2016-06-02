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

import pickle,os,re,datetime,argparse,string

# Parse command-line options
parser = argparse.ArgumentParser(description="Automate certain todo list tasks")
parser.add_argument("--options_file", help="File to read and write options")
parser.add_argument("--review", action="store_true", help="Perform review")
args = parser.parse_args()

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
            outstr += " " + k + ":" + v

        return outstr + "\n"

    def human_str(self):
        a = self.addons
        self.addons = {}
        s = str(self)
        self.addons = a
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
local_todos = []

with open(options["todo.txt-location"], "r") as local_todos_file:
    for line in local_todos_file.readlines():
        if line.strip():
            local_todos.append(LocalTodo(line))


# Start action list
for todo in local_todos:
    # Tag new tasks as new
    if not "state" in todo.addons and not todo.done:
        todo.addons["state"] = "new"

    # Complete tasks should be tagged as such
    if todo.done:
        todo.addons["state"] = "done"

    # Set creation date for undated tasks
    if not todo.created and not todo.done:
        todo.created = datetime.date.today()

# Print upcoming tasks
next_todos = []
today_todos = []
for todo in local_todos:
    if todo.addons["state"] == "next":
        next_todos.append(todo)

    elif todo.addons["state"] == "today":
        today_todos.append(todo)

if len(next_todos) > 0:
    print("Next:")
    for t in next_todos:
        print(t.human_str())

if len(today_todos) > 0:
    print("Today:")
    for t in today_todos:
        print(t.human_str())


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
if args.review:
    for todo in local_todos:
        if todo.addons["state"] == "new":
            print("---")
            print(todo.human_str())

            if ask_question("Does it take less than 2 minutes?") == "Y":
                print("Do it now.")
                if ask_question("Is it done?") == "Y":
                    todo.done = True
                    del todo.addons["state"]
                    print("Task marked as done")
                    continue

                else:
                    continue

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



# Sort tasks locally and on Habitica
#local_todos.sort(key = lambda x: str(x))

# Save changes
with open(options["todo.txt-location"], "w") as local_todos_file:
    for todo in local_todos:
        local_todos_file.write(str(todo))

