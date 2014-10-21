test_module:
	../ansible/hacking/test-module -m ./marathon_app -a "state=present name=docker-registry host=http://10.10.7.10:8080 memory=128 instances=1 container=\"{'type': 'DOCKER', 'docker': {'image': 'registry:0.8.1', 'network': 'BRIDGE', 'portMappings': [{'containerPort': 5000, 'hostPort': 0, 'protocol': 'tcp'}]}}\" env=\"{'SETTINGS_FLAVOR': 'local', 'SEARCH_BACKEND': 'sqlalchemy'}\""

test_module_cluster:
	cd ./testenv && ansible-playbook -i inventory --module-path=../ -c ssh --sudo docker-registry.yml

setup_cluster:
	cd ./testenv && vagrant up
	cd ./testenv && ansible-playbook -i inventory --module-path=../ -c ssh --sudo mesos-cluster.yml
