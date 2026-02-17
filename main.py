import funcs
import os
import time

run = True

if os.name == 'nt':
    os.system('cls')
else:
    os.system('clear')

feedback = ''

# this is the most basic thing, but it just runs a interactive terminal thing for the tool. We can interact with any supporting functions from funcs, 
# but use this file to write software logic.
while run:
    print(feedback+"\n\n")
    print("""What command do you want to use? (Input a number)
    0) Setup Userdata
    1) Get Course Student List \t\t 2) Get Course Assignments
    3) Pull Current Assignment Details \t 4) Check Files (Deprecated)
    5) Make Emails \t\t\t 6) Exit
    7) Combine/Rename Modules""")
    command = int(input())
    match command:
        case 0:
            funcs.setup_data(["config","assignments","modules","api", "students"])
            feedback = 'Successfully set up user data!'
        case 1:
            funcs.get_students()
            feedback = 'Successfully pulled student data!'
        case 2:
            funcs.api_scrape()
            feedback = 'Successfully pulled assignment data!'
        case 3:
            funcs.canvas_api(funcs.get_week())
            feedback = 'Successfully pulled submission data!'
        case 4:
            funcs.check()
            feedback = 'Ran Check!'
        case 5:
            funcs.make_emails(funcs.get_week())
            feedback = 'Successfully made email in ./exports!'
        case 6:
            run = False
        case 7:
            funcs.combine_modules(funcs.get_weeks(), input("\nWhat would you like to rename these modules to? "))
            feedback = ""
        case 8:
            funcs.change_late_list(funcs.get_week())
            feedback = ""
        case 20:
            funcs.canvas_assignment_dump()
            feedback = 'DEBUG: Canvas export made in ./userdata!'
