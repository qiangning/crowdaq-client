set -e

if [ -z "$CROWDAQ_FILE" ]
then
	echo "Using local development config"
	CROWDAQ_FILE="local.json"
else
	echo "Using config $CROWDAQ_FILE"
fi

if [ -z "$CROWDAQ_USER" ]
then
	echo "Using local development config"
	CROWDAQ_USER="_"
else
	echo "Using config $CROWDAQ_USER"
fi


python cli.py -c $CROWDAQ_FILE login
echo Login
echo "Creating instruction"
python cli.py -c $CROWDAQ_FILE create instruction/$CROWDAQ_USER/test_instruction example_project/example_instruction.md --overwrite
echo "Creating tutorial"
python cli.py -c $CROWDAQ_FILE create tutorial/$CROWDAQ_USER/test_tutorial example_project/example_tutorial.json --overwrite
echo "Creating question set"
python cli.py -c $CROWDAQ_FILE create question_set/$CROWDAQ_USER/test_questionset example_project/example_questionset.json --overwrite
echo "Creating exam"
python cli.py -c $CROWDAQ_FILE create exam/$CROWDAQ_USER/test_exam example_project/example_exam.json --overwrite

echo "Creating task"
python cli.py -c $CROWDAQ_FILE create task/$CROWDAQ_USER/simple_task example_project/main_task/example_taskset.json --overwrite

# #
#echo "Creating question task assignment"
#python cli.py -c $CROWDAQ_FILE post https://dev.crowdaq.com/api/task_assignment/_/simple_task/new_assignment\?expSeconds\=1800\&assignmentCount\=3
#echo "Listing task assignment urls"
#python cli.py -c $CROWDAQ_FILE get https://dev.crowdaq.com/api/task_assignment/_/simple_task | jq .results[] | xargs -I {} echo http://127.0.0.1:8080/w/task/_/simple_task/{}
#
function get_task_assignment_url {
  cat $CROWDAQ_FILE | jq -r '.site_url + "/api/task_assignment/" + .user + "/simple_task/new_assignment?expSeconds=1800&assignmentCount=3"  '
}


echo "Creating question task assignment"
python cli.py -c $CROWDAQ_FILE post `get_task_assignment_url`
echo "Listing task assignment urls"


function list_task_ticket_url {
  cat $CROWDAQ_FILE | jq -r '.site_url + "/api/task_ticket/" + .user + "/simple_task"  '
}

function task_ticket_url {
  cat $CROWDAQ_FILE | jq -r '.site_url + "/api/task_assignment/" + .user + "/simple_task"  '
}


python cli.py -c $CROWDAQ_FILE get `list_task_ticket_url` | jq .results[].ticket_id | xargs -I {} echo `task_ticket_url`{}
 # | jq .results[].id | xargs -I {} echo `task_assignment_url`{}

