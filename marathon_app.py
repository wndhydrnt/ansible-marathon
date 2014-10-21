#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from marathon import log as marathon_logger
from marathon.client import MarathonClient
from marathon.exceptions import MarathonError, MarathonHttpError
from marathon.models import MarathonApp
from marathon.models.container import MarathonContainer


class UnknownAppError(Exception):
    pass


class Marathon(object):
    def __init__(self, client, module):
        self._client = client
        self._module = module

    def create(self):
        app = MarathonApp(cmd=self._module.params["command"],
                          container=self._module.params["container"],
                          cpus=self._module.params["cpus"],
                          env=self._module.params["env"],
                          instances=self._module.params["instances"],
                          mem=self._module.params["memory"])

        self._client.create_app(self._module.params["name"], app)
        self._module.exit_json(changed=True)

    def delete(self):
        self._client.delete_app(self._module.params["name"])

    def exists(self):
        try:
            self._retrieve_app()
        except UnknownAppError:
            return False

        return True

    def needs_update(self):
        app = self._retrieve_app()

        if (app.cmd != self._module.params["command"]
                or app.cpus != self._module.params["cpus"]
                or app.env != self._module.params["env"]
                or app.instances != self._module.params["instances"]
                or app.mem != self._module.params["memory"]):
            return True

        new_container = self._container_from_module()
        if app.container.type != new_container.type:
            return True

        if app.container.docker.to_json() != new_container.docker\
                .to_json():
            return True

        if len(app.container.volumes) != len(new_container.volumes):
            return True

        for k, vol in enumerate(app.container.volumes):
            if vol.to_json() != new_container.volumes[k].to_json():
                return True

        return False

    def update(self):
        app = self._retrieve_app()

        # Work around a bug in marathon-python where the version key is sent
        # during update. This leads to the update not being applied.
        app.version = None

        app.cmd = self._module.params["command"]
        app.cpus = self._module.params["cpus"]
        app.env = self._module.params["env"]
        app.instances = self._module.params["instances"]
        app.mem = self._module.params["memory"]

        app.container = self._container_from_module()

        self._client.update_app(self._module.params["name"], app)

        self._module.exit_json(changed=True)

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

        # Set service port to 0 for easier comparison
        for pm in c.docker.port_mappings:
            if pm.service_port is None:
                pm.service_port = 0

        return c

    def _retrieve_app(self):
        try:
            return self._client.get_app(self._module.params["name"])
        except MarathonHttpError:
            raise UnknownAppError
        except MarathonError as e:
            self._module.fail_json(msg=e.message)


def main():
    # Disable logger that ships with marathon-python package
    marathon_logger.disabled = True

    module = AnsibleModule(
        argument_spec = dict(
            cpus=dict(default=1.0, type="float"),
            command=dict(default=None, type="str"),
            container=dict(default=dict(), type="dict"),
            env=dict(default=dict(), type="dict"),
            host=dict(default="http://localhost:8080", type="str"),
            instances=dict(default=1, type="int"),
            memory=dict(default=256.0, type="float"),
            name=dict(required=True, type="str"),
            state=dict(default="present", choices=["absent", "present"], type="str"),
            wait=dict(default="yes", type="bool")
        )
    )

    marathon_client = MarathonClient(module.params['host'])

    marathon = Marathon(client=marathon_client, module=module)

    if module.params["state"] == "present":
        if marathon.exists():
            if marathon.needs_update():
                marathon.update()
            else:
                module.exit_json(changed=False)
        else:
            marathon.create()

    if module.params["state"] == "absent":
        if marathon.exists():
            marathon.delete()
            module.exit_json(changed=True)
        else:
            module.exit_json(changed=False)

from ansible.module_utils.basic import *
main()
