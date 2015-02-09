#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from marathon.models.app import MarathonHealthCheck
from marathon.models.constraint import MarathonConstraint

DOCUMENTATION = """
---
module: marathon_app
short_description: manage marathon apps
description:
  - Create, update or delete an app via the Marathon API.
options:
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

- hosts: mesos_masters
  tasks:
    - marathon_app: >
        state=present
        name=/simple_app
        host=http://marathon.example.com:8080
        memory=16.0
        instances=1
        command=env && sleep 300
      delegate_to: 127.0.0.1
      register: marathon

    - debug: var=marathon

# Run the Docker Registry inside a docker container and expose its HTTP port:

- hosts: mesos_masters
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
      delegate_to: 127.0.0.1
"""

HAS_MARATHON_PACKAGE = True

try:
    from marathon import log as marathon_logger
    from marathon.client import MarathonClient
    from marathon.exceptions import MarathonError, MarathonHttpError
    from marathon.models import MarathonApp
    from marathon.models.container import MarathonContainer
except ImportError:
    HAS_MARATHON_PACKAGE = False


class TimeoutError(Exception):
    pass


class UnknownAppError(Exception):
    pass


class Marathon(object):
    def __init__(self, client, module):
        self._client = client
        self._module = module

    def create(self):
        new_app = MarathonApp(args=self._module.params["args"],
                              cmd=self._sanitize_command(),
                              constraints=self._module.params["constraints"],
                              container=self._module.params["container"],
                              cpus=self._module.params["cpus"],
                              env=self._module.params["env"],
                              health_checks=self._module.params["health_checks"],
                              instances=self._module.params["instances"],
                              mem=self._module.params["memory"])

        self._client.create_app(self._module.params["name"], new_app)

        self._check_deployment()

        self._module.exit_json(app=self.gather_facts(), changed=True)

    def delete(self):
        self._client.delete_app(self._module.params["name"])

    def exists(self):
        try:
            self._retrieve_app()
        except UnknownAppError:
            return False

        return True

    def gather_facts(self):
        app = self._retrieve_app()

        namespaces = app.id.split("/")
        # First item in the list empty due to "id" starting with "/"
        del namespaces[0]

        # Best way to convert the object to a dict
        data = json.loads(app.to_json())
        data["namespaces"] = namespaces

        return data

    def needs_update(self):
        app = self._retrieve_app()

        args_update = ((app.args != []
                        or self._module.params["args"] is not None)
                       and app.args != self._module.params["args"])

        if (args_update
                or app.cmd != self._sanitize_command()
                or app.cpus != self._module.params["cpus"]
                or app.env != self._sanitize_env()
                or app.instances != self._module.params["instances"]
                or app.mem != self._module.params["memory"]):
            return True

        new_container = self._container_from_module()
        if app.container.type != new_container.type:
            return True

        if self._docker_container_changed(app.container.docker,
                                          new_container.docker):
            return True

        if len(app.container.volumes) != len(new_container.volumes):
            return True

        for k, vol in enumerate(app.container.volumes):
            if vol.to_json() != new_container.volumes[k].to_json():
                return True
        # Convert to arrays-in-array for easier comparison
        app_constraints = [c.json_repr() for c in app.constraints]
        if self._module.params["constraints"] is None:
            module_constraints = []
        else:
            module_constraints = self._module.params["constraints"]
        if module_constraints != app_constraints:
            return True

        app_health_checks = [hc.json_repr() for hc in app.health_checks]

        if self._module.params["health_checks"] is None:
            module_health_checks = []
        else:
            module_health_checks = [MarathonHealthCheck.from_json(hc).json_repr()
                                    for hc in self._module.params["health_checks"]]

        if app_health_checks != module_health_checks:
            return True

        return False

    def sync(self):
        if self._module.params["state"] == "present":
            if self.exists():
                if self.needs_update():
                    self.update()
                else:
                    self._module.exit_json(app=self.gather_facts(),
                                           changed=False)
            else:
                self.create()

        if self._module.params["state"] == "absent":
            if self.exists():
                self.delete()
                self._module.exit_json(changed=True)
            else:
                self._module.exit_json(changed=False)

    def update(self):
        app = self._retrieve_app()

        previous_version = app.version

        app.args = self._module.params["args"]
        app.cmd = self._module.params["command"]
        app.cpus = self._module.params["cpus"]
        app.env = self._sanitize_env()
        app.instances = self._module.params["instances"]
        app.mem = self._module.params["memory"]

        app.container = self._container_from_module()

        app.constraints = [MarathonConstraint(*c)
                           for c in (self._module.params["constraints"] or [])]

        app.health_checks = [MarathonHealthCheck.from_json(hc)
                             for hc in (self._module.params["health_checks"] or [])]

        self._client.update_app(self._module.params["name"], app)

        self._check_deployment(previous_version)

        self._module.exit_json(app=self.gather_facts(), changed=True)

    def _check_deployment(self, previous_version=None):
        if self._module.params["wait"] is False:
            return

        timeout = int(time.time()) + self._module.params["wait_timeout"]

        while int(time.time()) < timeout:
            time.sleep(5)
            app = self._retrieve_app()
            # Make sure all tasks are running
            if (previous_version != app.version
                    and app.tasks_running == self._module.params["instances"]
                    and app.tasks_staged == 0):
                return

        raise TimeoutError("Marathon deployment timed out")

    def _container_from_module(self):
        if "container" not in self._module.params:
            return MarathonContainer()

        docker = None
        type = "DOCKER"
        volumes = None

        if "docker" in self._module.params["container"]:
            docker = self._module.params["container"]["docker"]

        if "type" in self._module.params["container"]:
            type = self._module.params["container"]["type"]

        if "volumes" in self._module.params["container"]:
            volumes = self._module.params["container"]["volumes"]

        c = MarathonContainer(docker=docker, type=type, volumes=volumes)

        # Set service ports to 0 for easier comparison
        for pm in c.docker.port_mappings:
            if pm.service_port is None:
                pm.service_port = 0

        return c

    def _docker_container_changed(self, app, module):
        if app.image != module.image:
            return True

        if app.network != module.network:
            return True

        if len(app.port_mappings) != len(module.port_mappings):
            return True

        found = 0

        for pm_module in module.port_mappings:
            for pm_app in app.port_mappings:
                service_port_equal = True

                if (pm_module.service_port != 0 and pm_module.service_port != pm_app.service_port):
                    service_port_equal = False

                if (service_port_equal
                        and pm_module.container_port == pm_app.container_port
                        and pm_module.host_port == pm_app.host_port
                        and pm_module.protocol == pm_app.protocol):
                    found += 1

        if found != len(module.port_mappings):
            return True

        return False

    def _retrieve_app(self):
        try:
            return self._client.get_app(self._module.params["name"])
        except MarathonHttpError:
            raise UnknownAppError

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


def main():
    # Disable logger that ships with marathon package
    marathon_logger.disabled = True

    module = AnsibleModule(
        argument_spec=dict(
            args=dict(default=None, type="list"),
            cpus=dict(default=1.0, type="float"),
            command=dict(default=None, type="str"),
            constraints=dict(default=None, type="list"),
            container=dict(default=None, type="dict"),
            env=dict(default=dict(), type="dict"),
            health_checks=dict(default=None, type="list"),
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

    if HAS_MARATHON_PACKAGE is False:
        module.fail_json("The Ansible Marathon App module requires `marathon` >= 0.6.3")

    try:
        marathon_client = MarathonClient(module.params['host'])

        marathon = Marathon(client=marathon_client, module=module)

        marathon.sync()
    except (MarathonError, TimeoutError), e:
        module.fail_json(msg=str(e))

from ansible.module_utils.basic import *
main()
