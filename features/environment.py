import os
import requests
import subprocess
import sys
import time


def before_all(context):
    ip = os.environ.get('BEHAVE_IP', '127.0.0.1')

    if ip == '127.0.0.1':
        docker_compose_cmd = 'BEHAVE_IP=127.0.0.1 docker-compose up -d'
    else:
        try:
            p = subprocess.Popen('vagrant up', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in iter(p.stdout.readline, ""):
                sys.stdout.write(line)
        except subprocess.CalledProcessError as e:
            sys.stdout.write(e.output)
            raise

        docker_compose_cmd = 'vagrant ssh -c "cd /vagrant && sudo BEHAVE_IP={0} docker-compose up -d"'.format(ip)

    try:
        vagrant_up = subprocess.Popen(docker_compose_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(vagrant_up.stdout.readline, ""):
            sys.stdout.write(line)
    except subprocess.CalledProcessError as e:
        sys.stdout.write(e.output)
        raise

def before_scenario(context, scenario):
    ip = os.environ.get('BEHAVE_IP', '127.0.0.1')
    apps_url = "http://{0}:8080/v2/apps".format(ip)

    try:
        rep = requests.get(apps_url, headers={"Accept": "application/json"})
    except requests.ConnectionError:
        # Wait ten seconds to account for Marathon starting up
        time.sleep(10)
        rep = requests.get(apps_url, headers={"Accept": "application/json"})

    data = rep.json()

    for key, app in enumerate(data["apps"]):
        requests.delete(apps_url + '/' + app["id"])
