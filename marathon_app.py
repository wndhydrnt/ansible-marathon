#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import requests
from requests.exceptions import HTTPError

DOCUMENTATION = """
---
module: marathon_app
short_description: manage marathon apps
description:
  - Create, update or delete an app via the Marathon API.
options:
  args:
    description:
      - List of arguments passed to a task
  cpus:
    description:
      - Set number of CPUs to allocate for one container
    required: False
    default: 1.0
    aliases: []
  command:
    description:
      - Set the command to execute in a container.
    required: False
    default: null
    aliases: []
  constraints:
    description:
      - Control where apps run.
    required: false
    default: null
    aliases: []
  container:
    description:
      - Options of a container.
    required: False
    default: dict
    aliases: []
  env:
    description:
      - Key/value pairs passed to a container as environment variables.
    required: False
    default: dict
    aliases: []
  health_checks:
    description:
      - A list of health checks that Marathon should execute
    required: False
    default: list
    aliases: []
  host:
    description:
      - Set the URL to a Marathon host.
    required: False
    default: http://localhost:8080
    aliases: []
  instances:
    description:
      - Set the number of instances to spawn.
    required: False
    default: 1
    aliases: []
  memory:
    description:
      - Set how much memory to assign to an instance.
    required: False
    default: 256.0
    aliases: []
  name:
    description:
      - Set the name of the app.
    required: True
    default: null
    aliases: []
  state:
    description:
      - Indicate desired state of the target.
    required: False
    default: present
    choices: ['present', 'absent']
  wait:
    description:
      - Wait until all new tasks are in 'running' state.
    required: False
    default: yes
    choices: ['yes', 'no']
  wait_timeout:
    description:
      - Time to wait for a deployment to finish.
    required: False
    default: 300
"""

EXAMPLES = """
# Run a command in a container (note that the execution is delegated to localhost):

- hosts: localhost
  gather_facts: no
  sudo: no
  tasks:
    - marathon_app:
        state: present
        name: /simple_app
        host: http://marathon.example.com:8080
        memory: 16.0
        instances: 1
        command: env && sleep 300
      register: marathon

    - debug: var=marathon

# Run the Docker Registry inside a docker container and expose its HTTP port:

- hosts: localhost
  gather_facts: no
  sudo: no
  tasks:
    - marathon_app:
        state: present
        name: /docker-registry
        host: http://marathon.example.com:8080
        memory: 128.0
        instances: 1
        container:
          type: DOCKER
          docker:
            image: registry:0.8.1
            network: BRIDGE
            portMappings:
              - { containerPort: 5000, hostPort: 0, protocol: "tcp" }
        env:
          SETTINGS_FLAVOR: local
          SEARCH_BACKEND: sqlalchemy
"""


class TimeoutError(Exception):
    pass


class UnknownAppError(Exception):
    pass


class Marathon(object):
    def __init__(self, module):
        self._module = module

    def create(self):
        url = "{0}/v2/apps".format(self._module.params["host"])

        rep = requests.post(url, data=json.dumps(self._updated_data()),
                            headers={"Content-Type": "application/json"})
        rep.raise_for_status()

        self._check_deployment()

    def delete(self):
        rep = requests.delete(self._url())
        rep.raise_for_status()

    def exists(self):
        try:
            self._retrieve_app()
        except UnknownAppError:
            return False

        return True

    def gather_facts(self):
        app = self._retrieve_app()

        namespaces = app["id"].split("/")
        # First item in the list empty due to "id" starting with "/"
        del namespaces[0]

        app["namespaces"] = namespaces

        return app

    def needs_update(self, app):
        args_update = ((app["args"] != []
                        or self._module.params["args"] is not None)
                       and app["args"] != self._module.params["args"])

        if (args_update
                or app["cmd"] != self._sanitize_command()
                or app["cpus"] != self._module.params["cpus"]
                or app["env"] != self._sanitize_env()
                or app["healthChecks"] != self._module.params["health_checks"]
                or app["instances"] != self._module.params["instances"]
                or app["mem"] != self._module.params["memory"]):
            return True

        new_container = self._container_from_module()
        if app["container"]["type"] != new_container["type"]:
            return True

        if self._docker_container_changed(app["container"]["docker"],
                                          new_container["docker"]):
            return True

        if app["container"]["volumes"] != new_container["volumes"]:
            return True

        if self._module.params["constraints"] is None:
            module_constraints = []
        else:
            module_constraints = self._module.params["constraints"]
        if module_constraints != app["constraints"]:
            return True

        return False

    def sync(self):
        if self._module.params["state"] == "present":
            try:
                app = self._retrieve_app()
                if self.needs_update(app):
                    self.update(app)
                    self._module.exit_json(app=self.gather_facts(),
                                           changed=True)
                else:
                    self._module.exit_json(app=self.gather_facts(),
                                           changed=False)
            except HTTPError:
                self.create()
                self._module.exit_json(app=self.gather_facts(), changed=True)

        if self._module.params["state"] == "absent":
            try:
                self._retrieve_app()
                self.delete()
                self._module.exit_json(changed=True)
            except HTTPError:
                self._module.exit_json(changed=False)

    def update(self, app):
        previous_version = app["version"]

        rep = requests.put(self._url(), data=json.dumps(self._updated_data()),
                           headers={"Content-Type": "application/json"})
        rep.raise_for_status()

        self._check_deployment(previous_version)

    def _check_deployment(self, previous_version=None):
        if self._module.params["wait"] is False:
            return

        timeout = int(time.time()) + self._module.params["wait_timeout"]

        while int(time.time()) < timeout:
            time.sleep(5)
            app = self._retrieve_app()
            # Make sure all tasks are running
            if (previous_version != app["version"]
                    and app["tasksRunning"] == self._module.params["instances"]
                    and app["tasksStaged"] == 0):
                return

        raise TimeoutError("Marathon deployment timed out")

    def _container_from_module(self):
        container = {}

        if "container" not in self._module.params:
            return container

        if "docker" in self._module.params["container"]:
            container["docker"] = self._module.params["container"]["docker"]

        if "type" in self._module.params["container"]:
            container["type"] = self._module.params["container"]["type"]

        if "volumes" in self._module.params["container"]:
            container["volumes"] = self._module.params["container"]["volumes"]
        else:
            container["volumes"] = []

        # Set service ports to 0 for easier comparison
        for key, pm in enumerate(container["docker"]["portMappings"]):
            if "servicePort" not in pm:
                container["docker"]["portMappings"][key]["servicePort"] = 0

        return container

    def _docker_container_changed(self, app, module):
        if app["image"] != module["image"]:
            return True

        if app["network"] != module["network"]:
            return True

        if len(app["portMappings"]) != len(module["portMappings"]):
            return True

        found = 0

        for pm_module in module["portMappings"]:
            for pm_app in app["portMappings"]:
                service_port_equal = True

                if (pm_module["servicePort"] != 0
                        and pm_module["servicePort"] != pm_app["servicePort"]):
                    service_port_equal = False

                if (service_port_equal
                        and pm_module["containerPort"] == pm_app["containerPort"]
                        and pm_module["hostPort"] == pm_app["hostPort"]
                        and pm_module["protocol"] == pm_app["protocol"]):
                    found += 1

        if found != len(module["portMappings"]):
            return True

        return False

    def _id(self):
        if self._module.params["name"][0] == "/":
            return self._module.params["name"]

        return "/" + self._module.params["name"]

    def _retrieve_app(self):
        req = requests.get(self._url())

        req.raise_for_status()

        data = req.json()

        return data["app"]

    def _sanitize_command(self):
        if self._module.params["command"]:
            return self._module.params["command"]
        return None

    def _sanitize_env(self):
        env = self._module.params["env"]

        for env_key in env:
            if isinstance(env[env_key], str) is False:
                env[env_key] = str(env[env_key])

        return env

    def _updated_data(self):
        return {
            "args": self._module.params["args"],
            "cmd": self._sanitize_command(),
            "constraints": self._module.params["constraints"],
            "container": self._container_from_module(),
            "cpus": self._module.params["cpus"],
            "id": self._id(),
            "env": self._sanitize_env(),
            "healthChecks": self._module.params["health_checks"],
            "instances": self._module.params["instances"],
            "mem": self._module.params["memory"]
        }

    def _url(self):
        url = "{0}/v2/apps".format(self._module.params["host"])

        if self._module.params["name"][0] != "/":
            url += "/"

        url += self._module.params["name"]

        return url


def main():
    module = AnsibleModule(
        argument_spec=dict(
            args=dict(default=None, type="list"),
            cpus=dict(default=1.0, type="float"),
            command=dict(default=None, type="str"),
            constraints=dict(default=None, type="list"),
            container=dict(default=None, type="dict"),
            env=dict(default=dict(), type="dict"),
            health_checks=dict(default=list(), type="list"),
            host=dict(default="http://localhost:8080", type="str"),
            instances=dict(default=1, type="int"),
            memory=dict(default=256.0, type="float"),
            name=dict(required=True, type="str"),
            state=dict(default="present", choices=["absent", "present"], type="str"),
            wait=dict(default="yes", choices=BOOLEANS, type="bool"),
            wait_timeout=dict(default=300, type="int")
        ),
        mutually_exclusive=(["args", "cmd"],)
    )

    try:
        marathon = Marathon(module=module)

        marathon.sync()
    except (HTTPError, TimeoutError), e:
        module.fail_json(msg=str(e))

from ansible.module_utils.basic import *
main()
