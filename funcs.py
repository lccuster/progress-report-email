import os
import csv
import json
import requests
import datetime
import time
import re
import sys

# logic that sets working directory to current. required for runtime on linux
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

### imported from checker ###
# Check is a function that makes sure that files which are scraped (and put into assignments.txt) are properly set up.
# honestly, we need something better than this long term, but its better to have it than not.
def check():

    # open the api file
    with open("./userdata/api.json", "r") as file:
        # the strips on the below line help remove random whitespace from canvas imports
        api_assignments = list(map(str.rstrip, list(json.load(file).keys())))
        file.close()

    # open the assignments json (handmade)
    with open("./userdata/assignments.json", "r") as file:
        assignment_dict = json.load(file)
        # the strips on the below line help remove random whitespace from canvas imports
        current_assignments = list(map(str.rstrip, list(assignment_dict.keys())))
        file.close()

    # open the modules json (handmade)  
    with open("./userdata/modules.json", "r") as file:
        week_map = json.load(file)
        # this is a temp list used to hold all the assignments which have modules ("weeks").
        assignments_in_modules = []
        # this just adds all assignments in each module to the list
        for week in list(week_map.keys()):
            assignments_in_modules += week_map[week]["assignments"]
        # same thing, strips whitespace
        assignments_in_modules = list(map(str.rstrip, assignments_in_modules))
        file.close()


    # this pulls the assignment names from output of the scraper.
    assignments = []
    with open("assignments.txt", "r") as file:
        for line in file:
            assignments.append(line.rstrip())
    
    # the print statements on each of these lines gives you a rough idea of what its checking for. Again, better to have it than not,
    # but we need a better long term solution.
    for assignment in assignments:
        if assignment not in current_assignments:
            print(f"\nWarning! '{assignment}' from assignments.txt not in assignments.json!")

    for assignment in current_assignments:
        if assignment not in assignments_in_modules:
            print(f"\nWarning! '{assignment}' from assignments.json not in modules.json!")
        if assignment_dict[assignment]["missingif"] == 'api':
            if assignment not in api_assignments:
                print(f"\nCRITICAL WARNING!!! '{assignment}' from assignments.json not in api.json! (run api_handler.py)")

    for assignment in assignments_in_modules:
        if assignment not in current_assignments:
            print(f"\nCRITICAL WARNING!!! '{assignment}' from modules.json not in assignments.json!")
    print("\n")



### imported from api_handler ###
# this handles the CanvasAPI scraping of assignment submissions. There's a whole system to how these exports work,
# and I think we should migrate to just using the api for everything. We can leave the old functionality in here under
# some legacy code (could help in working with non-Canvas systems in the future), but right now the entire scope of this
# project exists in Canvas.
def canvas_api(current_week):
    
    with open("./userdata/config.json", "r") as readfile:
        config = json.load(readfile)
        readfile.close()

    # a lot of this config reading (which we may add more) can eventually be put somewhere less scoped
    apikey = config["API"]["apikey"]
    course = config["API"]["course"]

    # right now we determine what assignments to pull based on the "./userdata/assignments.json" file. If a given assignment has
    # the api listed as its submission criterion, it pulls it here. Otherwise, we ignore it.
    with open("./userdata/assignments.json", "r") as file:
        assignment_dict = json.load(file)
        file.close()

    # this scopes the API usage so that we're not pulling everything in the class all at once. I'll be so real;
    # we can pull everything all at once. It's not that much of a problem.    
    with open("./userdata/modules.json", "r") as file:
        week_map = json.load(file)
        weeks = list(week_map.keys())[::-1]
        file.close()
    
    weeks_to_send = []

    week_index = weeks.index(current_week)
    for week in weeks[week_index:]:
        weeks_to_send.append(week)

    # uses the module mapping to determine everything that needs to be pulled
    current_assignments = []
    for week in weeks_to_send:
        current_assignments += week_map[week]["assignments"]

    # start of the actual code. missing_dict is the actual api dump that we save
    missing_dict = {}
    for assignment in set(current_assignments):
            
        # canvas gradebook (and subsequently our code) embeds assignments as "name (assignment_id)". This strips the assignment ID.
        # if we change this in the future, would make sense to fix this.
        assignment_id = str(assignment_dict[assignment]["id"])
        # for each assignment that needs api info we create a list.
        missing_dict[assignment] = []

        # so fun fact; we have to batch requests per 100 students to the API. This  looping function is here to go over all the pages.
        # maybe eventually we implement a progress bar or something? We can know the total amount of work ahead of time.
        page = 1
        print(f"Requesting page {page} of {assignment}...")
        # below is the full api url for the dump. You can look it over, it's pretty straightforward.
        base = "https://uncc.instructure.com/api/v1/courses/"+course+"/assignments/"
        query = assignment_id+"/submissions?access_token="+apikey+"&per_page=100&page=1&include[]=submission_history"
        r = requests.get(base+query)
        # sometimes Canvas will get mad at the number of requests, depending on the speokay,ed of the data transfer. This catches that issue and sleeps
        # the thread long enough to let us try again.
        while r.status_code == 403 or list(json.loads(r.text))[0] == "errors":
            print(f"Status Code 403, rerequesting page {page} of {assignment}...")
            time.sleep(5)
            r = requests.get(base+query)

        while r.text != "[]":
            page += 1
            submissions = json.loads(r.text)
            for submission in submissions:
                if type(assignment_dict[assignment]["missingif"]) != type([]):
                    assignment_dict[assignment]["missingif"] = [assignment_dict[assignment]["missingif"]]
                for criterion in assignment_dict[assignment]["missingif"]:
                # canvas just directly holds a boolean called missing for submittable assignments. freakin sweet
                    if submission["missing"] and criterion == "api":
                        # the way that we store missing assignments is a list of user IDs we cross-reference later. seemed okay to me
                        missing_dict[assignment].append(submission["user_id"])
                    # handles 0 case for now  
                    elif submission["grade"] == criterion:
                        missing_dict[assignment].append(submission["user_id"])

            # all the code from above again. a dowhile in python would go crazy... which we can write.
            print(f"Requesting page {page} of {assignment}...")
            query = assignment_id+"/submissions?access_token="+apikey+"&per_page=100&page="+str(page)+"&include[]=submission_history"
            r = requests.get(base+query)
            while r.status_code == 403 or (r.text != "[]" and list(json.loads(r.text))[0] == "errors"):
                print(f"Status Code 403, rerequesting page {page} of {assignment}...")
                time.sleep(5)
                r = requests.get(base+query)
            print("Done!")
        # empty page, so we're done with this assignment
        print(f"Page {page} empty, moving on...")

    
    # dumps everything for later use
    print("All assignments pulled via API.")
    with open("./userdata/api.json", "w") as file:
        json.dump(missing_dict, file, indent=4)



### imported from assignment_scraper ###
# this file can get completely trashed. We should move over to canvas API for this.
# I won't comment the code since the goal is to not have it anymore.
def scrape_assignments():
    with open("./userdata/assignments.json", "r") as file:
        assignment_dict = json.load(file)
        file.close()

    workfile = ""

    for file in os.listdir():
        if (file.split(".")[-1] == "csv"):
            workfile = file

    if workfile == "":
        print("Error: No Gradebook found")
    else:
        print("Gradebook found, extracting assignments")
        with open(workfile) as file:
            readfile = csv.reader(file)
            stuff = next(readfile)
            
            file.close()

    suggestions_dict = {}
    with open("assignments.txt", "w") as writefile:
        for assignment in stuff:
            if bool(re.match(r".*?\([0-9]+\)", assignment)):
                if assignment not in assignment_dict.keys():
                    writefile.write(assignment+"\n")
                    suggestions_dict[assignment] = {"missingif":"api"}

    with open("suggested_assignments.json", "w") as file:
        json.dump(suggestions_dict, file, indent=4)



### imported from runner ###
# this is the main logic used in the next function to check for missing assignments.
# it can handle most inputs, we'll mostly use API and something else to backup on unsubmittable assignments.
def is_missing(student, api_dict):
        if student in api_dict:
            return True
        return False


### imported from runner ###
# this is the big one. This is what actually produces the output file that is used to send emails.
# it's a big func, so i'll try to be clear with everything that happens.
# longterm, I think we should rewrite this to be more modular and customizable by users.
def make_emails(current_week):
    # get all assignments controlled by the api
    with open("./userdata/api.json", "r") as file:
        api_dict = json.load(file)
        file.close()

    # open all assignments currently known by the tool
    with open("./userdata/assignments.json", "r") as file:
        assignment_dict = json.load(file)
        file.close()

    with open("./userdata/students.json", "r") as file:
        students = json.load(file)
        file.close()

    with open("./userdata/modules.json", "r") as file:
        week_map = json.load(file)
        weeks = list(week_map.keys())[::-1]
        file.close()
    
    weeks_to_send = []

    week_index = weeks.index(current_week)
    for week in weeks[week_index:]:
        weeks_to_send.append(week)


    # sweet line
    workfile = ""

    # pulls all the assignments that are relevant 
    current_assignments = []
    for week in weeks_to_send:
        current_assignments += week_map[week]["assignments"]

    # this is what checks for and opens the gradebook for utilization.
    for file in os.listdir():
        if (file.split(".")[-1] == "csv"):
            workfile = file

    # this sets some of the things included in the export.
    # module, number of assignments, and the list of assignments for the module are done here.
    module = week_map[current_week]["name"]
    assignment_count = len(week_map[current_week]["assignments"])
    # logic to get the list of assignments mapped to the current module
    assignmentlist = ""
    for assignment in week_map[current_week]["assignments"]:
        # this logic cuts the numbers from the assignment when sending it to students.
        assignmentlist += "- "+assignment+"\n"

    # counts the total number of assignments which have been due so far, sums the number of assignments in each module.
    totalcomplete = 0
    for week in weeks_to_send:
        totalcomplete += len(week_map[week]["assignments"])

    # counts the total number of assignments due so far too. I believe I changed this code at some point due to a non-Yfunctional output. 
    totalcourse = 0
    for week in weeks:
        totalcourse += len(week_map[week]["assignments"])


    # okay, time for the meat of the function.
    data = []
    for student in students:
        # grab the first item, and get their first name (Canvas stores Last, First)
        name = students[student]["name"].split(", ")[-1]
        # grab student email
        email = students[student]["email"]

        # for the module, set the total completed to the max that can be. If something isn't complete, mark it as missing, and decrease the count.
        module_completed = assignment_count
        for assignment in week_map[current_week]["assignments"]:
            if is_missing(students[student]["id"], api_dict[assignment]):
                module_completed -= 1

        # same thing as before, BUT we're now going over the entire course. We also keep a record of the names of late assignments.
        # we do this so we can send the students a list of the assignments they can work on.
        actualcompleted = totalcomplete
        late_assignment_list = ""
        for week in weeks_to_send:
            for assignment in week_map[week]["assignments"]:
                if is_missing(students[student]["id"], api_dict[assignment]):
                    if assignment_dict[assignment]["showonlatelist"] != "False":
                        late_assignment_list += "- "+assignment+"\n"
                    actualcompleted -= 1

        # if anything is missing, we throw on this line for the email.
        if late_assignment_list != "":
            late_assignment_list = "In order to catch up, you can complete the following assignments:\n" + late_assignment_list

        # this appends everything as it'll go into the export. Pretty clear. 
        data.append({"Email Address":email, "Student":name, "Module":module, "Assignment Count":assignment_count,
        "Assignment List":assignmentlist, "Module Completed":module_completed, "Actual Completed Assigments":actualcompleted,
        "Total Assignments in Course":totalcourse, "Total Complete":totalcomplete, "Late Assignments":late_assignment_list})
    # logic to catch naming conventions based on OS
    if ":" in week_map[week]['name']:
        file = open(f"exports/Report - {week_map[week]['name'].split(':')[0]}.csv", "w", newline="")
    else:
        file = open(f"exports/Report - {week_map[week]['name']}.csv", "w", newline="")
    # write everything
    writer = csv.DictWriter(file, fieldnames=["Email Address", "Student", "Module", "Assignment Count", "Assignment List",
    "Module Completed", "Actual Completed Assigments", "Total Assignments in Course", "Total Complete", "Late Assignments"])
    writer.writeheader()
    writer.writerows(data)
    file.close()



# new function: this is being written to utilize the api to pull assignments, removing the need for the gradebook.
# other stuff will have to be rewritten, but this is the start of the pipeline.
def api_scrape():

    keys = ["name", "id", "missingif", "duedate", "duetimestamp", "showonlatelist"]
    defaults = ["No Name Found", 000000, "api", "2016-10-05 12:00:00", 1475683200.0, "True"]
    
    with open("./userdata/config.json", "r") as readfile:
        config = json.load(readfile)
        readfile.close()

    with open("./userdata/assignments.json", "r") as readfile:
        assignments = json.load(readfile)
        readfile.close()

    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        readfile.close()

    # a lot of this config reading (which we may add more) can eventually be put somewhere less scoped
    apikey = str(config["API"]["apikey"])
    course = str(config["API"]["course"])

    # build the api query
    query = "https://uncc.instructure.com/api/v1/courses/"+course+"/assignments?access_token="+apikey+"&per_page=250"
    r = requests.get(query)
    # sometimes Canvas will get mad at the number of requests, depending on the speed of the data transfer. This catches that issue and sleeps
    # the thread long enough to let us try again.
    while r.status_code == 403:
        print(f"Status Code 403, rerequesting assignments...")
        time.sleep(2)
        r = requests.get(query)

    new_assignments = json.loads(r.text)

    for assignment in new_assignments:

        if assignment["name"] not in list(assignments.keys()):
            
            assignments[assignment["name"]] = {"name":assignment["name"], "id":assignment["id"]}
            
            if "external_tool" in assignment["submission_types"] or assignment["submission_types"] == [] or "none" in assignment["submission_types"]:
                assignments[assignment["name"]]["missingif"] = "0"
            else:
                assignments[assignment["name"]]["missingif"] = "api"

            cd = assignment["due_at"]
            if cd != None:
                due_date = datetime.datetime(int(cd[:4]), int(cd[5:7]), int(cd[8:10]), int(cd[11:13]), int(cd[14:16]), int(cd[17:19]), tzinfo=datetime.timezone.utc).astimezone(tz=None)
                assignments[assignment["name"]]["duedate"] = due_date
            else:
                assignments[assignment["name"]]["duedate"] = datetime.datetime.fromtimestamp(1475683200)
            assignments[assignment["name"]]["duetimestamp"] = assignments[assignment["name"]]["duedate"].timestamp()

            assignments[assignment["name"]]["showonlatelist"] = "False"
        
        else:
            for index, key in enumerate(keys):
                if key not in assignments[assignment["name"]]:
                    assignments[assignment["name"]][key] = defaults[index]

    sorts = sorted(list(assignments.items()), key=lambda x: x[1]["duetimestamp"])
    export = {}
    for item in sorts:
        export[item[0]] = item[1]
        if type(export[item[0]]["duedate"]) != type(""):
            export[item[0]]["duedate"] = export[item[0]]["duedate"].strftime("%Y-%m-%d %H:%M:%S")

    with open("./userdata/assignments.json", "w") as file:
        json.dump(export, file, indent=4)

    query = "https://uncc.instructure.com/api/v1/courses/"+course+"/modules?access_token="+apikey+"&per_page=250"
    r = requests.get(query)
    # sometimes Canvas will get mad at the number of requests, depending on the speed of the data transfer. This catches that issue and sleeps
    # the thread long enough to let us try again.
    while r.status_code == 403:
        print(f"Status Code 403, rerequesting data...")
        time.sleep(2)
        r = requests.get(query)

    new_modules = json.loads(r.text)

    for module in new_modules:
       if module["name"] not in list(modules.keys()):
            modules[module["name"]] = {"id":module["id"], "name":module["name"], "assignments":[]}
    
    if "Homeless Assignments" in list(modules.keys()):
        del modules["Homeless Assignments"]

    assignments = list(export.keys())
    temp = list(assignments)
    for assignment in temp:
        for module in list(modules.keys()):
            if assignment in modules[module]["assignments"]:
                assignments.remove(assignment)
                break
    modules["Homeless Assignments"] = {}
    modules["Homeless Assignments"]["assignments"] = assignments

    with open("./userdata/modules.json", "w") as file:
        json.dump(modules, file, indent=4)
                
        



# made to get a list of students for the class
def get_students():
    #TODO: Add something that captures the student's section. This may be more involved than the users API.

    with open("./userdata/config.json", "r") as readfile:
        config = json.load(readfile)
        readfile.close()

    apikey = str(config["API"]["apikey"])
    course = str(config["API"]["course"])

    students_dict = {}
    page = 1

    while True:

        query = "https://uncc.instructure.com/api/v1/courses/"+course+"/users?access_token="+apikey+"&per_page=250&page="+str(page)

        r = requests.get(query)

        while r.status_code == 403:
            print(f"Status Code 403, rerequesting data...")
            time.sleep(2)
            r = requests.get(query)

        if r.text == "[]":
            break

        users = json.loads(r.text)
        for user in users:
            query2 = "https://uncc.instructure.com/api/v1/courses/"+course+"/enrollments?access_token="+apikey+"&user_id="+str(user["id"])
            r2 = requests.get(query2)
            while r2.status_code == 403:
                print(f"Status Code 403, rerequesting data...")
                time.sleep(2)
                r2 = requests.get(query2)
            student = json.loads(r2.text)[0]
            if student["role"] == "StudentEnrollment":
                student_id = student["user"]["login_id"]
                print(f"found student: {student_id}")
                students_dict[student_id] = {"name":student["user"]["sortable_name"], "email":student["user"]["login_id"]+"@charlotte.edu", "id":student["user"]["id"]}
        page += 1

    with open("./userdata/students.json", "w") as writefile:
        json.dump(students_dict, writefile, indent=4)

# sets up user configuration if it isnt present.
# everything in userdata is ignored by git, so we want to populate it all when the user launches (if its not there)
def setup_data(args):

    # make directories for files if they don't exist; it's fine to check this everytime this run.
    files = os.listdir()
    if "userdata" not in files:
        os.mkdir("./userdata")
    if "exports" not in files:
        os.mkdir("./exports")

    # below is a list of things that read args to determine what to rewrite. keeps functionality modular

    if "config" in args:
        make_config()

    if "assignments" in args:
        with open('./userdata/assignments.json', 'w') as writefile:
            json.dump({}, writefile, indent=4)
            writefile.close()

    if "modules" in args:
        with open('./userdata/modules.json', 'w') as writefile:
            json.dump({}, writefile, indent=4)
            writefile.close()

    if "students" in args:
        with open('./userdata/students.json', 'w') as writefile:
            json.dump({}, writefile, indent=4)
            writefile.close()

    if "api" in args:
        with open('./userdata/api.json', 'w') as writefile:
            json.dump({}, writefile, indent=4)
            writefile.close()


# since the config is particularly fiddly, it makes most since to have it be its own subfunc
# add stuff as needed
def make_config():
    config = {}
    config['DEFAULT'] = {'placeholder':''}
    config['API'] = {'apikey':'your_api_key_here', 'course':'your_course_here'}
    with open('./userdata/config.json', 'w') as writefile:
        json.dump(config, writefile, indent=4)
        writefile.close()

def get_week() -> str:

    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        module_names = list(modules.keys())
        readfile.close()
    
    print("Which of the following modules do you want to send? All modules prior to the first will be sent.")

    for index, module in enumerate(module_names):
        print(f"{index+1}) {module}")
    print("\n")
    input_string = int(input("Enter the number next to the module you want to send: "))
    return module_names[input_string-1]

def canvas_assignment_dump():
    with open("./userdata/config.json", "r") as readfile:
        config = json.load(readfile)
        readfile.close()

    # a lot of this config reading (which we may add more) can eventually be put somewhere less scoped
    apikey = str(config["API"]["apikey"])
    course = str(config["API"]["course"])
    query = "https://uncc.instructure.com/api/v1/courses/"+course+"/assignments?access_token="+apikey+"&per_page=250"
    r = requests.get(query)
    export = json.loads(r.text)
    with open("./userdata/canvas_assignments_dump.json", "w") as file:
        json.dump(export, file, indent=4)

# A Function that allows command line editing of the modules. Primarily intended to be used to combine modules from the course. 
# Can also be used for renames, cleanup, etc. A generally useful function.
def combine_modules(weeks, newname):
    # Bit of fluff for reading
    print("\n")

    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        readfile.close()

    # Create the newmodule as a separate unit at first; in case it shares name with existing module
    newmodule = {"id":-1, "name":newname, "assignments":[]}

    # Process modules, copying their assignments over and deleting the existing old modules.
    for module in weeks:
        newmodule["assignments"] += modules[module]["assignments"]
        del modules[module]

    # Now that removals are done, copy the new module into the file
    modules[newname] = newmodule

    # Save it
    with open("./userdata/modules.json", "w") as file:
        json.dump(modules, file, indent=4)



# This function works a lot like get_week(), but returns a list instead of a string. They could be combined,
# but in some cases forcing only a single option is better data safety. This is used for combine_modules().
def get_weeks() -> list:

    # Read modules and get names...
    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        module_names = list(modules.keys())
        readfile.close()

    # Print out the indicides for each module and their name; note the +1
    for index, module in enumerate(module_names):
        print(f"{index+1}) {module}")

    # Instructions
    print("\nWhich of the following modules do you want to combine? Separate module numbers with commas.\n")
    tosend = str(input("Enter the numbers next to the modules you want to combine: "))
    print("\n")
    
    # Strip all spaces
    tosend = tosend.replace(" ", "")

    # Make it into a list of strings
    modules_to_send = tosend.split(",")

    # Sort those strings; this is important to keep modules in order.
    modules_to_send = sorted(modules_to_send)
    
    # Prepare export list
    return_mods = []

    # Append each module desired to return list
    for module in modules_to_send:
        return_mods.append(module_names[int(module)-1])
    
    return return_mods

def change_late_list(week) -> None:

    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        weeks = list(modules.keys())[::-1]
        readfile.close()

    with open("./userdata/assignments.json", "r") as readfile:
        assignments = json.load(readfile)
        readfile.close()

    current_weeks = weeks[:weeks.index(week):-1] + [week]
    
    current_assignments = []
    for week in current_weeks:
        for assignment in modules[week]["assignments"]:
            current_assignments.append(assignment)

    on_list = []
    off_list = []
    for assignment in current_assignments:
        if assignments[assignment]["showonlatelist"] == "True":
            on_list.append(assignment)
        else:
            off_list.append(assignment)

    print("Do you want to remove (0) or add (1) assignments to the late list?")
    choice = int(input("Enter Choice (0 or 1): "))

    if choice == 1:
        flip_items = select_many_from_list(off_list, "assignment")
    else:
        flip_items = select_many_from_list(on_list, "assignment")

    flip_late_status(flip_items)



# I wrote this as a standalone just in case this is useful somewhere else.
def flip_late_status(assignments):

    assignment_data = get_assignments()

    for assignment in assignments:
        if assignment_data[assignment]["showonlatelist"] == "True":
            assignment_data[assignment]["showonlatelist"] = "False"
        else:
            assignment_data[assignment]["showonlatelist"] = "True"

    with open('./userdata/assignments.json', 'w') as writefile:
            json.dump(assignment_data, writefile, indent=4)
            writefile.close()
    

    

def select_one_from_list(stuff, resource_name="module"):
    for index, item in enumerate(stuff):
        print(f"{index+1}) {item}")
    print("\n")
    input_string = int(input(f"Enter the number next to the {resource_name} you want to use: "))
    return stuff[input_string-1]


def select_many_from_list(stuff, resource_name="module"):
    for index, item in enumerate(stuff):
        print(f"{index+1}) {item}")

    # Instructions
    print(f"\nWhich of the following {resource_name} do you want to use? Separate {resource_name} numbers with commas.\n")
    tosend = str(input(f"Enter the numbers next to the {resource_name} you want to use: "))
    print("\n")
    
    # Strip all spaces
    tosend = sorted(tosend.replace(" ", "").split(","))
    
    # Prepare export list
    return_items = []

    # Append each module desired to return list
    for item in tosend:
        return_items.append(stuff[int(item)-1])

    return return_items

def get_week_names() -> list:
    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        module_names = list(modules.keys())
        readfile.close()
    return module_names

def get_week_data() -> dict:
    with open("./userdata/modules.json", "r") as readfile:
        modules = json.load(readfile)
        readfile.close()
    return modules

# I'm going to try and make more funcs like this, so we can be more modular.
def get_assignments() -> dict:
    with open("./userdata/assignments.json", "r") as file:
        assignment_dict = json.load(file)
        file.close()
    return assignment_dict


    