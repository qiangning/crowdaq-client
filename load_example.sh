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
python cli.py -c $CROWDAQ_FILE create instruction/$CROWDAQ_USER/test_instruction example_project/example_instruction.md --overwrite
python cli.py -c $CROWDAQ_FILE create tutorial/$CROWDAQ_USER/test_tutorial example_project/example_tutorial.json --overwrite
python cli.py -c $CROWDAQ_FILE create question_set/$CROWDAQ_USER/test_questionset example_project/example_questionset.json --overwrite
python cli.py -c $CROWDAQ_FILE create exam/$CROWDAQ_USER/test_exam example_project/example_exam.json --overwrite

# Let try to disable one question.
#python cli.py -c $CROWDAQ_FILE sync-response exam/$CROWDAQ_USER/qa_ner /tmp
#python cli.py -c $CROWDAQ_FILE get-report exam/$CROWDAQ_USER/qa_ner

#python cli.py -c $CROWDAQ_FILE set question_set/_/qa_ner/question/bad_question_1 disable=true
#python mturk_cli.py -p mturk_default launch-exam  example_project/example_mturk_config.json https://dev.crowdaq.com/w/exam/hao/qa_ner

#python mturk_cli.py -p mturk_default expire-hit-group 1234567