Feature: Ansible Marathon

  Scenario: Start an application
    Given a running Marathon environment
      And no applications running
     When starting the application "simple-app.yml"
     Then "1" tasks of the application "/simple-app" are running

  Scenario: Start several instances of an application
    Given a running Marathon environment
      And no applications running
     When starting the application "multiple-instances.yml"
     Then "2" tasks of the application "/multiple-instances" are running

  Scenario: Scale an application with changes
    Given a running Marathon environment
      And no applications running
     When starting the application "scale-app-first.yml"
      And starting the application "scale-app-second.yml"
     Then "2" tasks of the application "/scale-app" are running

  Scenario: Synchronising the same config file does not trigger a new deployment
    Given a running Marathon environment
      And no applications running
     When starting the application "no-change.yml"
      And starting the application "no-change.yml"
     Then only one version of app "no-change" exists
