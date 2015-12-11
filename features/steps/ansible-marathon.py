#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import subprocess
import sys
import time

from behave import *


default_marathon_version = "0.10.1-1.0.416.ubuntu1404"
default_mesos_version = "0.22.2-0.2.62.ubuntu1404"


@given(u'a running Marathon environment')
def step_impl(context):
    cmd = "cd ./testenv && MARATHON_VERSION={0} MESOS_VERSION={1} vagrant up"\
        .format(os.getenv("MARATHON_VERSION", default_marathon_version),
                os.getenv("MESOS_VERSION", default_mesos_version))

    try:
        subprocess.check_output([cmd], shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write(e.output)
        raise


@given(u'no applications running')
def step_impl(context):
    try:
        rep = requests.get("http://10.10.7.10:8080/v2/apps", headers={"Accept": "application/json"})
    except requests.ConnectionError:
        # Wait ten seconds to account for Marathon starting up
        time.sleep(10)
        rep = requests.get("http://10.10.7.10:8080/v2/apps", headers={"Accept": "application/json"})

    data = rep.json()

    for key, app in enumerate(data["apps"]):
        requests.delete("http://10.10.7.10:8080/v2/apps/" + app["id"])


@when(u'starting the application "{playbook}"')
def step_impl(context, playbook):
    cmd = "source ./ansible/hacking/env-setup && cd ./testenv && ansible-playbook -i inventory " \
          "--module-path=../ " + playbook

    try:
        subprocess.check_output([cmd], shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write(e.output)
        raise


@then(u'"{number}" tasks of the application "{application_id}" are running')
def step_impl(context, number, application_id):
    rep = requests.get("http://10.10.7.10:8080/v2/tasks",
                       headers={"Accept": "application/json"})

    data = rep.json()

    c = 0

    for key, item in enumerate(data["tasks"]):
        if item["appId"] == application_id:
            c += 1

    if c != int(number):
        raise RuntimeError("Marathon did not start application with id '" + application_id + "'")
