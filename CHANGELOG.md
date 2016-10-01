# Changelog

## 2016-10-01

* Support `docker.portMappings.labels`

## 2016-02-03

* Support `ports`

## 2016-01-25

* Fix app being flagged as 'changed' when using HOST networking

## 2015-12-11

* Support `uris`
* Fix new deployments being triggered on every synchronisation
* Fix deployment being triggered when no labels are set

## 2015-08-07

* Support `labels`
* Use the deployment ID to determine that a deployment has finished

## 2015-05-03

* Fix application not being updated if a `servicePort` is removed

## 2015-03-17

* Support `backoffFactor`, `backoffSeconds` and `maxLaunchDelaySeconds`
* Fail with error message returned by Marathon instead of HTTP header

## 2015-03-07

* Support `healthChecks`

## 2014-12-12

* Fix error when value of an environment variable is an integer
* Fix 'args' being recognized as updated on subsequent requests

## 2014-11-24

* Treat an empty string as 'not set' for command parameter
* Fix infinite loop when updating an application on Marathon 0.7.5
* Increase wait before checking deployment status

## 2014-11-20

* Add support for 'args' parameter

## 2014-11-06

* Add support for 'constraints' parameter

## 2014-10-28

Initial release
