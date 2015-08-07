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
