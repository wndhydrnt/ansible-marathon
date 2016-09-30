test_module:
	./ansible/hacking/test-module -m ./marathon_app -a "@test_arguments.yml"

behave:
	if [ `uname` = "Darwin" ]; then BEHAVE_IP=10.10.7.10 behave; fi
	if [ `uname` = "Linux" ]; then BEHAVE_IP=127.0.0.1 behave; fi
