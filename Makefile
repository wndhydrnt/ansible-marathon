test_module:
	../ansible/hacking/test-module -m ./marathon_app -a "@test_arguments.yml"

test_module_cluster:
	cd ./testenv && ansible-playbook -i inventory --module-path=../ -c ssh --sudo docker-registry.yml

setup_cluster:
	cd ./testenv && vagrant up
	cd ./testenv && ansible-playbook -i inventory --module-path=../ -c ssh --sudo mesos-cluster.yml
