#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import subprocess
import sys
import time

from behave import *


@when(u'starting the application "{playbook}"')
def step_impl(context, playbook):
    cmd = "/bin/bash -c 'source ./ansible/hacking/env-setup && cd ./testenv && ansible-playbook -i inventory " \
          "--module-path=../ " + playbook + "'"

    try:
        subprocess.check_output([cmd], shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write(e.output)
        raise


@then(u'"{number}" tasks of the application "{application_id}" are running')
def step_impl(context, number, application_id):
    ip = os.environ.get('BEHAVE_IP', '127.0.0.1')

    rep = requests.get('http://' + ip + ':8080/v2/tasks',
                       headers={"Accept": "application/json"})

    data = rep.json()

    c = 0

    for key, item in enumerate(data["tasks"]):
        if item["appId"] == application_id:
            c += 1

    if c != int(number):
        raise RuntimeError("Marathon did not start application with id '" + application_id + "'")


@then(u'only one version of app "{application_id}" exists')
def step_impl(context, application_id):
    ip = os.environ.get('BEHAVE_IP', '127.0.0.1')
    rep = requests.get("http://" + ip + ":8080/v2/apps/" + application_id +
                       "/versions",
                       headers={"Accept": "application/json"})

    data = rep.json()

    version_count = len(data["versions"])
    if version_count != 1:
        raise RuntimeError("Expected one version of app {0} but found {1}"
                           .format(application_id, version_count))
