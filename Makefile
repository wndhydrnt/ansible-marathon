behave: bootstrap
	if [ `uname` = "Darwin" ]; then BEHAVE_IP=10.10.7.10 behave; fi
	if [ `uname` = "Linux" ]; then BEHAVE_IP=127.0.0.1 behave; fi

bootstrap:
	if [ ! -d ./ansible ]; then git clone git@github.com:ansible/ansible.git ./ansible; fi
	cd ./ansible && git pull

test_module:
	./ansible/hacking/test-module -m ./marathon_app -a "@test_arguments.yml"
